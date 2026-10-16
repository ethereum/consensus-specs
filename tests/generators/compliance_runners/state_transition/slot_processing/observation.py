"""Read one-slot ``sanity/slots`` inputs without replaying the transition."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import Context


def observe_attributes(ctx: Context) -> dict[str, Any]:
    spec, state = ctx.spec, ctx.pre
    slot = int(state.slot)
    period = int(spec.SLOTS_PER_HISTORICAL_ROOT)
    index = slot % period
    next_index = (slot + 1) % period
    return {
        "slot": slot,
        "slots_to_process": int(ctx.operation),
        "header_root_zero": state.latest_block_header.state_root == spec.Bytes32(),
        "state_root_slot_nonzero": any(state.state_roots[index]),
        "block_root_slot_nonzero": any(state.block_roots[index]),
        "next_payload_available": bool(state.execution_payload_availability[next_index]),
    }
