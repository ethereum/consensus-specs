"""Coverage profiles for ``process_operations``.

The target is expressed in the declaration DSL. At generation time
we use its predicate-level obligations as compact, executable solutions.
"""

from __future__ import annotations

from tests.generators.compliance_runners.state_transition.declaration_coverage import (
    coverage_profiles,
)

from .target import TARGET
from .witness import complete_obligation

build_profile = coverage_profiles(TARGET, witness=complete_obligation)


__all__ = ("TARGET", "build_profile")
