"""Independently validate Gloas ``process_withdrawals`` compliance vectors."""

from __future__ import annotations

from ..validation import Check, decode

from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from eth_consensus_specs.gloas import minimal as spec

_YAML = YAML(typ="safe")

def recover(pre: Any) -> dict[str, Any]:
    parent_full = pre.latest_block_hash == pre.latest_execution_payload_bid.block_hash
    current_epoch = spec.get_current_epoch(pre)
    builder_pending = bool(pre.builder_pending_withdrawals)
    pending_partial = bool(pre.pending_partial_withdrawals)
    builder_sweep = any(
        builder.withdrawable_epoch <= current_epoch and builder.balance > 0
        for builder in pre.builders
    )
    validator_sweep = any(
        spec.is_fully_withdrawable_validator(validator, pre.balances[index], current_epoch)
        or spec.is_partially_withdrawable_validator(validator, pre.balances[index])
        for index, validator in enumerate(pre.validators)
    )
    if not parent_full:
        builder_pending = pending_partial = builder_sweep = validator_sweep = False
        over_limit = False
    else:
        over_limit = (
            len(spec.get_expected_withdrawals(pre).withdrawals) == spec.MAX_WITHDRAWALS_PER_PAYLOAD
        )
    active_sources = sum((builder_pending, pending_partial, builder_sweep, validator_sweep))
    if not parent_full:
        outcome = "PARENT_EMPTY_NOOP"
    elif over_limit:
        outcome = "MAX_WITHDRAWALS_LIMIT"
    elif active_sources == 0:
        outcome = "FULL_NO_WITHDRAWALS"
    elif active_sources >= 2:
        outcome = "MIXED_WITHDRAWALS"
    elif builder_pending:
        outcome = "BUILDER_PENDING"
    elif pending_partial:
        outcome = "PENDING_PARTIAL"
    elif builder_sweep:
        outcome = "BUILDER_SWEEP"
    else:
        outcome = "VALIDATOR_SWEEP"
    return {
        "parent_payload_revealed": parent_full,
        "builder_pending_nonempty": builder_pending,
        "pending_partial_nonempty": pending_partial,
        "builder_sweep_nonempty": builder_sweep,
        "validator_sweep_nonempty": validator_sweep,
        "withdrawals_over_limit": over_limit,
        "state_effected": parent_full,
        "outcome": outcome,
    }

def validate_case(case_dir: Path) -> tuple[list[Check], list[str]]:
    pre = decode(case_dir / "pre.ssz_snappy", spec.BeaconState)
    post = decode(case_dir / "post.ssz_snappy", spec.BeaconState)
    claimed = _YAML.load((case_dir / "dimensions.yaml").read_text())["claimed"]
    actual = recover(pre)
    checks = [
        Check(name, value, actual.get(name), "ok" if actual.get(name) == value else "mismatch")
        for name, value in claimed.items()
    ]
    oracle = pre.copy()
    spec.process_withdrawals(oracle)
    errors = []
    if oracle.hash_tree_root() != post.hash_tree_root():
        errors.append("post state does not match spec re-execution")
    if (pre.hash_tree_root() != post.hash_tree_root()) != actual["state_effected"]:
        errors.append("state change does not match state_effected")
    return checks, errors
