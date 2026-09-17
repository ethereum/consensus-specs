"""Aspect-based compliance generator for ``process_sync_aggregate``."""

from .coverage import build_profile
from .materializer import SyncAggregateMaterializer
from .validation import validate_case

MATERIALIZER = SyncAggregateMaterializer

__all__ = ("MATERIALIZER", "build_profile", "validate_case")
