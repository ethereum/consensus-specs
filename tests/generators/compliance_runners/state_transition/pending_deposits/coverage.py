"""Coverage profiles for Gloas ``process_pending_deposits``."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from eth_consensus_specs.gloas import minimal as spec
from tests.generators.compliance_runners.state_transition.aspect_coverage import (
    build_profile as _build_profile,
    enumerate_signatures,
)

from .materializer import _DIMS, PendingDepositsMaterializer

# Fine-grained aspects remain part of the signature used by `all`; the normal
# profile uses the composite validator_state factor.
FINE_QUEUE_ASPECT = {
    "queue_layout": ["queue_layout", "secondary_role"],
    "finalization_and_limit": ["primary_reached"],
}
FINE_VALIDATOR_ASPECT = {
    "validator_membership": ["validator_pubkey_found"],
    "validator_lifecycle": ["validator_active", "validator_exiting"],
    "withdrawable_boundary": ["withdrawable_epoch_to_next_epoch"],
}
FINE_DEPOSIT_ASPECT = {"deposit_signature": ["deposit_signature_valid"]}
FINE_CHURN_ASPECT = {
    "carried_churn": ["initial_churn"],
    "amount_to_available": ["primary_amount_to_available"],
    "second_amount_to_remaining": ["second_amount_to_remaining"],
    "state_effect": ["churn_effect"],
}
OUTCOME_ASPECT = {"outcome": ["outcome"]}
FINE_ALL_ASPECTS = {
    **FINE_QUEUE_ASPECT,
    **FINE_VALIDATOR_ASPECT,
    **FINE_DEPOSIT_ASPECT,
    **FINE_CHURN_ASPECT,
    **OUTCOME_ASPECT,
}
QUEUE_ASPECT = {
    "queue_layout": ["queue_layout", "secondary_role"],
    "finalization_and_limit": ["primary_reached"],
}
VALIDATOR_ASPECT = {
    "validator_state": [
        "validator_pubkey_found",
        "validator_active",
        "validator_exiting",
        "withdrawable_epoch_to_next_epoch",
    ],
}
DEPOSIT_ASPECT = {"deposit_signature": ["deposit_signature_valid"]}
CHURN_ASPECT = FINE_CHURN_ASPECT
ALL_ASPECTS = {
    **QUEUE_ASPECT,
    **VALIDATOR_ASPECT,
    **DEPOSIT_ASPECT,
    **CHURN_ASPECT,
    **OUTCOME_ASPECT,
}
MODEL = Path(__file__).parent / "models" / "handler_pending_deposits.mzn"


def _recs():
    return enumerate_signatures(MODEL, _DIMS, FINE_ALL_ASPECTS, _nfaults)


def _nfaults(_r: dict) -> int:
    return 0


def build_profile(records, name: str):
    return _build_profile(
        records, name, ALL_ASPECTS, ALL_ASPECTS, {"outcome": ["outcome"]}, normal_t=3
    )


def materialize_profile(name: str, output_dir: Path | None = None) -> int:
    _, chosen = build_profile(_recs(), name)
    return PendingDepositsMaterializer(spec).materialize_reps(
        output_dir or (Path(__file__).parent / "reftests"),
        [SimpleNamespace(**record) for record in chosen],
    )
