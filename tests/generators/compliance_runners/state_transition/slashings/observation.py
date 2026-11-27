"""Observe slashings coverage dimensions from the pre-state."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import (
        Context,
    )


def observe_attributes(ctx: Context) -> dict[str, str]:
    spec, state = ctx.spec, ctx.pre
    marker = spec.Epoch(spec.GENESIS_EPOCH + 1)
    validator_index = next(
        index
        for index, validator in enumerate(state.validators)
        if validator.activation_eligibility_epoch == marker
    )
    validator = state.validators[validator_index]
    epoch = spec.get_current_epoch(state)
    total_active_balance = spec.get_total_active_balance(state)
    increment = spec.EFFECTIVE_BALANCE_INCREMENT
    raw_slashings = sum(state.slashings)
    adjusted_slashings = min(
        spec.Gwei(raw_slashings) * spec.PROPORTIONAL_SLASHING_MULTIPLIER_BELLATRIX,
        total_active_balance,
    )
    penalty_per_increment = adjusted_slashings // (total_active_balance // increment)
    due = validator.slashed and (
        epoch + spec.EPOCHS_PER_SLASHINGS_VECTOR // 2 == validator.withdrawable_epoch
    )
    penalty = (
        penalty_per_increment * (validator.effective_balance // increment) if due else spec.Gwei(0)
    )
    if not validator.slashed:
        validator_status = "UNSLASHED_VALIDATOR"
    elif not due:
        validator_status = "SLASHED_WAITING"
    else:
        validator_status = "SLASHED_DUE"
    if raw_slashings == 0:
        total_slashings = "ZERO_TOTAL"
    elif adjusted_slashings == total_active_balance:
        total_slashings = "SATURATED_TOTAL"
    else:
        total_slashings = "PARTIAL_TOTAL"
    if penalty == 0:
        penalty_outcome, outcome = "NO_PENALTY", "NO_STATE_CHANGE"
    elif penalty > state.balances[validator_index]:
        penalty_outcome, outcome = "UNDERFLOW_TO_ZERO", "BALANCE_ZEROED"
    elif penalty == state.balances[validator_index]:
        penalty_outcome, outcome = "FULL_PENALTY", "BALANCE_ZEROED"
    else:
        penalty_outcome, outcome = "PARTIAL_PENALTY", "BALANCE_DECREASED"
    return {
        "observed_validator_status": validator_status,
        "observed_total_slashings": total_slashings,
        "observed_penalty_outcome": penalty_outcome,
        "observed_outcome": outcome,
    }
