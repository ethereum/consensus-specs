"""Declaration-based provider for Gloas ``process_ptc_window``."""

from eth_consensus_specs.gloas import minimal as spec
from tests.generators.compliance_runners.state_transition.declaration_coverage import (
    coverage_profiles,
)
from tests.generators.compliance_runners.state_transition.declaration_validation import (
    target_validator,
)

from .materializer import PtcWindowMaterializer as MATERIALIZER
from .target import TARGET

build_profile = coverage_profiles(TARGET)
recover, validate_case = target_validator(TARGET, spec=lambda: spec, require_post=True)

__all__ = ("MATERIALIZER", "TARGET", "build_profile", "recover", "validate_case")
