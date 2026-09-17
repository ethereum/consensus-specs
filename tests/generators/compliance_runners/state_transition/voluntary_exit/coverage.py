"""Coverage profiles for Gloas ``process_voluntary_exit``."""

from __future__ import annotations

from pathlib import Path

from tests.generators.compliance_runners.state_transition.aspect_coverage import (
    build_profile as _build_profile,
    enumerate_signatures,
)

from .materializer import _DIMS

MODEL = Path(__file__).parent / "models" / "handler_voluntary_exit.mzn"
ASPECTS = {
    "activity": ["validator_active", "exit_not_initiated"],
    "epoch": ["exit_epoch_valid", "active_long_enough"],
    "exit_churn": ["exit_churn_state"],
    "withdrawals": ["no_pending_withdrawal"],
    "signature": ["signature_valid"],
    "outcome": ["outcome"],
}


def _nfaults(record: dict) -> int:
    return int(record["outcome"] != "ACCEPT")


def _recs():
    return enumerate_signatures(MODEL, _DIMS, ASPECTS, _nfaults)


def build_profile(name: str):
    return _build_profile(_recs(), name, ASPECTS, ASPECTS, {"outcome": ["outcome"]})
