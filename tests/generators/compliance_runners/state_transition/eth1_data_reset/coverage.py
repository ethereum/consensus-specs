"""Coverage profiles for ``process_eth1_data_reset``."""

from __future__ import annotations

from .target import PROFILES, TARGET


def build_profile(name: str):
    """Return predicate-level DSL obligations in provider format."""
    formula = PROFILES["standard" if name == "all" else name]
    obligations = formula.run("predicate")
    records = [dict(obligation) for obligation in sorted(obligations, key=repr)]
    return records, records


__all__ = ("TARGET", "build_profile")
