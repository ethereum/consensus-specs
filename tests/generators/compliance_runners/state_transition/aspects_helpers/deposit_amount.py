"""Shared Python realization helpers for deposit-amount profiles."""

from __future__ import annotations

from typing import Any


def deposit_amount_from_profile(spec: Any, profile: str) -> int:
    return {
        "ZERO": 0,
        "MINIMUM": int(spec.MIN_DEPOSIT_AMOUNT),
        "ACTIVATION": int(spec.MIN_ACTIVATION_BALANCE),
        "ABOVE_ACTIVATION": int(spec.MIN_ACTIVATION_BALANCE + spec.EFFECTIVE_BALANCE_INCREMENT),
    }[profile]


def deposit_amount_profile(spec: Any, amount: Any) -> str:
    amount = int(amount)
    if amount == 0:
        return "ZERO"
    if amount == int(spec.MIN_DEPOSIT_AMOUNT):
        return "MINIMUM"
    if amount == int(spec.MIN_ACTIVATION_BALANCE):
        return "ACTIVATION"
    if amount > int(spec.MIN_ACTIVATION_BALANCE):
        return "ABOVE_ACTIVATION"
    return "UNKNOWN"
