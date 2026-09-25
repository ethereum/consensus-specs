"""Coverage profiles for ``process_randao_mixes_reset``."""

from __future__ import annotations

from .target import TARGET


def build_profile(name: str, *, spec):
    target = TARGET.for_spec(spec)
    formula = target.profiles[name]
    obligations = formula.run("predicate")
    records = [dict(obligation) for obligation in sorted(obligations, key=repr)]
    return records, records


__all__ = ("TARGET", "build_profile")
