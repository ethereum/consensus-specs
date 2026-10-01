"""Coverage profiles for Gloas ``process_sync_aggregate``."""

from __future__ import annotations

from pathlib import Path

from tests.generators.compliance_runners.state_transition.aspect_coverage import (
    build_profile as _build_profile,
    enumerate_signatures,
)

from .materializer import _DIMS

MODEL = Path(__file__).parent / "models" / "handler_sync_aggregate.mzn"
ASPECTS = {
    "participants": ["participation_level"],
    "signature": ["signature_valid"],
    "outcome": ["outcome"],
}


def _nfaults(record: dict) -> int:
    return int(record["outcome"] != "ACCEPT")


def _recs():
    return enumerate_signatures(MODEL, _DIMS, ASPECTS, _nfaults)


def build_profile(name: str):
    return _build_profile(_recs(), name, ASPECTS, ASPECTS, {"outcome": ["outcome"]})
