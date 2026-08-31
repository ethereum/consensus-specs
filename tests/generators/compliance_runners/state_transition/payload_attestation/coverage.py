"""Coverage profiles for Gloas ``process_payload_attestation``."""

from __future__ import annotations

from pathlib import Path

from tests.generators.compliance_runners.state_transition.aspect_coverage import (
    build_profile as _build_profile,
    enumerate_signatures,
)

from .materializer import _DIMS

INPUT_ASPECTS = {
    "block_context": ["parent_root_matches", "slot_is_previous"],
    "participants": ["attesting_indices_profile", "attesting_indices_nonempty", "signature_valid"],
}
OUTCOME_ASPECT = {"outcome": ["outcome"]}
ALL_ASPECTS = {**INPUT_ASPECTS, **OUTCOME_ASPECT}
MODEL = Path(__file__).parent / "models" / "handler_payload_attestation.mzn"


def _nfaults(r: dict) -> int:
    return (
        int(not r["parent_root_matches"])
        + int(not r["slot_is_previous"])
        + int(not r["attesting_indices_nonempty"])
        + int(r["signature_valid"] == "F")
    )


def _recs():
    return enumerate_signatures(MODEL, _DIMS, ALL_ASPECTS, _nfaults)


def build_profile(name):
    return _build_profile(_recs(), name, ALL_ASPECTS, INPUT_ASPECTS, OUTCOME_ASPECT)
