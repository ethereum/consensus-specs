"""Extract per-vector attributes; coverage declarations live in target.py."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import Context


def observe_attributes(ctx: Context) -> dict[str, Any]:
    spec, state = (ctx.spec, ctx.pre)
    next_epoch = int(spec.get_current_epoch(state)) + 1
    destination_index = next_epoch % int(spec.EPOCHS_PER_SLASHINGS_VECTOR)
    return {
        "destination_index": destination_index,
        "destination_value": int(state.slashings[destination_index]),
    }
