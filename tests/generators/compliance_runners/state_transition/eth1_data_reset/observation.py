"""Extract the concrete inputs to the ETH1 data reset coverage specification.

This adapter returns attributes only. Factor definitions and coverage choices
belong to ``target.py``; no coverage recording context is needed here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import (
        Context,
    )


def observe_attributes(ctx: Context) -> dict[str, int]:
    spec, state = ctx.spec, ctx.pre
    return {
        "next_epoch": int(spec.get_current_epoch(state)) + 1,
        "vote_count": len(state.eth1_data_votes),
    }
