"""Extract per-vector attributes independently of coverage declarations."""

from __future__ import annotations

from typing import Any

from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import Context, NA
from tests.generators.compliance_runners.state_transition.inactivity_updates.observation import (
    recover,
)


def observe_attributes(ctx: Context) -> dict[str, Any]:
    sl = recover(ctx)
    index = sl.focus
    single_eligible = sl.loop_reached and sl.single_eligible
    score = post_score = participating = slashed = NA
    active_in_previous = timely_target_flag = NA
    if single_eligible:
        validator = sl.validator(index)
        score = sl.score(index)
        post_score = sl.post_score(index)
        participating = sl.participates(index)
        slashed = bool(validator.slashed)
        active_in_previous = sl.is_active_in_previous(index)
        timely_target_flag = sl.has_timely_target_flag(index)
    return {
        "single_eligible": single_eligible,
        "leak_free": sl.leak_free,
        "post_present": sl.post is not None,
        "score": score,
        "post_score": post_score,
        "participating": participating,
        "slashed": slashed,
        "active_in_previous": active_in_previous,
        "timely_target_flag": timely_target_flag,
        "finality_delay": sl.finality_delay,
    }
