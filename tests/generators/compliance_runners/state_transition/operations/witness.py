"""Complete partial process_operations obligations into concrete gate witnesses."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .target import LIMITS

if TYPE_CHECKING:
    from collections.abc import Mapping

GATES = tuple(factor.name for factor in LIMITS.factors)


def complete_obligation(obligation: Mapping[str, bool]) -> dict[str, bool]:
    """Preserve explicit values and fill only unassigned gate conditions."""
    gates = {name: bool(obligation.get(name, True)) for name in GATES}
    requested_acceptance = obligation.get("accepted")
    accepted = (
        bool(requested_acceptance) if requested_acceptance is not None else all(gates.values())
    )

    if not accepted and all(gates.values()):
        missing_gate = next((name for name in GATES if name not in obligation), None)
        if missing_gate is None:
            raise ValueError("rejection obligation has no failing or unassigned gate")
        gates[missing_gate] = False
    if accepted and not all(gates.values()):
        raise ValueError("acceptance obligation includes a failing gate")

    return {**gates, "accepted": accepted}
