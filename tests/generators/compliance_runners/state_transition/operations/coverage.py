"""Coverage profiles for ``process_operations``.

The target is deliberately expressed in the capture DSL.  At generation time
we use its predicate-level obligations as compact, executable solutions.
"""

from __future__ import annotations

from .target import PROFILES, TARGET


def build_profile(name: str):
    """Return DSL obligations in the provider's ``(all, chosen)`` shape."""
    formula = PROFILES["standard" if name == "all" else name]
    obligations = formula.run("predicate")
    records = [dict(obligation) for obligation in sorted(obligations, key=repr)]
    return records, records


__all__ = ("TARGET", "build_profile")
