"""Coverage profiles for ``process_participation_flag_updates``."""

from tests.generators.compliance_runners.state_transition.declaration_coverage import (
    coverage_profiles,
)

from .target import TARGET

build_profile = coverage_profiles(TARGET, empty_profiles=("exceptional",))

__all__ = ("TARGET", "build_profile")
