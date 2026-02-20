from eth_consensus_specs.test.context import (
    spec_state_test,
    with_gloas_and_later,
)
from eth_consensus_specs.test.helpers.block import (
    build_empty_block_for_next_slot,
)
from eth_consensus_specs.test.helpers.execution_payload import (
    build_signed_execution_payload_envelope,
)
from eth_consensus_specs.test.helpers.fork_choice import (
    add_execution_payload,
    check_head_against_root,
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
def test_on_execution_payload(spec, state):
    test_steps = []

    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block

    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)

    anchor_root = get_anchor_root(spec, state)
    check_head_against_root(spec, store, anchor_root)

    # Genesis head has FULL payload status
    head = spec.get_head(store)
    assert head.payload_status == spec.PAYLOAD_STATUS_FULL

    # On receiving a block of `GENESIS_SLOT + 1` slot
    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block)
    yield from tick_and_add_block(spec, store, signed_block, test_steps)

    # Verify block was added to store
    block_root = signed_block.message.hash_tree_root()
    assert block_root in store.blocks
    assert block_root in store.block_states
    assert block_root in store.payload_timeliness_vote

    # Head is the new block with EMPTY status
    check_head_against_root(spec, store, block_root)
    head = spec.get_head(store)
    assert head.payload_status == spec.PAYLOAD_STATUS_EMPTY
    test_steps.append(
        {"checks": {"head_payload_status": int(spec.PAYLOAD_STATUS_EMPTY)}}
    )

    # Builder reveals execution payload
    envelope = build_signed_execution_payload_envelope(spec, state, block_root, signed_block)
    yield from add_execution_payload(spec, store, envelope, test_steps, valid=True)

    # Block root should now be stored in payload_states after payload reveal
    assert block_root in store.payload_states
    head = spec.get_head(store)
    assert head.payload_status == spec.PAYLOAD_STATUS_FULL
    test_steps.append(
        {"checks": {"head_payload_status": int(spec.PAYLOAD_STATUS_FULL)}}
    )

    # On receiving a block of next slot, chain continues after payload reveal
    block_2 = build_empty_block_for_next_slot(spec, state)
    signed_block_2 = state_transition_and_sign_block(spec, state, block_2)
    yield from tick_and_add_block(spec, store, signed_block_2, test_steps)

    block_2_root = signed_block_2.message.hash_tree_root()
    check_head_against_root(spec, store, block_2_root)

    # Head moved to block 2 with EMPTY status
    head = spec.get_head(store)
    assert head.payload_status == spec.PAYLOAD_STATUS_EMPTY
    test_steps.append(
        {"checks": {"head_payload_status": int(spec.PAYLOAD_STATUS_EMPTY)}}
    )

    yield "steps", test_steps
