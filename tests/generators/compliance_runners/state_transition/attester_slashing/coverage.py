"""Coverage profiles for Gloas ``process_attester_slashing``."""

from __future__ import annotations

from pathlib import Path

from tests.generators.compliance_runners.state_transition.aspect_coverage import (
    build_profile as _build_profile,
    enumerate_signatures,
)

from .materializer import _DIMS

MODEL = Path(__file__).parent / "models" / "handler_attester_slashing.mzn"
ASPECTS = {
    "slashability": ["attestation_data_slashable"],
    "attestation_1": ["attestation_1_indices_well_formed", "attestation_1_valid"],
    "attestation_2": ["attestation_2_valid"],
    "intersection": ["intersection_size", "slashable_intersection"],
    "outcome": ["outcome"],
}


def _nfaults(record: dict) -> int:
    return int(record["outcome"] != "ACCEPT")


def _recs():
    return enumerate_signatures(MODEL, _DIMS, ASPECTS, _nfaults)


def build_profile(name: str):
    return _build_profile(_recs(), name, ASPECTS, ASPECTS, {"outcome": ["outcome"]})
