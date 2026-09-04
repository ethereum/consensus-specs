"""Provider for builder pending-withdrawal processing cases."""

from . import validation
from .coverage import (
    _build_profile,
    _normalize_pending_withdrawal,
    PENDING_ASPECTS,
    PENDING_MODEL,
)
from .materializer import WithdrawalProcessingMaterializer

MATERIALIZER = WithdrawalProcessingMaterializer
validate_case = validation.validate_case


def build_profile(name: str) -> tuple[int, list[dict]]:
    records = _build_profile(PENDING_MODEL, _normalize_pending_withdrawal, PENDING_ASPECTS, name)
    return len(records), records
