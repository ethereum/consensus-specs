from eth_consensus_specs.test.context import (
    default_activation_threshold,
    single_phase,
    spec_test,
    with_custom_state,
    with_gloas_and_later,
)
from eth_consensus_specs.test.helpers.fork_choice import (
    add_payload_vote_checks,
    output_head_check,
)
from eth_consensus_specs.test.helpers.payload_attestation import (
    ptc_size_balances,
    setup_verified_parent_with_distinct_ptc,
    vote_via_child_block,
)


@with_gloas_and_later
@spec_test
@with_custom_state(balances_fn=ptc_size_balances, threshold_fn=default_activation_threshold)
@single_phase
def test_get_head_full_payload_tiebreak(spec, state):
    """
    Test that get_head picks the FULL variant of a previous slot payload decision
    when should_extend_payload is true.
    """
    store, block_root, block_state, test_steps = yield from setup_verified_parent_with_distinct_ptc(
        spec, state
    )

    yield from vote_via_child_block(
        spec,
        store,
        block_root,
        block_state,
        positions=range(spec.PAYLOAD_TIMELY_THRESHOLD + 1),
        test_steps=test_steps,
        payload_present=True,
        blob_data_available=True,
    )

    # PTC voted timely and available, so the tiebreaker must rank FULL above EMPTY
    assert spec.should_extend_payload(store, block_root)

    full_node = spec.ForkChoiceNode(root=block_root, payload_status=spec.PAYLOAD_STATUS_FULL)
    empty_node = spec.ForkChoiceNode(root=block_root, payload_status=spec.PAYLOAD_STATUS_EMPTY)

    full_rank = spec.get_payload_status_tiebreaker(store, full_node)
    empty_rank = spec.get_payload_status_tiebreaker(store, empty_node)
    assert full_rank > empty_rank

    # get_head stops at the parent FULL node
    head = spec.get_head(store)
    assert head.root == block_root
    assert head.payload_status == spec.PAYLOAD_STATUS_FULL

    add_payload_vote_checks(store, block_root, test_steps)
    output_head_check(spec, store, test_steps)
    yield "steps", test_steps


@with_gloas_and_later
@spec_test
@with_custom_state(balances_fn=ptc_size_balances, threshold_fn=default_activation_threshold)
@single_phase
def test_get_head_empty_payload_tiebreak(spec, state):
    """
    Test that get_head picks the EMPTY variant of a previous slot payload decision
    when should_extend_payload is false.
    """
    store, block_root, block_state, test_steps = yield from setup_verified_parent_with_distinct_ptc(
        spec, state
    )

    child_root = yield from vote_via_child_block(
        spec,
        store,
        block_root,
        block_state,
        positions=range(spec.PAYLOAD_TIMELY_THRESHOLD + 1),
        test_steps=test_steps,
        payload_present=False,
        blob_data_available=True,
    )

    # PTC voted untimely, so the tiebreaker must rank EMPTY above FULL
    assert not spec.should_extend_payload(store, block_root)

    full_node = spec.ForkChoiceNode(root=block_root, payload_status=spec.PAYLOAD_STATUS_FULL)
    empty_node = spec.ForkChoiceNode(root=block_root, payload_status=spec.PAYLOAD_STATUS_EMPTY)

    full_rank = spec.get_payload_status_tiebreaker(store, full_node)
    empty_rank = spec.get_payload_status_tiebreaker(store, empty_node)
    assert empty_rank > full_rank

    # get_head walks past parent EMPTY to the slot-2 child
    head = spec.get_head(store)
    assert head.root == child_root
    assert head.payload_status == spec.PAYLOAD_STATUS_EMPTY

    add_payload_vote_checks(store, block_root, test_steps)
    output_head_check(spec, store, test_steps)
    yield "steps", test_steps
