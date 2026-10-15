"""Provider for the per-validator effective-balance-update loop body."""

from eth_consensus_specs.gloas import minimal as spec
from tests.generators.compliance_runners.state_transition.declaration_coverage import (
    coverage_profiles,
)
from tests.generators.compliance_runners.state_transition.declaration_validation import (
    target_validator,
)

from .materializer import EffectiveBalanceUpdatesBodyMaterializer
from .target import TARGET

MATERIALIZER = EffectiveBalanceUpdatesBodyMaterializer
build_profile = coverage_profiles(TARGET)
recover_dimensions, validate_case = target_validator(TARGET, spec=lambda: spec)

__all__ = (
    "MATERIALIZER",
    "TARGET",
    "build_profile",
    "recover_dimensions",
    "validate_case",
)
