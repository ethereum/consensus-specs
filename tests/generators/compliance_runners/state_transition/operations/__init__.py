"""DSL-based compliance generator for Gloas ``process_operations``."""

from eth_consensus_specs.gloas import minimal as spec
from tests.generators.compliance_runners.state_transition.declaration_coverage import (
    coverage_profiles,
)
from tests.generators.compliance_runners.state_transition.declaration_validation import (
    target_validator,
)

from .materializer import MATERIALIZER
from .target import TARGET
from .witness import complete_obligation

build_profile = coverage_profiles(TARGET, witness=complete_obligation)
recover_dimensions, validate_case = target_validator(
    TARGET,
    operation_name="blocks_0",
    operation_type="SignedBeaconBlock",
    spec=lambda: spec,
)

__all__ = ("MATERIALIZER", "build_profile", "recover_dimensions", "validate_case")
