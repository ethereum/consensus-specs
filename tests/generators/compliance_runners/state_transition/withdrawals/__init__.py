"""Aspect-based compliance generator for Gloas ``process_withdrawals``."""

from .coverage import build_profile
from .materializer import WithdrawalsMaterializer
from .validation import validate_case

MATERIALIZER = WithdrawalsMaterializer

__all__ = ("MATERIALIZER", "build_profile", "validate_case")
