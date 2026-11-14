"""Extract per-vector attributes; coverage declarations live in target.py."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import Context


def observe_attributes(ctx: Context) -> dict[str, Any]:
    state = ctx.pre
    return {
        "validator_count": len(state.validators),
        "previous_nonzero_count": sum(bool(flags) for flags in state.previous_epoch_participation),
        "current_nonzero_count": sum(bool(flags) for flags in state.current_epoch_participation),
    }
