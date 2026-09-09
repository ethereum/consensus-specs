"""Shared Python realization helpers for deposit-amount profiles."""

from __future__ import annotations

from random import Random
from typing import Any


def deposit_amount_from_profile(spec: Any, profile: str, rng: Random) -> int:
    """Choose a reproducible random representative for an amount profile."""
    minimum = int(spec.MIN_DEPOSIT_AMOUNT)
    activation = int(spec.MIN_ACTIVATION_BALANCE)
    if profile == "ZERO":
        return 0
    if profile == "BELOW_MINIMUM":
        return rng.randint(1, minimum - 1)
    if profile == "MINIMUM":
        return minimum
    if profile == "BETWEEN_MINIMUM_AND_ACTIVATION":
        return rng.randint(minimum + 1, activation - 1)
    if profile == "ACTIVATION":
        return activation
    if profile == "ABOVE_ACTIVATION":
        upper_bound = activation + 10 * int(spec.EFFECTIVE_BALANCE_INCREMENT)
        return rng.randint(activation + 1, upper_bound)
    raise ValueError(f"Unknown deposit amount profile: {profile}")


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
