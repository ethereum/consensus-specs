"""Shared classification for churn-queue helper inputs."""

from __future__ import annotations


def queue_churn_variant(
    activation_epoch: int,
    earliest_epoch: int,
    requested_balance: int,
    balance_to_consume: int,
) -> str:
    """Classify whether a churn helper resets, reuses, or overflows its queue."""
    if earliest_epoch < activation_epoch:
        return "RESET_FIT"
    if requested_balance > balance_to_consume:
        return "CARRY_OVERFLOW"
    return "CARRY_FIT"
