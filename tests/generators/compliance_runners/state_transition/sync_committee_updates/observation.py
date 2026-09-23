"""Extract per-vector attributes; coverage declarations live in target.py."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import Context


def observe_attributes(ctx: Context) -> dict[str, Any]:
    spec, state = (ctx.spec, ctx.pre)
    current_epoch = int(spec.get_current_epoch(state))
    next_committee = spec.get_next_sync_committee(state)
    return {
        "next_epoch": current_epoch + 1,
        "current_matches_next": state.current_sync_committee == state.next_sync_committee,
        "computed_next_matches_existing": next_committee == state.next_sync_committee,
    }
