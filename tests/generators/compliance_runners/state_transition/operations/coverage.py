"""Coverage profiles for ``process_operations``.

The target is deliberately expressed in the capture DSL.  At generation time
we use its predicate-level obligations as compact, executable solutions.
"""

from __future__ import annotations

from .target import TARGET
from .witness import complete_obligation


def build_profile(name: str, *, spec):
    """Complete partial obligations and keep one case per realized witness."""
    target = TARGET.for_spec(spec)
    formula = target.profiles[name]
    obligations = formula.run("predicate")
    records = [dict(obligation) for obligation in sorted(obligations, key=repr)]
    chosen_by_signature = {}
    for record in records:
        witness = complete_obligation(record)
        chosen_by_signature.setdefault(tuple(witness.items()), witness)
    return records, list(chosen_by_signature.values())


__all__ = ("TARGET", "build_profile")
