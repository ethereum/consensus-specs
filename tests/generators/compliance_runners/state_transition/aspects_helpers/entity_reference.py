"""Concrete entity-reference witnesses for state-transition materializers."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from random import Random


def distinct_indices(
    rng: Random,
    upper_bound: int,
    count: int,
) -> tuple[int, ...]:
    """Return distinct indices from the requested range."""
    if not 0 <= count <= upper_bound:
        raise ValueError(f"Cannot select {count} distinct indices below {upper_bound}")
    return tuple(rng.sample(range(upper_bound), count))
