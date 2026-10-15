"""Provider for aggregate withdrawal-processing cases."""

from . import validation
from .coverage import (
    _build_profile,
    _flatten_withdrawal_processing,
    get_solution_catalog,
    WITHDRAWAL_PROCESSING_ASPECTS,
    WITHDRAWAL_PROCESSING_MODEL,
)
from .materializer import WithdrawalProcessingMaterializer


def MATERIALIZER(spec, **kwargs):
    return WithdrawalProcessingMaterializer(spec, get_solution_catalog(), **kwargs)


validate_case = validation.validate_case


def build_profile(name: str) -> list[dict]:
    return _build_profile(
        WITHDRAWAL_PROCESSING_MODEL,
        _flatten_withdrawal_processing,
        WITHDRAWAL_PROCESSING_ASPECTS,
        name,
    )
