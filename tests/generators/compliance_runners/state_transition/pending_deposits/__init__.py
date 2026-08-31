"""Aspect-based compliance generator for ``process_pending_deposits``."""
from .coverage import build_profile
from .materializer import PendingDepositsMaterializer
from .validation import validate_case

MATERIALIZER = PendingDepositsMaterializer

__all__ = ("MATERIALIZER", "build_profile", "validate_case")
