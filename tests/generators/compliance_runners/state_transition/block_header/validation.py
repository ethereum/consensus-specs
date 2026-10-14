"""Validate block-header vectors through the declaration target."""

from eth_consensus_specs.gloas import minimal as spec
from tests.generators.compliance_runners.state_transition.declaration_validation import (
    target_validator,
)

from .target import TARGET

recover, validate_case = target_validator(
    TARGET,
    operation_name="block_header",
    operation_type="BeaconBlock",
    spec=lambda: spec,
)
