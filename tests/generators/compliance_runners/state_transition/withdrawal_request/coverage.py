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
from types import SimpleNamespace

from ..aspect_coverage import build_profile as _build_profile, enumerate_signatures
from .materializer import _DIMS, WithdrawalRequestMaterializer

# Fine-grained input aspects remain part of the signature used by `all`; the
# normal/exceptional profiles use the composite validator_state factor.
FINE_INPUT_ASPECTS = {
    "withdrawal_amount": ["is_full_exit_request"],
    "partial_queue_capacity": ["partial_queue_full"],
    "validator_membership": ["validator_pubkey_found"],
    "validator_credential": ["validator_credential"],
    "source_authorization": ["source_address_matches"],
    "validator_lifecycle": ["validator_active", "validator_exiting", "validator_old_enough"],
    "validator_pending_withdrawal": ["has_pending_partial_withdrawal"],
    "validator_balance": ["sufficient_effective_balance", "has_excess_balance"],
}
OUTCOME_ASPECT = {"outcome": ["outcome"]}
INPUT_ASPECTS = {
    "withdrawal_amount": ["is_full_exit_request"],
    "partial_queue_capacity": ["partial_queue_full"],
    "validator_state": [
        "validator_pubkey_found",
        "validator_credential",
        "source_address_matches",
        "validator_active",
        "validator_exiting",
        "validator_old_enough",
        "has_pending_partial_withdrawal",
        "sufficient_effective_balance",
        "has_excess_balance",
    ],
}
FINE_ALL_ASPECTS = {**FINE_INPUT_ASPECTS, **OUTCOME_ASPECT}
ALL_ASPECTS = {**INPUT_ASPECTS, **OUTCOME_ASPECT}
MODEL = Path(__file__).parent / "models" / "handler_withdrawal_request.mzn"


def _nfaults(r: dict) -> int:
    faults = int(r["partial_queue_full"] and not r["is_full_exit_request"])
    faults += int(not r["validator_pubkey_found"])
    if r["validator_pubkey_found"]:
        faults += int(
            not (r["validator_has_execution_credential"] and r["source_address_matches"] == "T")
        )
        faults += int(r["validator_active"] != "T")
        faults += int(r["validator_exiting"] != "F")
        faults += int(r["validator_old_enough"] != "T")
    return faults


def build_profile(recs, name):
    return _build_profile(recs, name, ALL_ASPECTS, INPUT_ASPECTS, OUTCOME_ASPECT)


def _recs():
    return enumerate_signatures(MODEL, _DIMS, FINE_ALL_ASPECTS, _nfaults)


def materialize_profile(name: str, output_dir: Path | None = None) -> int:
    from eth_consensus_specs.gloas import minimal as spec

    _, chosen = build_profile(_recs(), name)
    reps = [SimpleNamespace(**r) for r in chosen]
    out = output_dir or (Path(__file__).parent / "reftests")
    return WithdrawalRequestMaterializer(spec, MODEL).materialize_reps(out, reps)
