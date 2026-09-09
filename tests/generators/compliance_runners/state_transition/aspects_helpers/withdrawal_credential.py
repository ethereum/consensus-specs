"""Shared Python realization helpers for withdrawal-credential profiles."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from random import Random


def _withdrawal_credential_prefixes(spec: Any) -> dict[str, bytes]:
    return {
        "BLS": bytes(spec.BLS_WITHDRAWAL_PREFIX),
        "ETH1": bytes(spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX),
        "COMPOUNDING": bytes(spec.COMPOUNDING_WITHDRAWAL_PREFIX),
        "BUILDER": bytes(spec.BUILDER_WITHDRAWAL_PREFIX),
    }


def withdrawal_credentials_from_profile(
    spec: Any, profile: str, address_tail: bytes, rng: Random
) -> bytes:
    prefixes = _withdrawal_credential_prefixes(spec)
    prefix = prefixes.get(profile)
    if profile == "OTHER":
        known_prefixes = set(prefixes.values())
        prefix = bytes([rng.randrange(256)])
        while prefix in known_prefixes:
            prefix = bytes([rng.randrange(256)])
    if prefix is None:
        raise ValueError(f"Cannot materialize withdrawal credential profile: {profile}")
    padding = rng.getrandbits(88).to_bytes(11, "big")
    return prefix + padding + address_tail


def withdrawal_credentials_profile(spec: Any, credentials: Any) -> str:
    profiles = {
        prefix: profile for profile, prefix in _withdrawal_credential_prefixes(spec).items()
    }
    return profiles.get(bytes(credentials[:1]), "OTHER")
