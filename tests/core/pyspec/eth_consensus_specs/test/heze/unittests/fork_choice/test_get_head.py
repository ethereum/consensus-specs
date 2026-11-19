from eth_consensus_specs.test.context import (
    default_activation_threshold,
    single_phase,
    spec_test,
    with_custom_state,
    with_heze_and_later,
    with_matching_spec_config,
)
from eth_consensus_specs.test.helpers.fork_choice import tick_store_to_slot
from eth_consensus_specs.test.helpers.payload_attestation import (
    ptc_size_balances,
    setup_verified_parent_with_distinct_ptc,
)


@with_heze_and_later
@spec_test
@with_custom_state(balances_fn=ptc_size_balances, threshold_fn=default_activation_threshold)
@single_phase
@with_matching_spec_config()
def test_get_head_unsatisfied_inclusion_list(spec, state):
    """
    Test that get_head prefers the EMPTY node of a block whose payload did not satisfy
    the inclusion list constraints during the block's own slot and the next slot.
    """
    store, block_root, _, test_steps = yield from setup_verified_parent_with_distinct_ptc(
        spec, state
    )
    slot = store.blocks[block_root].slot
    assert spec.get_current_slot(store) == slot
    assert spec.is_payload_inclusion_list_satisfied(store, block_root)

    full_node = spec.ForkChoiceNode(root=block_root, payload_status=spec.PAYLOAD_STATUS_FULL)
    empty_node = spec.ForkChoiceNode(root=block_root, payload_status=spec.PAYLOAD_STATUS_EMPTY)

    # A satisfied payload is preferred over its empty variant as in Gloas
    full_rank = spec.get_payload_status_tiebreaker(store, full_node)
    empty_rank = spec.get_payload_status_tiebreaker(store, empty_node)
    assert full_rank > empty_rank
    head = spec.get_head(store)
    assert head.root == block_root
    assert head.payload_status == spec.PAYLOAD_STATUS_FULL

    # Once the payload is known to not satisfy the constraints, the empty variant is the head
    store.payload_inclusion_list_satisfaction[block_root] = False
    full_rank = spec.get_payload_status_tiebreaker(store, full_node)
    empty_rank = spec.get_payload_status_tiebreaker(store, empty_node)
    assert empty_rank > full_rank
    head = spec.get_head(store)
    assert head.root == block_root
    assert head.payload_status == spec.PAYLOAD_STATUS_EMPTY

    # The empty variant remains the head during the next slot
    tick_store_to_slot(spec, store, slot + 1, test_steps)
    full_rank = spec.get_payload_status_tiebreaker(store, full_node)
    empty_rank = spec.get_payload_status_tiebreaker(store, empty_node)
    assert empty_rank > full_rank
    head = spec.get_head(store)
    assert head.root == block_root
    assert head.payload_status == spec.PAYLOAD_STATUS_EMPTY

    # After the next slot, the payload is preferred over its empty variant again
    tick_store_to_slot(spec, store, slot + 2, test_steps)
    full_rank = spec.get_payload_status_tiebreaker(store, full_node)
    empty_rank = spec.get_payload_status_tiebreaker(store, empty_node)
    assert full_rank > empty_rank
    head = spec.get_head(store)
    assert head.root == block_root
    assert head.payload_status == spec.PAYLOAD_STATUS_FULL


@with_heze_and_later
@spec_test
@with_custom_state(balances_fn=ptc_size_balances, threshold_fn=default_activation_threshold)
@single_phase
@with_matching_spec_config()
def test_build_on_empty_unsatisfied_inclusion_list(spec, state):
    """
    Test that the next proposer builds on the EMPTY node, and only bids built on it are
    compatible with the head, once the payload is known to not satisfy the inclusion list
    constraints, during the block's own slot and the next slot.
    """
    store, block_root, _, test_steps = yield from setup_verified_parent_with_distinct_ptc(
        spec, state
    )
    slot = store.blocks[block_root].slot
    head_bid = store.blocks[block_root].body.signed_execution_payload_bid.message
    assert head_bid.block_hash != head_bid.parent_block_hash

    bid_on_full = spec.ExecutionPayloadBid(
        slot=slot + 1, parent_block_root=block_root, parent_block_hash=head_bid.block_hash
    )
    bid_on_empty = spec.ExecutionPayloadBid(
        slot=slot + 1, parent_block_root=block_root, parent_block_hash=head_bid.parent_block_hash
    )

    # A satisfied payload is built on as in Gloas
    assert spec.should_build_on_full(store, spec.get_head(store), slot + 1)
    assert spec.is_bid_compatible_with_head(store, bid_on_full)
    assert not spec.is_bid_compatible_with_head(store, bid_on_empty)

    # Once the payload is known to not satisfy the constraints, it is not built on
    store.payload_inclusion_list_satisfaction[block_root] = False
    assert not spec.should_build_on_full(store, spec.get_head(store), slot + 1)
    assert not spec.is_bid_compatible_with_head(store, bid_on_full)
    assert spec.is_bid_compatible_with_head(store, bid_on_empty)

    # Nothing changes at the start of the next slot
    tick_store_to_slot(spec, store, slot + 1, test_steps)
    assert not spec.should_build_on_full(store, spec.get_head(store), slot + 1)
    assert not spec.is_bid_compatible_with_head(store, bid_on_full)
    assert spec.is_bid_compatible_with_head(store, bid_on_empty)
