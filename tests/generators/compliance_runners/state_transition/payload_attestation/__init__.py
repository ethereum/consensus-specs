"""Aspect-based compliance runner for Gloas payload attestations."""

from .coverage import build_profile
from .materializer import PayloadAttestationMaterializer
from .validation import validate_case

MATERIALIZER = PayloadAttestationMaterializer

__all__ = ("MATERIALIZER", "build_profile", "validate_case")
