"""Coverage profiles for Gloas ``process_pending_consolidations``."""

from __future__ import annotations

from pathlib import Path

from tests.generators.compliance_runners.state_transition.aspect_coverage import (
    build_profile as _build_profile,
    enumerate_signatures,
)

from .materializer import _DIMS

MODEL = Path(__file__).parent / "models" / "handler_pending_consolidations.mzn"
ASPECTS = {
    "queue": ["queue_layout"],
    "transfer": ["source_balance_to_effective"],
    "outcome": ["outcome"],
}


def _recs():
    return enumerate_signatures(MODEL, _DIMS, ASPECTS, _nfaults)


def _nfaults(_record: dict) -> int:
    # This handler deliberately skips or retains entries; neither is an invalid
    # input, so every feasible case is a normal case.
    return 0


def build_profile(name: str):
    return _build_profile(_recs(), name, ASPECTS, ASPECTS, {"outcome": ["outcome"]})
