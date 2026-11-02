"""Count the mutually exclusive registry-update branches on the pre-state."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import Context


def observe_attributes(ctx: Context) -> dict[str, Any]:
    spec, state = ctx.spec, ctx.pre
    epoch = spec.get_current_epoch(state)
    queued = ejected = activated = unchanged = 0
    for validator in state.validators:
        if spec.is_eligible_for_activation_queue(validator):
            queued += 1
        elif (
            spec.is_active_validator(validator, epoch)
            and validator.effective_balance <= spec.config.EJECTION_BALANCE
        ):
            ejected += 1
        elif spec.is_eligible_for_activation(state, validator):
            activated += 1
        else:
            unchanged += 1
    return {
        "validator_count": len(state.validators),
        "queued_count": queued,
        "ejected_count": ejected,
        "activated_count": activated,
        "unchanged_count": unchanged,
    }
