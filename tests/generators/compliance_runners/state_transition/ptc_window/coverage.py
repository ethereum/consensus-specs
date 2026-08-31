from __future__ import annotations

from pathlib import Path

from tests.generators.compliance_runners.state_transition.aspect_coverage import (
    build_profile as _build_profile,
    enumerate_signatures,
)

from .materializer import _DIMS

MODEL = Path(__file__).parent / "models" / "handler_ptc_window.mzn"
ASPECTS = {
    "epoch_context": ["epoch_position"],
    "state": ["validator_count", "validator_balance", "validator_activity"],
}


def _recs():
    return enumerate_signatures(MODEL, _DIMS, ASPECTS, _nfaults)


def _nfaults(_r: dict) -> int:
    return 0


def build_profile(name):
    return _build_profile(_recs(), name, ASPECTS, ASPECTS, {"outcome": ["outcome"]})
