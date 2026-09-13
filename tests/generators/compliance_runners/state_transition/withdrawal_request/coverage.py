"""Coverage profiles for process_withdrawal_request.

Handler-specific instantiation of the shared ``..aspect_coverage`` engine. Uses
the validator aspect family (membership / credential / lifecycle / balance /
pending) and REUSES source_authorization (shared with builder_exit_request).

Run:
    uv run python -m ...withdrawal_request.coverage
    uv run python -m ...withdrawal_request.coverage standard --materialize
"""

from __future__ import annotations

from pathlib import Path

from tests.generators.compliance_runners.state_transition.aspect_coverage import (
    build_profile as _build_profile,
    enumerate_signatures,
)

from .materializer import _DIMS

# Fine-grained input aspects remain part of the signature used by `all`; the
# normal/exceptional profiles use the composite validator_state factor.
FINE_INPUT_ASPECTS = {
    "withdrawal_amount": ["is_full_exit_request"],
    "partial_queue_capacity": ["partial_queue_capacity"],
    "validator_membership": ["validator_pubkey_found"],
    "validator_credential": ["validator_credential"],
    "source_authorization": ["source_address_matches"],
    "validator_lifecycle": ["validator_active", "validator_exiting", "validator_old_enough"],
    "validator_pending_withdrawal": ["has_pending_partial_withdrawal"],
    "validator_balance": ["effective_balance_to_min_activation", "balance_to_required"],
    "queue_churn": ["churn_variant"],
}
OUTCOME_ASPECT = {"outcome": ["outcome"]}
INPUT_ASPECTS = {
    "withdrawal_amount": ["is_full_exit_request"],
    "partial_queue_capacity": ["partial_queue_capacity"],
    "queue_churn": ["churn_variant"],
    "validator_state": [
        "validator_pubkey_found",
        "validator_credential",
        "source_address_matches",
        "validator_active",
        "validator_exiting",
        "validator_old_enough",
        "has_pending_partial_withdrawal",
        "effective_balance_to_min_activation",
        "balance_to_required",
    ],
}
FINE_ALL_ASPECTS = {**FINE_INPUT_ASPECTS, **OUTCOME_ASPECT}
ALL_ASPECTS = {**INPUT_ASPECTS, **OUTCOME_ASPECT}
MODEL = Path(__file__).parent / "models" / "handler_withdrawal_request.mzn"


def _nfaults(r: dict) -> int:
    faults = int(r["partial_queue_capacity"] == "FULL" and not r["is_full_exit_request"])
    faults += int(not r["validator_pubkey_found"])
    if r["validator_pubkey_found"]:
        faults += int(
            not (r["validator_has_execution_credential"] and r["source_address_matches"] == "T")
        )
        faults += int(r["validator_active"] != "T")
        faults += int(r["validator_exiting"] != "F")
        faults += int(r["validator_old_enough"] != "T")
    return faults


def build_profile(name):
    return _build_profile(_recs(), name, ALL_ASPECTS, INPUT_ASPECTS, OUTCOME_ASPECT)


def _recs():
    return enumerate_signatures(MODEL, _DIMS, FINE_ALL_ASPECTS, _nfaults)
