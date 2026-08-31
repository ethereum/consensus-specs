"""Coverage profiles for Gloas ``process_proposer_slashing``."""

from __future__ import annotations

from pathlib import Path

from tests.generators.compliance_runners.state_transition.aspect_coverage import (
    build_profile as _build_profile,
    enumerate_signatures,
)

from .materializer import _DIMS

INPUT_ASPECTS = {
    "headers": ["slots_match", "proposers_match", "headers_different"],
    "proposer_slashability": [
        "proposer_slashed",
        "proposer_activated",
        "proposer_withdrawable",
        "proposer_exited",
    ],
    "signatures": ["signature_1_valid", "signature_2_valid"],
    "pending_payment": ["payment_window", "payment_proposer_matches"],
}
OUTCOME_ASPECT = {"outcome": ["outcome", "pending_payment_cleared", "state_effected"]}
ALL_ASPECTS = {**INPUT_ASPECTS, **OUTCOME_ASPECT}
MODEL = Path(__file__).parent / "models" / "handler_proposer_slashing.mzn"


def _nfaults(r: dict) -> int:
    return (
        int(not r["slots_match"])
        + int(not r["proposers_match"])
        + int(not r["headers_different"])
        + int(r["proposer_slashed"])
        + int(not r["proposer_activated"])
        + int(r["proposer_withdrawable"])
        + int(r["signature_1_valid"] != "T")
        + int(r["signature_2_valid"] != "T")
    )


def _recs():
    return enumerate_signatures(MODEL, _DIMS, ALL_ASPECTS, _nfaults)


def build_profile(name):
    return _build_profile(_recs(), name, ALL_ASPECTS, INPUT_ASPECTS, OUTCOME_ASPECT)
