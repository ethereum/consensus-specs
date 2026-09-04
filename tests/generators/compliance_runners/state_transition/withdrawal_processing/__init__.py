"""Aspect-based compliance generator for Gloas ``process_withdrawals``."""

from .coverage import build_profile
from .materializer import WithdrawalProcessingMaterializer
from .validation import validate_case

MATERIALIZER = WithdrawalProcessingMaterializer

__all__ = ("MATERIALIZER", "build_profile", "validate_case")
