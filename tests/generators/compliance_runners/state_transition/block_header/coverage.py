"""Coverage profiles for Gloas ``process_block_header``."""

from __future__ import annotations

from .target import TARGET


def build_profile(name: str, *, spec) -> tuple[int, list[dict]]:
    """Expand a DSL profile into operation representatives at the declared granularities."""
    target = TARGET.for_spec(spec)
    formula = target.profiles[name]
    obligations = formula.run()
    records = [dict(sorted(obligation)) for obligation in sorted(obligations, key=repr)]
    return len(records), records
