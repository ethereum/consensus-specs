from eth_consensus_specs.test.context import (
    default_activation_threshold,
    single_phase,
    spec_test,
    with_custom_state,
    with_gloas_and_later,
)
from eth_consensus_specs.test.helpers.block import build_empty_block_for_next_slot
from eth_consensus_specs.test.helpers.execution_payload import (
    build_signed_execution_payload_envelope,
)
from eth_consensus_specs.test.helpers.fork_choice import (
    add_execution_payload,
    add_payload_vote_checks,
    on_tick_and_append_step,
    output_head_check,
)
from eth_consensus_specs.test.helpers.payload_attestation import (
    ptc_size_balances,
    setup_verified_parent_with_distinct_ptc,
    vote_via_child_block,
)
from eth_consensus_specs.test.helpers.state import next_slots, state_transition_and_sign_block


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


@with_gloas_and_later
@spec_test
@with_custom_state(balances_fn=ptc_size_balances, threshold_fn=default_activation_threshold)
@single_phase
def test_get_head_with_anchor_payload_delivered(spec, state):
    """
    Test that get_head picks the FULL variant when the anchor payload is present.
    """
    test_steps = []

    # Anchor on the first block of the next epoch so it can have a payload and
    # get_head can decide between its FULL and EMPTY variants
    next_slots(spec, state, spec.SLOTS_PER_EPOCH - 1)
    anchor_block = build_empty_block_for_next_slot(spec, state)
    signed_anchor = state_transition_and_sign_block(spec, state, anchor_block)
    anchor_state = state.copy()
    anchor_root = anchor_block.hash_tree_root()

    store = spec.get_forkchoice_store(anchor_state, anchor_block)

    yield "anchor_state", anchor_state
    yield "anchor_block", anchor_block

    # Deliver the anchor payload, so the anchor has the FULL variant
    envelope = build_signed_execution_payload_envelope(
        spec, anchor_state, anchor_root, signed_anchor
    )
    yield from add_execution_payload(spec, store, envelope, test_steps)

    # Advance to the next slot so get_head can decide between the anchor's payload variants
    time = (state.slot + 1) * spec.config.SLOT_DURATION_MS // 1000 + store.genesis_time
    on_tick_and_append_step(spec, store, time, test_steps)

    # With no PTC votes or proposer boost, get_head should choose the FULL variant
    head = spec.get_head(store)
    assert head.root == anchor_root
    assert head.payload_status == spec.PAYLOAD_STATUS_FULL

    output_head_check(spec, store, test_steps)
    yield "steps", test_steps
