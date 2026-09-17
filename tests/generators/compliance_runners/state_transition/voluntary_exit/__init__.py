"""Aspect-based compliance generator for ``process_voluntary_exit``."""

from .coverage import build_profile
from .materializer import VoluntaryExitMaterializer
from .validation import validate_case

MATERIALIZER = VoluntaryExitMaterializer

__all__ = ("MATERIALIZER", "build_profile", "validate_case")
