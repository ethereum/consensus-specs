"""Declaration profiles with complete, fault-scoped proposer-slashing witnesses."""

from tests.generators.compliance_runners.state_transition.declaration_coverage import (
    coverage_profiles,
)

from .target import TARGET
from .witness import materializer_record

build_profile = coverage_profiles(TARGET, complete=True, witness=materializer_record)


__all__ = ("TARGET", "build_profile")
