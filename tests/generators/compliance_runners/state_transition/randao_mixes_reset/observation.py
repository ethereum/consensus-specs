"""Extract per-vector attributes; coverage declarations live in target.py."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import Context


def observe_attributes(ctx: Context) -> dict[str, Any]:
    spec, state = (ctx.spec, ctx.pre)
    current_epoch = int(spec.get_current_epoch(state))
    next_epoch = current_epoch + 1
    vector_length = int(spec.EPOCHS_PER_HISTORICAL_VECTOR)
    source_index = current_epoch % vector_length
    destination_index = next_epoch % vector_length
    return {
        "destination_index": destination_index,
        "source_mix": bytes(state.randao_mixes[source_index]),
        "destination_mix": bytes(state.randao_mixes[destination_index]),
    }
