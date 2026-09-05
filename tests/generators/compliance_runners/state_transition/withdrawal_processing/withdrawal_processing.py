"""Provider for aggregate withdrawal-processing cases."""

from . import validation
from .coverage import (
    _build_profile,
    _flatten_withdrawal_processing,
    WITHDRAWAL_PROCESSING_ASPECTS,
    WITHDRAWAL_PROCESSING_MODEL,
)
from .materializer import WithdrawalProcessingMaterializer

MATERIALIZER = WithdrawalProcessingMaterializer
validate_case = validation.validate_case


def build_profile(name: str) -> tuple[int, list[dict]]:
    records = _build_profile(
        WITHDRAWAL_PROCESSING_MODEL,
        _flatten_withdrawal_processing,
        WITHDRAWAL_PROCESSING_ASPECTS,
        name,
    )
    return len(records), records
