"""Coverage profiles for Gloas ``process_effective_balance_updates``."""

from __future__ import annotations

from pathlib import Path

from tests.generators.compliance_runners.state_transition.aspect_coverage import (
    build_profile as _build_profile,
    enumerate_signatures,
)

from .materializer import _DIMS

MODEL = Path(__file__).parent / "models" / "handler_effective_balance_updates.mzn"
ASPECTS = {
    "credential": ["credential_type"],
    "update": ["hysteresis_result", "balance_alignment"],
    "outcome": ["outcome"],
}


def _recs():
    return enumerate_signatures(MODEL, _DIMS, ASPECTS, lambda _record: 0)


def build_profile(name: str):
    return _build_profile(_recs(), name, ASPECTS, ASPECTS, {"outcome": ["outcome"]})
