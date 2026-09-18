"""Aspect-based compliance generator for ``process_slashings``."""

from .coverage import build_profile
from .materializer import SlashingsMaterializer
from .validation import validate_case

MATERIALIZER = SlashingsMaterializer

__all__ = ("MATERIALIZER", "build_profile", "validate_case")
