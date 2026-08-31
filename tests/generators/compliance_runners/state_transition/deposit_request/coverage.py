"""Coverage profiles for process_deposit_request.

This handler has no faults, so its exceptional profile is empty. `normal` and
`standard` provide pairwise coverage over its input-shape dimensions.

Run:
    uv run python -m ...deposit_request.coverage
    uv run python -m ...deposit_request.coverage standard --materialize
"""

from __future__ import annotations

from pathlib import Path

from tests.generators.compliance_runners.state_transition.aspect_coverage import (
    build_profile as _build_profile,
    enumerate_signatures,
)

from .materializer import _DIMS

INPUT_ASPECTS = {
    "deposit_amount": ["amount_profile", "amount_nonzero"],
    "withdrawal_credentials": ["withdrawal_credentials_profile"],
    "signature": ["signature_profile"],
    "deposit_pubkey": ["pubkey_is_existing_validator"],
}
ALL_ASPECTS = INPUT_ASPECTS
MODEL = Path(__file__).parent / "models" / "handler_deposit_request.mzn"


def _nfaults(_r: dict) -> int:
    return 0  # no failing gates in this handler


def build_profile(name):
    return _build_profile(_recs(), name, ALL_ASPECTS, ALL_ASPECTS, {"outcome": ["outcome"]})


def _recs():
    return enumerate_signatures(MODEL, _DIMS, ALL_ASPECTS, _nfaults)
