"""Validate proposer-slashing vectors through the declaration target."""

from eth_consensus_specs.gloas import minimal as spec
from tests.generators.compliance_runners.state_transition.declaration_validation import (
    target_validator,
)

from .target import TARGET

recover, validate_case = target_validator(
    TARGET, operation_name="proposer_slashing", operation_type="ProposerSlashing", spec=lambda: spec
)
