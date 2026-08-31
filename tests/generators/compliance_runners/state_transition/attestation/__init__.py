"""Aspect-based compliance runner for Gloas attestations."""

from .coverage import build_profile
from .materializer import AttestationMaterializer
from .validation import validate_case

MATERIALIZER = AttestationMaterializer

__all__ = ("MATERIALIZER", "build_profile", "validate_case")
