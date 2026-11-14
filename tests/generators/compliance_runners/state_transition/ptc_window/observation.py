"""Observe the PTC-window coverage inputs from the pre-state."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import (
        Context,
    )


def observe_attributes(ctx: Context) -> dict[str, str]:
    spec, state = ctx.spec, ctx.pre
    current_epoch = spec.get_current_epoch(state)
    validator_count = len(state.validators)
    balances = state.balances
    if all(balance == spec.MAX_EFFECTIVE_BALANCE for balance in balances):
        balance_profile = "MAXIMUM_BALANCE"
    elif all(balance == spec.EFFECTIVE_BALANCE_INCREMENT for balance in balances):
        balance_profile = "MINIMUM_BALANCE"
    else:
        balance_profile = "MIXED_BALANCE"
    all_active = all(validator.activation_epoch <= current_epoch for validator in state.validators)
    return {
        "observed_epoch_position": "GENESIS_END" if int(current_epoch) == 0 else "LATER_EPOCH_END",
        "observed_validator_count": "MINIMUM" if validator_count == 64 else "MANY",
        "observed_validator_balance": balance_profile,
        "observed_validator_activity": "ALL_ACTIVE" if all_active else "SOME_INACTIVE",
    }
