"""Aspect-based compliance generator for ``process_pending_consolidations``."""

from .coverage import build_profile
from .materializer import PendingConsolidationsMaterializer
from .validation import validate_case

MATERIALIZER = PendingConsolidationsMaterializer

__all__ = ("MATERIALIZER", "build_profile", "validate_case")
