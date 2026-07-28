"""Coverage profiles for the Gloas ``process_withdrawals`` handler."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

from eth_consensus_specs.gloas import minimal as spec
from tests.generators.compliance_runners.state_transition.aspect_coverage import (
    cover,
    dedup,
    enumerate_signatures,
)
from tests.generators.compliance_runners.state_transition.withdrawals.materializer import (
    _DIMS,
    WithdrawalsMaterializer,
)

INPUT_ASPECTS = {
    "parent_payload": ["parent_payload_revealed"],
    "builder_pending": ["builder_pending_nonempty"],
    "pending_partial": ["pending_partial_nonempty"],
    "builder_sweep": ["builder_sweep_nonempty"],
    "validator_sweep": ["validator_sweep_nonempty"],
    "withdrawal_capacity": ["withdrawals_over_limit"],
}
OUTCOME_ASPECT = {"outcome": ["outcome", "state_effected"]}
ALL_ASPECTS = {**INPUT_ASPECTS, **OUTCOME_ASPECT}
ACCEPT = {
    "FULL_NO_WITHDRAWALS",
    "BUILDER_PENDING",
    "PENDING_PARTIAL",
    "BUILDER_SWEEP",
    "VALIDATOR_SWEEP",
    "MIXED_WITHDRAWALS",
    "MAX_WITHDRAWALS_LIMIT",
}
MODEL = Path(__file__).parent / "models" / "handler_withdrawals.mzn"


def _nfaults(record: dict) -> int:
    return int(not record["parent_payload_revealed"])


PROFILES = {
    "onewise": (ALL_ASPECTS, 1, None),
    "pairwise": (ALL_ASPECTS, 2, None),
    "normal": (INPUT_ASPECTS, 2, "normal"),
    "exceptional": (OUTCOME_ASPECT, 1, "exceptional"),
}


def _recs():
    return enumerate_signatures(MODEL, _DIMS, ALL_ASPECTS, _nfaults)


def build_profile(records, name: str):
    if name == "standard":
        _, normal = cover(records, *PROFILES["normal"], accept=ACCEPT)
        _, exceptional = cover(records, *PROFILES["exceptional"], accept=ACCEPT)
        return -1, dedup(normal + exceptional, ALL_ASPECTS)
    aspects, strength, outcome_filter = PROFILES[name]
    return cover(records, aspects, strength, outcome_filter, accept=ACCEPT)


def materialize_profile(name: str) -> int:
    _, chosen = build_profile(_recs(), name)
    return WithdrawalsMaterializer(spec, MODEL).materialize_reps(
        Path(__file__).parent / "reftests", [SimpleNamespace(**record) for record in chosen]
    )


def main() -> int:
    args = [arg for arg in sys.argv[1:] if not arg.startswith("--")]
    materialize = "--materialize" in sys.argv
    records = _recs()
    print(f"distinct aspect-state signatures: {len(records)}\n")
    if not args:
        print(f"{'profile':14} {'obligations':>12} {'cases':>7}")
        for name in ("onewise", "normal", "exceptional"):
            obligations, cases = build_profile(records, name)
            print(f"{name:14} {obligations:>12} {len(cases):>7}")
        _, cases = build_profile(records, "standard")
        print(f"{'standard':14} {'(union)':>12} {len(cases):>7}")
        return 0
    obligations, cases = build_profile(records, args[0])
    print(
        f"profile '{args[0]}': {len(cases)} cases"
        + (f" covering {obligations} obligations" if obligations >= 0 else "")
    )
    if materialize:
        materialize_profile(args[0])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
