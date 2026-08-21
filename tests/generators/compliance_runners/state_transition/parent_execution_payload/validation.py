"""Independent validation for parent-execution-payload compliance vectors."""

from __future__ import annotations

from ..validation import Check, decode

from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from eth_consensus_specs.gloas import minimal as spec

_YAML = YAML(typ="safe")

def _payment_dimensions(pre: Any) -> tuple[str, bool]:
    parent_bid = pre.latest_execution_payload_bid
    parent_slot = int(parent_bid.slot)
    parent_epoch = int(spec.compute_epoch_at_slot(parent_slot))
    current_epoch = int(spec.get_current_epoch(pre))
    if parent_epoch == current_epoch:
        settlement = "CURRENT_EPOCH"
        payment_index = int(spec.SLOTS_PER_EPOCH) + parent_slot % int(spec.SLOTS_PER_EPOCH)
        nonzero = int(pre.builder_pending_payments[payment_index].withdrawal.amount) > 0
    elif parent_epoch == int(spec.get_previous_epoch(pre)):
        settlement = "PREVIOUS_EPOCH"
        payment_index = parent_slot % int(spec.SLOTS_PER_EPOCH)
        nonzero = int(pre.builder_pending_payments[payment_index].withdrawal.amount) > 0
    else:
        settlement = "EVICTED"
        nonzero = int(parent_bid.value) > 0
    return settlement, nonzero

def recover(pre: Any, block: Any) -> dict[str, Any]:
    """Recover input, trace, outcome, and effect dimensions from a vector."""
    parent_bid = pre.latest_execution_payload_bid
    bid = block.body.signed_execution_payload_bid.message
    requests = block.body.parent_execution_requests

    revealed = bid.parent_block_hash == parent_bid.block_hash
    requests_empty = requests == spec.ExecutionRequests()
    root_matches = spec.hash_tree_root(requests) == parent_bid.execution_requests_root
    withdrawals_ok = len(requests.withdrawals) <= spec.MAX_WITHDRAWAL_REQUESTS_PER_PAYLOAD
    consolidations_ok = len(requests.consolidations) <= spec.MAX_CONSOLIDATION_REQUESTS_PER_PAYLOAD
    builder_deposits_ok = (
        len(requests.builder_deposits) <= spec.MAX_BUILDER_DEPOSIT_REQUESTS_PER_PAYLOAD
    )
    builder_exits_ok = len(requests.builder_exits) <= spec.MAX_BUILDER_EXIT_REQUESTS_PER_PAYLOAD
    settlement, value_nonzero = _payment_dimensions(pre)

    requests_empty_checked = not revealed
    requests_root_checked = revealed
    withdrawals_checked = revealed and root_matches
    consolidations_checked = withdrawals_checked and withdrawals_ok
    builder_deposits_checked = consolidations_checked and consolidations_ok
    builder_exits_checked = builder_deposits_checked and builder_deposits_ok
    dispatches = builder_exits_checked and builder_exits_ok and not requests_empty

    if not revealed:
        outcome = (
            "EMPTY_PARENT_NOOP" if requests_empty else "REJECT_NONEMPTY_REQUESTS_FOR_EMPTY_PARENT"
        )
    elif not root_matches:
        outcome = "REJECT_REQUESTS_ROOT"
    elif not withdrawals_ok:
        outcome = "REJECT_WITHDRAWALS_CAP"
    elif not consolidations_ok:
        outcome = "REJECT_CONSOLIDATIONS_CAP"
    elif not builder_deposits_ok:
        outcome = "REJECT_BUILDER_DEPOSITS_CAP"
    elif not builder_exits_ok:
        outcome = "REJECT_BUILDER_EXITS_CAP"
    elif settlement == "CURRENT_EPOCH":
        outcome = (
            "APPLY_CURRENT_WITH_WITHDRAWAL" if value_nonzero else "APPLY_CURRENT_NO_WITHDRAWAL"
        )
    elif settlement == "PREVIOUS_EPOCH":
        outcome = "APPLY_PREVIOUS_WITH_WITHDRAWAL"
    else:
        outcome = (
            "APPLY_EVICTED_WITH_WITHDRAWAL" if value_nonzero else "APPLY_EVICTED_NO_WITHDRAWAL"
        )

    applied = outcome.startswith("APPLY_")
    return {
        "parent_payload_revealed": revealed,
        "requests_empty": requests_empty,
        "requests_root_matches": root_matches,
        "withdrawals_within_cap": withdrawals_ok,
        "consolidations_within_cap": consolidations_ok,
        "builder_deposits_within_cap": builder_deposits_ok,
        "builder_exits_within_cap": builder_exits_ok,
        "deposits_nonempty": len(requests.deposits) > 0,
        "dispatches_nonempty_requests": dispatches,
        "payment_settlement": settlement,
        "payment_value_nonzero": value_nonzero,
        "requests_empty_checked": requests_empty_checked,
        "requests_root_checked": requests_root_checked,
        "withdrawals_cap_checked": withdrawals_checked,
        "consolidations_cap_checked": consolidations_checked,
        "builder_deposits_cap_checked": builder_deposits_checked,
        "builder_exits_cap_checked": builder_exits_checked,
        "outcome": outcome,
        "state_effected": applied,
        "payment_withdrawal_appended": applied and value_nonzero,
        "payment_slot_cleared": applied and settlement in {"CURRENT_EPOCH", "PREVIOUS_EPOCH"},
    }

