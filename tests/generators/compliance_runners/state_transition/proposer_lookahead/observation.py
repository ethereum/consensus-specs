"""Recover candidate and rotation facts from a proposer-lookahead vector."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import Context


def observe_attributes(ctx: Context) -> dict[str, Any]:
    spec, pre = ctx.spec, ctx.pre
    epoch = spec.get_current_epoch(pre) + spec.MIN_SEED_LOOKAHEAD + 1
    active = spec.get_active_validator_indices(pre, epoch)
    candidates = [index for index in active if not pre.validators[index].slashed]
    new_proposers = list(spec.get_beacon_proposer_indices(pre, epoch))
    slots = int(spec.SLOTS_PER_EPOCH)
    old = list(pre.proposer_lookahead)
    split = len(old) - slots
    return {
        "candidate_count": len(candidates),
        "slashed_active_count": len(active) - len(candidates),
        "old_lookahead_has_slashed": any(pre.validators[index].slashed for index in old),
        "new_proposers_have_duplicate": len(set(new_proposers)) < len(new_proposers),
        "old_tail_equals_new": old[split:] == new_proposers,
    }
