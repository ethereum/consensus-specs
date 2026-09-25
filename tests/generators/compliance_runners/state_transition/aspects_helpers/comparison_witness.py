"""Concrete numeric witnesses for comparison-profile dimensions."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from random import Random


def value_for_comparison(
    rng: Random, relation: str, threshold: int, *, lower_bound: int = 0
) -> int:
    """Return a value satisfying ``value <|=|> threshold``."""
    if relation == "LT":
        if threshold <= lower_bound:
            raise ValueError("LT witness has no value within the requested bounds")
        return rng.randrange(lower_bound, threshold)
    if relation == "EQ":
        return threshold
    if relation == "GT":
        return threshold + rng.randrange(1, max(2, threshold + 1))
    raise ValueError(f"Unknown comparison relation: {relation}")
