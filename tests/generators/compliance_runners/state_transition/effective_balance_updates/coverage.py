"""DSL coverage profiles and concrete witnesses for effective-balance updates."""

from __future__ import annotations

from .cases import constants, representatives
from .target import COMPARISONS, TARGET


def build_profile(name: str, *, spec):
    if name == "exceptional":
        return [], []
    target = TARGET.for_spec(spec)
    obligations = target.profiles[name].run()
    candidates = representatives(constants(spec), COMPARISONS)
    records = []
    for obligation in sorted(obligations, key=repr):
        matching = [key for key in candidates if obligation <= frozenset(key)]
        if not matching:
            raise ValueError(f"no concrete witness for {dict(obligation)}")
        key = min(matching, key=repr)
        _, effective, balance = candidates[key]
        records.append(
            {
                **dict(key),
                "effective_balance": effective,
                "balance": balance,
            }
        )
    records = list({tuple(sorted(record.items())): record for record in records}.values())
    return records, records


__all__ = ("TARGET", "build_profile")
