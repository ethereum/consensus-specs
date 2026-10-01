"""Concrete authorization-identity witnesses for request materializers."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from random import Random


def credential_and_other_address(rng: Random) -> tuple[bytes, bytes]:
    """Return distinct credential and non-matching source addresses."""
    credential_address = rng.getrandbits(160).to_bytes(20, "big")
    other_address = bytes([credential_address[0] ^ 1]) + credential_address[1:]
    return credential_address, other_address
