"""MiniZinc-backed declaration profiles for payload attestations."""

from tests.generators.compliance_runners.state_transition.declaration_coverage import (
    coverage_profiles,
)

from .target import TARGET

build_profile = coverage_profiles(TARGET, backend="minizinc", materializer=True)

__all__ = ("TARGET", "build_profile")
