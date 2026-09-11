"""Shared helpers for count dimensions."""

from __future__ import annotations


def count_profile(count: int) -> str:
    """Classify a non-negative count as zero, one, or multiple."""
    if count < 0:
        raise ValueError("count must be non-negative")
    if count == 0:
        return "ZERO"
    if count == 1:
        return "ONE"
    return "MULTIPLE_COUNT"
