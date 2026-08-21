"""Independent validation of process_execution_payload_bid vectors.

Recovers every applicable coverage dimension directly from the decoded pre state
and SignedExecutionPayloadBid via the real spec predicates, compares to the
serialized solution in dimensions.yaml, recomputes the outcome, and runs the
handler as an oracle (post present + matching iff accepted). Imports neither the
materializer nor the model.

Usage:
    uv run python -m tests.generators.compliance_runners.state_transition.execution_payload_bid.validation [REFTESTS_DIR]
"""
from __future__ import annotations

from ..validation import Check, decode

from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from eth_consensus_specs.gloas import minimal as spec

_YAML = YAML(typ="safe")

def _cmp(a: int, b: int) -> str:
    return "LT" if a < b else ("EQ" if a == b else "GT")

def _tri(x: bool) -> str:
    return "T" if x else "F"

def recover(pre: Any, signed: Any) -> dict[str, Any]:
    bid = signed.message
    idx = bid.builder_index
    n_builders = len(pre.builders)

    if idx == spec.BUILDER_INDEX_SELF_BUILD:
        ref = "SELF_BUILD"
    elif int(idx) < n_builders:
        ref = "EXISTING"
    else:
        ref = "NON_EXISTING"
    self_build = ref == "SELF_BUILD"
    current_epoch = spec.get_current_epoch(pre)
    past_genesis = int(pre.slot) > spec.GENESIS_SLOT

    r: dict[str, Any] = {
        "builder_ref": ref,
        "self_build": self_build,
        "amount_positive": int(bid.value) > 0,
        "state_slot_past_genesis": past_genesis,
        "bid_parent_block_hash_matches": bid.parent_block_hash == pre.latest_block_hash,
        "bid_prev_randao_matches": bid.prev_randao == spec.get_randao_mix(pre, current_epoch),
    }

    max_blobs = spec.get_blob_parameters(current_epoch).max_blobs_per_block
    r["bid_kzg_to_max"] = _cmp(len(bid.blob_kzg_commitments), max_blobs)
    r["bid_slot_to_state"] = _cmp(int(bid.slot), int(pre.slot))

    # parent_block_root: only defined past genesis
    if past_genesis:
        expected = spec.get_block_root_at_slot(pre, spec.Slot(int(pre.slot) - 1))
        r["bid_parent_block_root_matches"] = _tri(bid.parent_block_root == expected)
    else:
        r["bid_parent_block_root_matches"] = "NA"

    # self-build signature
    r["self_build_signature_is_infinity"] = (
        _tri(signed.signature == spec.bls.G2_POINT_AT_INFINITY) if self_build else "NA"
    )

    # EXISTING-only builder dimensions
    if ref == "EXISTING":
        b = pre.builders[idx]
        finalized = int(pre.finalized_checkpoint.epoch)
        min_balance = int(spec.MIN_DEPOSIT_AMOUNT) + int(
            spec.get_pending_balance_to_withdraw_for_builder(pre, idx)
        )
        r["builder_deposit_to_finalized_epoch"] = _cmp(int(b.deposit_epoch), finalized)
        r["builder_withdrawable_epoch_set"] = _tri(b.withdrawable_epoch != spec.FAR_FUTURE_EPOCH)
        r["builder_version_valid"] = _tri(b.version == spec.PAYLOAD_BUILDER_VERSION)
        r["builder_has_pending_withdrawal"] = _tri(
            any(w.builder_index == idx and int(w.amount) > 0 for w in pre.builder_pending_withdrawals)
        )
        r["builder_has_pending_payment"] = _tri(
            any(p.withdrawal.builder_index == idx and int(p.withdrawal.amount) > 0
                for p in pre.builder_pending_payments)
        )
        r["builder_balance_to_min_balance"] = _cmp(int(b.balance), min_balance)
        r["builder_available_to_bid"] = (
            _cmp(int(b.balance) - min_balance, int(bid.value)) if int(b.balance) >= min_balance else "NA"
        )
        r["builder_signature_valid"] = _tri(spec.verify_execution_payload_bid_signature(pre, signed))
        r["builder_active"] = bool(spec.is_active_builder(pre, idx))
        r["builder_can_cover_bid"] = bool(spec.can_builder_cover_bid(pre, idx, bid.value))
    else:
        for name in (
            "builder_deposit_to_finalized_epoch", "builder_withdrawable_epoch_set",
            "builder_version_valid", "builder_has_pending_withdrawal", "builder_has_pending_payment",
            "builder_balance_to_min_balance", "builder_available_to_bid", "builder_signature_valid",
        ):
            r[name] = "NA"
        r["builder_active"] = False
        r["builder_can_cover_bid"] = False

    r["outcome"] = _derive_outcome(r)
    return r

