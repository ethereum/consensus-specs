"""Shared Python realization helpers for deposit-amount profiles."""

from __future__ import annotations

from typing import Any


def deposit_amount_from_profile(spec: Any, profile: str) -> int:
    minimum = int(spec.MIN_DEPOSIT_AMOUNT)
    activation = int(spec.MIN_ACTIVATION_BALANCE)
    return {
        "ZERO": 0,
        "BELOW_MINIMUM": minimum - 1,
        "MINIMUM": minimum,
        "BETWEEN_MINIMUM_AND_ACTIVATION": minimum + 1,
        "ACTIVATION": activation,
        "ABOVE_ACTIVATION": activation + int(spec.EFFECTIVE_BALANCE_INCREMENT),
    }[profile]


def deposit_amount_profile(spec: Any, amount: Any) -> str:
    amount = int(amount)
    if amount == 0:
        return "ZERO"
    minimum = int(spec.MIN_DEPOSIT_AMOUNT)
    activation = int(spec.MIN_ACTIVATION_BALANCE)
    if amount < minimum:
        return "BELOW_MINIMUM"
    if amount == minimum:
        return "MINIMUM"
    if amount < activation:
        return "BETWEEN_MINIMUM_AND_ACTIVATION"
    if amount == activation:
        return "ACTIVATION"
    return "ABOVE_ACTIVATION"
