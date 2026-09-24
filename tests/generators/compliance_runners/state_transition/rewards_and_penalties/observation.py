"""Recover the nonzero delta sources used by ``process_rewards_and_penalties``."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import Context


def observe_attributes(ctx: Context) -> dict[str, Any]:
    spec, state = ctx.spec, ctx.pre
    epoch = int(spec.get_current_epoch(state))
    result = {
        "current_epoch": epoch,
        "eligible_count": 0,
        "leaking": False,
        "flag_reward": False,
        "flag_penalty": False,
        "inactivity_penalty": False,
    }
    if epoch == int(spec.GENESIS_EPOCH):
        return result

    result["eligible_count"] = len(spec.get_eligible_validator_indices(state))
    result["leaking"] = bool(spec.is_in_inactivity_leak(state))
    for flag_index in range(len(spec.PARTICIPATION_FLAG_WEIGHTS)):
        rewards, penalties = spec.get_flag_index_deltas(state, flag_index)
        result["flag_reward"] |= any(int(amount) > 0 for amount in rewards)
        result["flag_penalty"] |= any(int(amount) > 0 for amount in penalties)
    _, penalties = spec.get_inactivity_penalty_deltas(state)
    result["inactivity_penalty"] = any(int(amount) > 0 for amount in penalties)
    return result
