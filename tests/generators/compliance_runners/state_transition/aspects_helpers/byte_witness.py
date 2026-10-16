"""Concrete byte-string witnesses for matching and mismatching dimensions."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from random import Random


def distinct_bytes(rng: Random, length: int) -> tuple[bytes, bytes]:
    """Return two distinct byte strings of the requested length."""
    if length <= 0:
        raise ValueError("Byte witness length must be positive")
    first = rng.getrandbits(8 * length).to_bytes(length, "big")
    second = bytes([first[0] ^ 1]) + first[1:]
    return first, second
