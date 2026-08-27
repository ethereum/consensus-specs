"""Shared Python realization helpers for withdrawal-credential profiles."""

from __future__ import annotations

from typing import Any


def _withdrawal_credential_prefixes(spec: Any) -> dict[str, bytes]:
    return {
        "BLS": bytes(spec.BLS_WITHDRAWAL_PREFIX),
        "ETH1": bytes(spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX),
        "COMPOUNDING": bytes(spec.COMPOUNDING_WITHDRAWAL_PREFIX),
        "BUILDER": bytes(spec.BUILDER_WITHDRAWAL_PREFIX),
    }


def withdrawal_credentials_from_profile(spec: Any, profile: str, address_tail: bytes) -> bytes:
    return _withdrawal_credential_prefixes(spec)[profile] + b"\x00" * 11 + address_tail


def withdrawal_credentials_profile(spec: Any, credentials: Any) -> str:
    profiles = {
        prefix: profile for profile, prefix in _withdrawal_credential_prefixes(spec).items()
    }
    return profiles.get(bytes(credentials[:1]), "UNKNOWN")
