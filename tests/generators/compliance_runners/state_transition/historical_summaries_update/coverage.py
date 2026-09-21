"""Coverage profiles for ``process_historical_summaries_update``."""

from __future__ import annotations

from .target import PROFILES, TARGET


def build_profile(name: str):
    formula = PROFILES["standard" if name == "all" else name]
    obligations = formula.run("predicate")
    records = [dict(obligation) for obligation in sorted(obligations, key=repr)]
    return records, records


__all__ = ("TARGET", "build_profile")
