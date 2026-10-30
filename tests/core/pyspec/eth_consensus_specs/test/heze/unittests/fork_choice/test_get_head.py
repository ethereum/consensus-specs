from eth_consensus_specs.test.context import (
    default_activation_threshold,
    single_phase,
    spec_test,
    with_custom_state,
    with_heze_and_later,
    with_matching_spec_config,
)
from eth_consensus_specs.test.helpers.payload_attestation import (
    ptc_size_balances,
    setup_verified_parent_with_distinct_ptc,
)


@with_heze_and_later
@spec_test
@with_custom_state(balances_fn=ptc_size_balances, threshold_fn=default_activation_threshold)
@single_phase
@with_matching_spec_config()
def test_get_head_unsatisfied_inclusion_list_own_slot(spec, state):
    """
    Test that get_head does not prefer the FULL node of a payload that did not satisfy
    the inclusion list constraints during the block's own slot.
    """
    store, block_root, _, _ = yield from setup_verified_parent_with_distinct_ptc(spec, state)
    assert spec.get_current_slot(store) == store.blocks[block_root].slot
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
