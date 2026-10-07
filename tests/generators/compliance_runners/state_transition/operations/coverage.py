"""Coverage profiles for ``process_operations``.

The target is expressed in the declaration DSL. At generation time
we use its predicate-level obligations as compact, executable solutions.
"""

from __future__ import annotations

from tests.generators.compliance_runners.state_transition.declaration_coverage import (
    profile_records,
)

from .target import TARGET
from .witness import complete_obligation


def build_profile(name: str, *, spec):
    """Complete partial obligations and keep one case per realized witness."""
    target = TARGET.for_spec(spec)
    records = profile_records(target, name)
    chosen_by_signature = {}
    for record in records:
        witness = complete_obligation(record)
        chosen_by_signature.setdefault(tuple(witness.items()), witness)
    return records, list(chosen_by_signature.values())


__all__ = ("TARGET", "build_profile")