def _check_applied_output(pre: Any, post: Any, actual: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    parent_bid = pre.latest_execution_payload_bid
    parent_slot = int(parent_bid.slot)
    availability_index = parent_slot % int(spec.SLOTS_PER_HISTORICAL_ROOT)
    if post.execution_payload_availability[availability_index] != 0b1:
        errors.append("parent payload availability bit was not set")
    if post.latest_block_hash != parent_bid.block_hash:
        errors.append("latest_block_hash was not updated to the parent block hash")

    expected_growth = int(actual["payment_withdrawal_appended"])
    growth = len(post.builder_pending_withdrawals) - len(pre.builder_pending_withdrawals)
    if growth != expected_growth:
        errors.append(f"builder_pending_withdrawals grew by {growth}, expected {expected_growth}")

    settlement = actual["payment_settlement"]
    if settlement in {"CURRENT_EPOCH", "PREVIOUS_EPOCH"}:
        offset = parent_slot % int(spec.SLOTS_PER_EPOCH)
        payment_index = offset
        if settlement == "CURRENT_EPOCH":
            payment_index += int(spec.SLOTS_PER_EPOCH)
        if post.builder_pending_payments[payment_index] != spec.BuilderPendingPayment():
            errors.append("settled builder payment slot was not cleared")
    elif any(
        before != after
        for before, after in zip(
            pre.builder_pending_payments,
            post.builder_pending_payments,
            strict=True,
        )
    ):
        errors.append("evicted payment changed builder_pending_payments")
    return errors

def validate_case(case_dir: Path) -> tuple[list[Check], list[str]]:
    pre = decode(case_dir / "pre.ssz_snappy", spec.BeaconState)
    block = decode(case_dir / "block.ssz_snappy", spec.BeaconBlock)
    post_path = case_dir / "post.ssz_snappy"
    post = decode(post_path, spec.BeaconState) if post_path.exists() else None
    claimed = _YAML.load((case_dir / "dimensions.yaml").read_text())["claimed"]
    actual = recover(pre, block)
    checks = [
        Check(name, value, actual.get(name), "ok" if actual.get(name) == value else "mismatch")
        for name, value in claimed.items()
    ]

    rejected = actual["outcome"].startswith("REJECT_")
    errors: list[str] = []
    oracle = pre.copy()
    try:
        spec.process_parent_execution_payload(oracle, block)
    except (AssertionError, IndexError):
        if not rejected:
            errors.append("spec re-execution rejected a claimed successful case")
        if post is not None:
            errors.append("rejected operation must not have a post state")
        return checks, errors

    if rejected:
        errors.append("spec re-execution accepted a claimed rejected case")
        return checks, errors
    if post is None:
        return checks, ["successful operation is missing post state"]
    if oracle.hash_tree_root() != post.hash_tree_root():
        errors.append("post state does not match spec re-execution")
    if actual["outcome"] == "EMPTY_PARENT_NOOP":
        if post.hash_tree_root() != pre.hash_tree_root():
            errors.append("empty-parent path changed state")
    else:
        errors.extend(_check_applied_output(pre, post, actual))
    return checks, errors
