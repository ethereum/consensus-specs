"""Declaration-based provider for Gloas ``process_block_header``."""

from eth_consensus_specs.gloas import minimal as spec
from tests.generators.compliance_runners.state_transition.declaration_coverage import (
    coverage_profiles,
)
from tests.generators.compliance_runners.state_transition.declaration_validation import (
    target_validator,
)

from .materializer import BlockHeaderMaterializer
from .target import TARGET

MATERIALIZER = BlockHeaderMaterializer
build_profile = coverage_profiles(TARGET)
recover, validate_case = target_validator(
    TARGET,
    operation_name="block_header",
    operation_type="BeaconBlock",
    spec=lambda: spec,
)

__all__ = ("MATERIALIZER", "TARGET", "build_profile", "recover", "validate_case")
