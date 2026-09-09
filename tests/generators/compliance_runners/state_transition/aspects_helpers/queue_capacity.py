"""Shared realization helpers for queue-capacity profiles."""

from __future__ import annotations


def queue_capacity_profile(length: int, limit: int) -> str:
    if length == 0:
        return "EMPTY"
    if not 0 < length <= limit:
        return "UNKNOWN"
    if length == limit:
        return "FULL"
    return "AVAILABLE"


def queue_length_from_profile(profile: str, limit: int) -> int:
    if profile == "EMPTY":
        return 0
    if profile == "AVAILABLE":
        return 1
    if profile == "FULL":
        return limit
    raise ValueError(f"Unknown queue-capacity profile: {profile}")
