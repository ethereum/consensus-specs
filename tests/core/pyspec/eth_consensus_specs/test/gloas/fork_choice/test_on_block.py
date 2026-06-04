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
    output_head_check,
    setup_one_block_store,
    tick_and_add_block,
    tick_store_to_slot,
)
from eth_consensus_specs.test.helpers.state import (
    state_transition_and_sign_block,
)


@with_gloas_and_later
@spec_state_test
def test_on_block_parent_full_rejects_unverified_payload(spec, state):
    """
    Test that on_block rejects a child claiming a full parent when the
    parent's execution payload has not been verified.
    """
    store, _, block_state, signed_block, test_steps = yield from setup_one_block_store(spec, state)

    # Build a child that points its bid at parent.bid.block_hash so it claims
    # the parent is FULL
    tick_store_to_slot(spec, store, block_state.slot + 1, test_steps)
    child_state = block_state.copy()
    child = build_empty_block_for_next_slot(spec, child_state)
    child.body.signed_execution_payload_bid.message.parent_block_hash = (
        signed_block.message.body.signed_execution_payload_bid.message.block_hash
    )
    signed_child = state_transition_and_sign_block(spec, child_state, child)

    yield from tick_and_add_block(spec, store, signed_child, test_steps, valid=False)
    output_head_check(spec, store, test_steps)
    yield "steps", test_steps


@with_gloas_and_later
@spec_state_test
def test_on_block_parent_full_accepts_verified_payload(spec, state):
    """
    Test that on_block accepts a child claiming a full parent when the
    parent's execution payload has been verified.
    """
    store, block_root, block_state, signed_block, test_steps = yield from setup_one_block_store(
        spec, state
    )

    # Deliver the parent's envelope so is_payload_verified returns True
    envelope = build_signed_execution_payload_envelope(spec, block_state, block_root, signed_block)
    yield from add_execution_payload(spec, store, envelope, test_steps)

    # Build the same FULL-claim child fixture as the rejection test
    tick_store_to_slot(spec, store, block_state.slot + 1, test_steps)
    child_state = block_state.copy()
    child = build_empty_block_for_next_slot(spec, child_state)
    child.body.signed_execution_payload_bid.message.parent_block_hash = (
        signed_block.message.body.signed_execution_payload_bid.message.block_hash
    )
    signed_child = state_transition_and_sign_block(spec, child_state, child)

    yield from tick_and_add_block(spec, store, signed_child, test_steps)
    output_head_check(spec, store, test_steps)
    yield "steps", test_steps
