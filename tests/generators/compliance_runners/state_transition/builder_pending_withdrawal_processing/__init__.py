"""Declaration provider for the single pending builder-withdrawal slice."""

from eth_consensus_specs.gloas import minimal as spec
from tests.generators.compliance_runners.state_transition.declaration_coverage import (
    coverage_profiles,
)
from tests.generators.compliance_runners.state_transition.declaration_validation import (
    target_validator,
)

from .target import TARGET

build_profile = coverage_profiles(TARGET, backend="python")
recover, validate_case = target_validator(TARGET, spec=lambda: spec, require_post=True)


def MATERIALIZER(spec, **kwargs):
    # Defer the shared aggregate import: its coverage and validation route back here.
    from tests.generators.compliance_runners.state_transition.withdrawal_processing.materializer import (  # noqa: PLC0415
        WithdrawalProcessingMaterializer,
    )

    return WithdrawalProcessingMaterializer(spec, **kwargs)


__all__ = ("MATERIALIZER", "TARGET", "build_profile", "recover", "validate_case")
