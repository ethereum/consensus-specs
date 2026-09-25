"""Coverage profiles for Gloas ``process_block_header``."""

from __future__ import annotations

from .target import TARGET


def build_profile(name: str, *, spec) -> tuple[int, list[dict]]:
    """Expand a DSL profile into predicate-level operation representatives."""
    target = TARGET.for_spec(spec)
    formula = target.profiles[name]
    obligations = formula.run("predicate")
    records = [dict(sorted(obligation)) for obligation in sorted(obligations, key=repr)]
    return len(records), records
