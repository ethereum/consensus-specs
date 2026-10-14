"""DSL coverage profiles and concrete witnesses for effective-balance updates."""

from __future__ import annotations

from tests.generators.compliance_runners.state_transition.declaration_coverage import (
    coverage_profiles,
)

from .cases import candidate_records, constants
from .target import COMPARISONS, TARGET

build_profile = coverage_profiles(
    TARGET,
    candidates=lambda spec: candidate_records(constants(spec), COMPARISONS),
)


__all__ = ("TARGET", "build_profile")
