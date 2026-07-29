"""Coverage profiles for Gloas ``process_pending_deposits``."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

from eth_consensus_specs.gloas import minimal as spec
from tests.generators.compliance_runners.state_transition.aspect_coverage import (
    cover,
    enumerate_signatures,
)

from .materializer import _DIMS, PendingDepositsMaterializer

QUEUE_ASPECT = {
    "queue_layout": ["queue_layout", "secondary_role"],
    "finalization_and_limit": ["primary_reached"],
}
VALIDATOR_ASPECT = {
    "validator_membership": ["validator_pubkey_found"],
    "validator_lifecycle": ["validator_active", "validator_exiting"],
    "withdrawable_boundary": ["withdrawable_epoch_to_next_epoch"],
}
DEPOSIT_ASPECT = {"deposit_signature": ["deposit_signature_valid"]}
CHURN_ASPECT = {
    "carried_churn": ["initial_churn"],
    "amount_to_available": ["primary_amount_to_available"],
    "second_amount_to_remaining": ["second_amount_to_remaining"],
    "state_effect": ["churn_effect"],
}
OUTCOME_ASPECT = {"outcome": ["outcome"]}
ALL_ASPECTS = {
    **QUEUE_ASPECT,
    **VALIDATOR_ASPECT,
    **DEPOSIT_ASPECT,
    **CHURN_ASPECT,
    **OUTCOME_ASPECT,
}
MODEL = Path(__file__).parent / "models" / "handler_pending_deposits.mzn"


def _recs():
    return enumerate_signatures(MODEL, _DIMS, ALL_ASPECTS)


def build_profile(records, name: str):
    if name not in {"onewise", "pairwise", "standard"}:
        raise ValueError(f"unknown profile: {name}")
    strength = {"onewise": 1, "pairwise": 2, "standard": 3}[name]
    return cover(records, ALL_ASPECTS, strength)


def materialize_profile(name: str) -> int:
    _, chosen = build_profile(_recs(), name)
    return PendingDepositsMaterializer(spec).materialize_reps(
        Path(__file__).parent / "reftests", [SimpleNamespace(**record) for record in chosen]
    )


def main() -> int:
    args = [arg for arg in sys.argv[1:] if not arg.startswith("--")]
    materialize = "--materialize" in sys.argv
    records = _recs()
    print(f"distinct aspect-state signatures: {len(records)}\n")
    if not args:
        print(f"{'profile':10} {'obligations':>12} {'cases':>7}")
        for name in ("onewise", "pairwise", "standard"):
            obligations, cases = build_profile(records, name)
            print(f"{name:10} {obligations:>12} {len(cases):>7}")
        return 0
    obligations, cases = build_profile(records, args[0])
    print(f"profile '{args[0]}': {len(cases)} cases covering {obligations} obligations")
    if materialize:
        materialize_profile(args[0])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
