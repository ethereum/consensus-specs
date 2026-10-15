"""MiniZinc-backed declaration-based provider for proposer slashings."""

from eth_consensus_specs.gloas import minimal as spec
from tests.generators.compliance_runners.state_transition.declaration_coverage import (
    coverage_profiles,
)
from tests.generators.compliance_runners.state_transition.declaration_validation import (
    target_validator,
)

from .materializer import ProposerSlashingMaterializer
from .target import TARGET

MATERIALIZER = ProposerSlashingMaterializer
build_profile = coverage_profiles(TARGET, backend="minizinc")
recover, validate_case = target_validator(
    TARGET,
    operation_name="proposer_slashing",
    operation_type="ProposerSlashing",
    spec=lambda: spec,
)

__all__ = ("MATERIALIZER", "TARGET", "build_profile", "recover", "validate_case")
