"""Coverage profiles for process_consolidation_request.

Handler-specific instantiation of the shared ``..aspect_coverage`` engine.
Reuses the validator family for the SOURCE validator + source_authorization, and
a compact target_validator aspect for the target.

Run:
    uv run python -m ...consolidation_request.coverage
    uv run python -m ...consolidation_request.coverage standard --materialize
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from eth_consensus_specs.gloas import minimal as spec
from tests.generators.compliance_runners.state_transition.aspect_coverage import (
    build_profile as _build_profile,
    enumerate_signatures,
)

from .materializer import _DIMS, ConsolidationRequestMaterializer

# Fine-grained input aspects remain part of the signature used by `all`; the
# normal/exceptional profiles use the composite validator_state factor.
FINE_INPUT_ASPECTS = {
    "consolidation_pair": ["same_source_target"],
    "pending_consolidations_capacity": ["pending_consolidations_full"],
    "consolidation_churn": ["sufficient_consolidation_churn"],
    "validator_membership": ["validator_pubkey_found"],
    "validator_credential": ["validator_credential"],
    "source_authorization": ["source_address_matches"],
    "validator_lifecycle": ["validator_active", "validator_exiting", "validator_old_enough"],
    "validator_pending_withdrawal": ["has_pending_partial_withdrawal"],
    "target_validator": ["target_found", "target_credential", "target_active", "target_exiting"],
}
OUTCOME_ASPECT = {"outcome": ["outcome"]}
INPUT_ASPECTS = {
    "consolidation_pair": ["same_source_target"],
    "pending_consolidations_capacity": ["pending_consolidations_full"],
    "consolidation_churn": ["sufficient_consolidation_churn"],
    "validator_state": [
        "validator_pubkey_found",
        "validator_credential",
        "source_address_matches",
        "validator_active",
        "validator_exiting",
        "validator_old_enough",
        "has_pending_partial_withdrawal",
        "target_found",
        "target_credential",
        "target_active",
        "target_exiting",
    ],
}
FINE_ALL_ASPECTS = {**FINE_INPUT_ASPECTS, **OUTCOME_ASPECT}
ALL_ASPECTS = {**INPUT_ASPECTS, **OUTCOME_ASPECT}
MODEL = Path(__file__).parent / "models" / "handler_consolidation_request.mzn"


def _nfaults(r: dict) -> int:
    if r["same_source_target"]:
        if not r["validator_pubkey_found"]:
            return 1
        return sum(
            (
                r["source_address_matches"] != "T",
                r["validator_credential"] != "CRED_ETH1",
                r["validator_active"] != "T",
                r["validator_exiting"] == "T",
            )
        )

    faults = int(r["pending_consolidations_full"]) + int(not r["sufficient_consolidation_churn"])
    faults += int(not r["validator_pubkey_found"])
    faults += int(r["target_found"] != "T")
    if r["validator_pubkey_found"]:
        faults += int(
            not (r["validator_has_execution_credential"] and r["source_address_matches"] == "T")
        )
        faults += int(r["validator_active"] != "T")
        faults += int(r["validator_exiting"] == "T")
        faults += int(r["validator_old_enough"] != "T")
        faults += int(r["has_pending_partial_withdrawal"] == "T")
    faults += int(r["target_active"] != "T") if r["target_found"] == "T" else 0
    faults += int(r["target_exiting"] == "T") if r["target_found"] == "T" else 0
    faults += int(not r["target_has_compounding_credential"]) if r["target_found"] == "T" else 0
    return faults


def build_profile(recs, name):
    return _build_profile(recs, name, ALL_ASPECTS, INPUT_ASPECTS, OUTCOME_ASPECT)


def _recs():
    return enumerate_signatures(MODEL, _DIMS, FINE_ALL_ASPECTS, _nfaults)


def materialize_profile(name: str, output_dir: Path | None = None) -> int:
    _, chosen = build_profile(_recs(), name)
    reps = [SimpleNamespace(**r) for r in chosen]
    out = output_dir or (Path(__file__).parent / "reftests")
    return ConsolidationRequestMaterializer(spec, MODEL).materialize_reps(out, reps)