def _derive_outcome(r: dict[str, Any]) -> str:
    def common() -> str:
        if r["bid_kzg_to_max"] not in ("LT", "EQ"):
            return "REJECT_KZG_OVER_LIMIT"
        if r["bid_slot_to_state"] != "EQ":
            return "REJECT_WRONG_SLOT"
        if not r["state_slot_past_genesis"]:
            return "REJECT_NOT_PAST_GENESIS"
        if not r["bid_parent_block_hash_matches"]:
            return "REJECT_PARENT_HASH"
        if r["bid_parent_block_root_matches"] != "T":
            return "REJECT_PARENT_ROOT"
        if not r["bid_prev_randao_matches"]:
            return "REJECT_PREV_RANDAO"
        return "ACCEPT"

    if r["self_build"]:
        if r["amount_positive"]:
            return "REJECT_SELF_BUILD_NONZERO_AMOUNT"
        if r["self_build_signature_is_infinity"] != "T":
            return "REJECT_SELF_BUILD_BAD_SIGNATURE"
        return common()
    if r["builder_ref"] == "NON_EXISTING":
        return "REJECT_BUILDER_NOT_FOUND"
    if not r["builder_active"]:
        return "REJECT_BUILDER_INACTIVE"
    if r["builder_version_valid"] != "T":
        return "REJECT_WRONG_VERSION"
    if not r["builder_can_cover_bid"]:
        return "REJECT_UNDERFUNDED"
    if r["builder_signature_valid"] != "T":
        return "REJECT_BAD_SIGNATURE"
    return common()

def validate_case(case_dir: Path) -> tuple[list[Check], list[str]]:
    pre = decode(case_dir / "pre.ssz_snappy", spec.BeaconState)
    signed = decode(case_dir / "execution_payload_bid.ssz_snappy", spec.SignedExecutionPayloadBid)
    claimed = _YAML.load((case_dir / "dimensions.yaml").read_text())["claimed"]
    actual = recover(pre, signed)

    checks = [
        Check(dim, claim, actual.get(dim, "<none>"),
              "ok" if actual.get(dim, "<none>") == claim else "mismatch")
        for dim, claim in claimed.items()
    ]

    # Oracle: run the handler; accepted iff it does not raise.
    errors: list[str] = []
    post_path = case_dir / "post.ssz_snappy"
    oracle = pre.copy()
    accepted = True
    try:
        spec.process_execution_payload_bid(oracle, signed)
    except (AssertionError, IndexError):
        accepted = False

    if accepted and not post_path.exists():
        errors.append("handler accepted but no post recorded")
    if not accepted and post_path.exists():
        errors.append("handler rejected but post present")
    if accepted and post_path.exists():
        post = decode(post_path, spec.BeaconState)
        if oracle.hash_tree_root() != post.hash_tree_root():
            errors.append("post does not match spec re-execution")
    if accepted != (claimed.get("outcome") == "ACCEPT"):
        errors.append(f"accepted={accepted} but outcome={claimed.get('outcome')}")
    return checks, errors
