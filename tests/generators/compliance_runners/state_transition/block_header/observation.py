"""Extract per-vector attributes independently of coverage declarations."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import Context


def observe_attributes(ctx: Context) -> dict[str, Any]:
    spec, state, block = (ctx.spec, ctx.pre, ctx.operation)
    proposer_index = int(block.proposer_index)
    proposer_found = proposer_index < len(state.validators)
    return {
        "post_present": ctx.post is not None,
        "proposer_found": proposer_found,
        "block_slot": int(block.slot),
        "state_slot": int(state.slot),
        "latest_header_slot": int(state.latest_block_header.slot),
        "proposer_index": proposer_index,
        "expected_proposer_index": int(spec.get_beacon_proposer_index(state)),
        "parent_root_match": block.parent_root == spec.hash_tree_root(state.latest_block_header),
        "proposer_slashed": bool(state.validators[proposer_index].slashed)
        if proposer_found
        else False,
    }
