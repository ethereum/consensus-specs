"""MiniZinc-backed declaration-based provider for voluntary exits."""

from eth_consensus_specs.gloas import minimal as spec
from tests.generators.compliance_runners.state_transition.declaration_coverage import (
    coverage_profiles,
)
from tests.generators.compliance_runners.state_transition.declaration_validation import (
    target_validator,
)

from .materializer import VoluntaryExitMaterializer
from .target import TARGET

MATERIALIZER = VoluntaryExitMaterializer
build_profile = coverage_profiles(TARGET)
recover_dimensions, validate_case = target_validator(
    TARGET,
    operation_name="voluntary_exit",
    operation_type="SignedVoluntaryExit",
    spec=lambda: spec,
)

__all__ = ("MATERIALIZER", "TARGET", "build_profile", "recover_dimensions", "validate_case")
