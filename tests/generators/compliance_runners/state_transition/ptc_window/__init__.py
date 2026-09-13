"""Compliance generator for Gloas ``process_ptc_window``."""

from .coverage import build_profile
from .materializer import PtcWindowMaterializer
from .validation import validate_case

MATERIALIZER = PtcWindowMaterializer

__all__ = ("MATERIALIZER", "build_profile", "validate_case")
