"""Aspect-based compliance generator for ``process_attester_slashing``."""

from .coverage import build_profile
from .materializer import AttesterSlashingMaterializer
from .validation import validate_case

MATERIALIZER = AttesterSlashingMaterializer

__all__ = ("MATERIALIZER", "build_profile", "validate_case")
