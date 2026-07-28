"""Independently validate Gloas ``process_withdrawals`` compliance vectors."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import snappy
from ruamel.yaml import YAML

from eth_consensus_specs.gloas import minimal as spec

_YAML = YAML(typ="safe")


@dataclass
class Check:
    dimension: str
    claimed: Any
    actual: Any
    status: str


def _decode(path: Path, sedes: Any) -> Any:
    return sedes.decode_bytes(snappy.decompress(path.read_bytes()))


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
    pre = _decode(case_dir / "pre.ssz_snappy", spec.BeaconState)
    post = _decode(case_dir / "post.ssz_snappy", spec.BeaconState)
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
    if (pre.hash_tree_root() != post.hash_tree_root()) != bool(claimed["state_effected"]):
        errors.append("state change does not match state_effected")
    return checks, errors


def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "reftests"
    case_dirs = sorted(root.glob("**/operations/withdrawals/**/case_*"))
    if not case_dirs:
        print(f"No cases found under {root}")
        return 1
    failures = 0
    for case_dir in case_dirs:
        checks, errors = validate_case(case_dir)
        mismatches = [check for check in checks if check.status == "mismatch"]
        failures += len(mismatches) + len(errors)
        print(f"{case_dir.name}: {'OK' if not mismatches and not errors else 'FAIL'}")
        for check in mismatches:
            print(f"    {check.dimension}: claimed={check.claimed!r} actual={check.actual!r}")
        for error in errors:
            print(f"    {error}")
    print(f"{'PASSED' if not failures else 'FAILED'}: {len(case_dirs)} cases")
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
