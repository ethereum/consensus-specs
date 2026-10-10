"""Materialize and evaluate Gloas ``process_slot`` sanity/slots vectors."""

from .coverage import build_profile
from .materializer import MATERIALIZER
from .validation import validate_case

__all__ = ("MATERIALIZER", "build_profile", "validate_case")
