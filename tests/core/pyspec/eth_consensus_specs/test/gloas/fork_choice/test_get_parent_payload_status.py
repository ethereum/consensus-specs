from eth_consensus_specs.test.context import (
    spec_state_test,
    with_gloas_and_later,
)
from eth_consensus_specs.test.helpers.block import (
    build_empty_block_for_next_slot,
)
from eth_consensus_specs.test.helpers.fork_choice import (
    get_anchor_root,
    get_genesis_forkchoice_store_and_block,
    on_tick_and_append_step,
    tick_and_add_block,
)
from eth_consensus_specs.test.helpers.state import (
    state_transition_and_sign_block,
)


@with_gloas_and_later
@spec_state_test
def test_get_parent_payload_status__genesis_empty_block_hash(spec, state):
    """
    Verify that get_parent_payload_status returns EMPTY when the parent
    block's bid has Hash32().
    """
    test_steps = []

    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    anchor_root = get_anchor_root(spec, state)

    store.blocks[
        anchor_root
    ].body.signed_execution_payload_bid.message.block_hash = spec.Hash32()

    yield "anchor_state", state
    yield "anchor_block", anchor_block

    current_time = state.slot * (spec.config.SLOT_DURATION_MS // 1000) + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)

    # Add a block on top of genesis
    block = build_empty_block_for_next_slot(spec, state)
    block.body.signed_execution_payload_bid.message.parent_block_hash = spec.Hash32()
    signed_block = state_transition_and_sign_block(spec, state, block)
    yield from tick_and_add_block(spec, store, signed_block, test_steps)

    # Parent payload status should be EMPTY
    assert spec.get_parent_payload_status(store, signed_block.message) == spec.PAYLOAD_STATUS_EMPTY

    yield "steps", test_steps
