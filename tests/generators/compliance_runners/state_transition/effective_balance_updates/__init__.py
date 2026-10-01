"""Provider for the per-validator effective-balance-update loop body."""

from .coverage import build_profile
from .materializer import EffectiveBalanceUpdatesBodyMaterializer
from .validation import validate_case

MATERIALIZER = EffectiveBalanceUpdatesBodyMaterializer

__all__ = ("MATERIALIZER", "build_profile", "validate_case")
