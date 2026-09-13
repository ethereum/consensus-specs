"""Aspect-based compliance runner for Gloas proposer slashings."""

from .coverage import build_profile
from .materializer import ProposerSlashingMaterializer
from .validation import validate_case

MATERIALIZER = ProposerSlashingMaterializer

__all__ = ("MATERIALIZER", "build_profile", "validate_case")
