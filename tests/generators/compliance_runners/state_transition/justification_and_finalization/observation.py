"""Recover the decisions in ``weigh_justification_and_finalization``."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import Context


def observe_attributes(ctx: Context) -> dict[str, Any]:
    spec, state = ctx.spec, ctx.pre
    epoch = int(spec.get_current_epoch(state))
    if epoch <= int(spec.GENESIS_EPOCH) + 1:
        return {
            "current_epoch": epoch,
            "previous_support": False,
            "current_support": False,
            "finalization_rule": 0,
        }

    previous_epoch = spec.get_previous_epoch(state)
    previous_indices = spec.get_unslashed_participating_indices(
        state, spec.TIMELY_TARGET_FLAG_INDEX, previous_epoch
    )
    current_indices = spec.get_unslashed_participating_indices(
        state, spec.TIMELY_TARGET_FLAG_INDEX, spec.get_current_epoch(state)
    )
    active_balance = int(spec.get_total_active_balance(state))
    previous_support = (
        3 * int(spec.get_total_balance(state, previous_indices)) >= 2 * active_balance
    )
    current_support = 3 * int(spec.get_total_balance(state, current_indices)) >= 2 * active_balance

    # Previous-epoch support can set bit 1 even when the bit shifted into it was clear.
    old_bits = state.justification_bits
    bits = (current_support, previous_support or old_bits[0], old_bits[1], old_bits[2])
    previous_justified = int(state.previous_justified_checkpoint.epoch)
    current_justified = int(state.current_justified_checkpoint.epoch)
    path = 0
    if all(bits[1:4]) and previous_justified + 3 == epoch:
        path = 1
    if all(bits[1:3]) and previous_justified + 2 == epoch:
        path = 2
    if all(bits[0:3]) and current_justified + 2 == epoch:
        path = 3
    if all(bits[0:2]) and current_justified + 1 == epoch:
        path = 4
    return {
        "current_epoch": epoch,
        "previous_support": previous_support,
        "current_support": current_support,
        "finalization_rule": path,
    }
