"""Shared realization helpers for queue-capacity profiles."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from random import Random


def queue_capacity_profile(length: int, limit: int) -> str:
    if length == 0:
        return "EMPTY"
    if not 0 < length <= limit:
        return "UNKNOWN"
    if length == limit:
        return "FULL"
    return "AVAILABLE"


def queue_occupancy(length: int, capacity: int) -> str:
    """Classify a bounded queue's occupancy."""
    if length == 0:
        return "EMPTY"
    if length == 1:
        return "SINGLE"
    if length == capacity:
        return "FULL"
    return "MULTIPLE"


def queue_length_from_profile(profile: str, limit: int, rng: Random) -> int:
    """Choose a reproducible random queue length for a capacity profile."""
    if profile == "EMPTY":
        return 0
    if profile == "AVAILABLE":
        if limit <= 1:
            raise ValueError("AVAILABLE requires a queue limit greater than one")
        return rng.randint(1, limit - 1)
    if profile == "FULL":
        return limit
    raise ValueError(f"Unknown queue-capacity profile: {profile}")
