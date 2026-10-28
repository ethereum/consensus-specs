from eth_consensus_specs.test.context import (
    spec_state_test,
    with_heze_and_later,
    with_presets,
)
from eth_consensus_specs.test.helpers.block import (
    build_empty_block_for_next_slot,
)
from eth_consensus_specs.test.helpers.constants import MAINNET
from eth_consensus_specs.test.helpers.execution_payload import (
    build_signed_execution_payload_envelope,
    sign_execution_payload_envelope,
)
from eth_consensus_specs.test.helpers.fork_choice import (
    add_execution_payload,
    add_inclusion_list,
    add_payload_inclusion_list_satisfaction_check,
    add_signed_empty_block,
    check_head_against_root,
    get_genesis_forkchoice_store_and_block,
    on_tick_and_append_step,
    output_head_check,
    setup_one_block_store,
    tick_and_add_block,
    tick_store_to_slot,
)
from eth_consensus_specs.test.helpers.inclusion_list import (
    cached_inclusion_list_store,
    get_sample_signed_inclusion_list,
)
from eth_consensus_specs.test.helpers.state import (
    state_transition_and_sign_block,
)


def _add_payload(spec, store, state, test_steps, transactions=()):
    """
    Add the next block, and its payload with ``transactions``, and emit the
    payload's inclusion list satisfaction check.
    """
    block_root, _, signed_block = yield from add_signed_empty_block(spec, store, state, test_steps)
    envelope = build_signed_execution_payload_envelope(
        spec, state, block_root, signed_block
    ).message
    envelope.payload.transactions = spec.Transactions(data=transactions)
    signed_envelope = sign_execution_payload_envelope(spec, state, signed_block, envelope)
    yield from add_execution_payload(spec, store, signed_envelope, test_steps)
    add_payload_inclusion_list_satisfaction_check(store, block_root, test_steps)
    return block_root


def _check_head_payload_extended(spec, store, block_root, extended, test_steps):
    """
    Tick to the slot after ``block_root`` and check whether fork choice extends its payload.
    """
    tick_store_to_slot(spec, store, store.blocks[block_root].slot + 1, test_steps)
    check_head_against_root(spec, store, block_root)
    status = spec.PAYLOAD_STATUS_FULL if extended else spec.PAYLOAD_STATUS_EMPTY
    assert spec.get_head(store).payload_status == status
    output_head_check(spec, store, test_steps)


def _run_inclusion_list_scenario(spec, state, add_inclusion_lists, satisfied):
    """
    Add inclusion lists for slot 0 with ``add_inclusion_lists``, which returns the
    payload transactions, add the block at slot 1 with that payload, and check that
    the payload is ``satisfied`` and extended in slot 2 only if it is.
    """
    with cached_inclusion_list_store(spec):
        test_steps = []
        store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
        yield "anchor_state", state
        yield "anchor_block", anchor_block

        transactions = yield from add_inclusion_lists(spec, store, state, test_steps)
        block_root = yield from _add_payload(spec, store, state, test_steps, transactions)

        assert store.payload_inclusion_list_satisfaction[block_root] == satisfied
        _check_head_payload_extended(spec, store, block_root, satisfied, test_steps)

    yield "steps", test_steps


def _get_inclusion_list(spec, store, state, committee_position=0):
    committee = spec.get_inclusion_list_committee(state, state.slot)
    return get_sample_signed_inclusion_list(
        spec, store, state, validator_index=committee[committee_position]
    )


def _tick_into_slot_0(spec, store, time_into_slot_ms, test_steps):
    # Test vectors express ticks in whole seconds
    assert time_into_slot_ms % 1000 == 0
    on_tick_and_append_step(spec, store, store.genesis_time_ms + time_into_slot_ms, test_steps)


def _last_second_before_due_ms(spec):
    return (spec.get_inclusion_list_due_ms() - 1) // 1000 * 1000


def _first_second_after_due_ms(spec):
    return (spec.get_inclusion_list_due_ms() + 999) // 1000 * 1000


#
# Satisfaction
#


def _add_timely_inclusion_lists(count, included):
    """
    Add ``count`` timely inclusion lists and return the transactions of the
    first ``included`` of them.
    """

    def add_inclusion_lists(spec, store, state, test_steps):
        inclusion_lists = [_get_inclusion_list(spec, store, state, i) for i in range(count)]
        for inclusion_list in inclusion_lists:
            yield from add_inclusion_list(spec, store, inclusion_list, test_steps)
        return [tx for il in inclusion_lists[:included] for tx in il.message.transactions]

    return add_inclusion_lists


@with_heze_and_later
@spec_state_test
def test_payload_satisfies_inclusion_list(spec, state):
    """
    Test that a payload containing every timely inclusion list transaction is
    satisfied and extended in the next slot.
    """
    yield from _run_inclusion_list_scenario(
        spec, state, _add_timely_inclusion_lists(1, included=1), satisfied=True
    )


@with_heze_and_later
@spec_state_test
def test_payload_missing_inclusion_list_transactions(spec, state):
    """
    Test that a payload missing a timely inclusion list transaction remains valid
    but is not extended in the next slot.
    """
    yield from _run_inclusion_list_scenario(
        spec, state, _add_timely_inclusion_lists(1, included=0), satisfied=False
    )


@with_heze_and_later
@spec_state_test
def test_payload_satisfies_only_one_of_two_inclusion_lists(spec, state):
    """
    Test that a payload containing the transactions of only one of two timely
    inclusion lists is not extended in the next slot.
    """
    yield from _run_inclusion_list_scenario(
        spec, state, _add_timely_inclusion_lists(2, included=1), satisfied=False
    )


#
# Timeliness
#


def _add_inclusion_list_at(time_into_slot_ms_fn):
    """
    Add an inclusion list at ``time_into_slot_ms_fn(spec)`` into slot 0 and
    return no payload transactions.
    """

    def add_inclusion_lists(spec, store, state, test_steps):
        _tick_into_slot_0(spec, store, time_into_slot_ms_fn(spec), test_steps)
        yield from add_inclusion_list(
            spec, store, _get_inclusion_list(spec, store, state), test_steps
        )
        return []

    return add_inclusion_lists


@with_heze_and_later
@spec_state_test
@with_presets([MAINNET], reason="the inclusion list due is a whole second only on mainnet")
def test_inclusion_list_at_due_is_not_enforced(spec, state):
    """
    Test that an inclusion list received exactly at the inclusion list due is
    untimely and does not constrain the payload.
    """
    yield from _run_inclusion_list_scenario(
        spec,
        state,
        _add_inclusion_list_at(lambda spec: spec.get_inclusion_list_due_ms()),
        satisfied=True,
    )


@with_heze_and_later
@spec_state_test
def test_inclusion_list_before_due_is_enforced(spec, state):
    """
    Test that an inclusion list received in the last whole second before the
    inclusion list due is timely and constrains the payload.
    """
    yield from _run_inclusion_list_scenario(
        spec, state, _add_inclusion_list_at(_last_second_before_due_ms), satisfied=False
    )


@with_heze_and_later
@spec_state_test
def test_inclusion_list_after_due_is_not_enforced(spec, state):
    """
    Test that an inclusion list received in the first whole second after the
    inclusion list due is untimely and does not constrain the payload.
    """
    yield from _run_inclusion_list_scenario(
        spec, state, _add_inclusion_list_at(_first_second_after_due_ms), satisfied=True
    )


@with_heze_and_later
@spec_state_test
def test_inclusion_list_in_next_slot_is_not_enforced(spec, state):
    """
    Test that an inclusion list received in the slot after its own slot is
    untimely and does not constrain the payload.
    """
    yield from _run_inclusion_list_scenario(
        spec,
        state,
        _add_inclusion_list_at(lambda spec: spec.config.SLOT_DURATION_MS),
        satisfied=True,
    )


#
# Equivocation
#


def _add_inclusion_list_twice(equivocate, second_at=None):
    """
    Add an inclusion list in slot 0, then add it again, or a different one from
    the same validator if ``equivocate``, optionally after ticking to
    ``second_at(spec)``. Return no payload transactions.
    """

    def add_inclusion_lists(spec, store, state, test_steps):
        first = _get_inclusion_list(spec, store, state)
        second = _get_inclusion_list(spec, store, state) if equivocate else first
        assert (first != second) == equivocate
        yield from add_inclusion_list(spec, store, first, test_steps)
        if second_at is not None:
            _tick_into_slot_0(spec, store, second_at(spec), test_steps)
        yield from add_inclusion_list(spec, store, second, test_steps)
        return []

    return add_inclusion_lists


@with_heze_and_later
@spec_state_test
def test_equivocating_inclusion_lists_are_not_enforced(spec, state):
    """
    Test that two different timely inclusion lists from the same validator
    are both ignored and do not constrain the payload.
    """
    yield from _run_inclusion_list_scenario(
        spec, state, _add_inclusion_list_twice(equivocate=True), satisfied=True
    )


@with_heze_and_later
@spec_state_test
def test_equivocation_after_due_cancels_timely_inclusion_list(spec, state):
    """
    Test that an equivocating inclusion list received after the inclusion list
    due still cancels the validator's earlier timely inclusion list.
    """
    yield from _run_inclusion_list_scenario(
        spec,
        state,
        _add_inclusion_list_twice(equivocate=True, second_at=_first_second_after_due_ms),
        satisfied=True,
    )


@with_heze_and_later
@spec_state_test
def test_duplicate_inclusion_list_is_enforced(spec, state):
    """
    Test that receiving the same inclusion list twice is not an equivocation,
    so the inclusion list still constrains the payload.
    """
    yield from _run_inclusion_list_scenario(
        spec, state, _add_inclusion_list_twice(equivocate=False), satisfied=False
    )


@with_heze_and_later
@spec_state_test
def test_duplicate_inclusion_list_after_due_keeps_timeliness(spec, state):
    """
    Test that receiving a timely inclusion list again after the inclusion list
    due does not make it untimely.
    """
    yield from _run_inclusion_list_scenario(
        spec,
        state,
        _add_inclusion_list_twice(equivocate=False, second_at=_first_second_after_due_ms),
        satisfied=False,
    )


#
# Epoch boundary
#


@with_heze_and_later
@spec_state_test
def test_payload_at_epoch_start_uses_previous_epoch_dependent_root(spec, state):
    """
    Test that the payload of the first block of an epoch is checked against the
    inclusion lists of the last slot of the previous epoch, which are keyed by
    the previous epoch's shuffling dependent root.
    """
    with cached_inclusion_list_store(spec):
        # The block at slot 1 is the shuffling dependent block of epoch 2, but not of epoch 1
        store, _, _, _, test_steps = yield from setup_one_block_store(spec, state)
        epoch = spec.MIN_SEED_LOOKAHEAD + 1

        spec.process_slots(state, spec.compute_start_slot_at_epoch(epoch) - 1)
        tick_store_to_slot(spec, store, state.slot, test_steps)
        inclusion_list = _get_inclusion_list(spec, store, state)
        yield from add_inclusion_list(spec, store, inclusion_list, test_steps)

        block_root = yield from _add_payload(spec, store, state, test_steps)
        assert spec.compute_epoch_at_slot(state.slot) == epoch
        assert inclusion_list.message.dependent_root != spec.get_shuffling_dependent_root(
            store, block_root, epoch
        )

        assert not store.payload_inclusion_list_satisfaction[block_root]
        _check_head_payload_extended(spec, store, block_root, extended=False, test_steps=test_steps)

    yield "steps", test_steps


#
# Payload extension
#


@with_heze_and_later
@spec_state_test
def test_child_of_unsatisfied_full_parent_is_not_head(spec, state):
    """
    Test that a valid child building on an unsatisfied full parent is accepted,
    but fork choice does not extend the parent's payload in the child's slot.
    """
    with cached_inclusion_list_store(spec):
        test_steps = []
        store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
        yield "anchor_state", state
        yield "anchor_block", anchor_block

        yield from _add_timely_inclusion_lists(1, included=0)(spec, store, state, test_steps)
        parent_root = yield from _add_payload(spec, store, state, test_steps)

        # Build a child that claims the parent is FULL
        child = build_empty_block_for_next_slot(spec, state)
        bid = child.body.signed_execution_payload_bid.message
        bid.parent_block_hash = state.latest_execution_payload_bid.block_hash
        bid.block_hash = spec.Hash32(b"\x42" * 32)
        signed_child = state_transition_and_sign_block(spec, state, child)
        yield from tick_and_add_block(spec, store, signed_child, test_steps)

        assert store.proposer_boost_root == signed_child.message.hash_tree_root()
        assert spec.is_parent_node_full(store, signed_child.message)
        check_head_against_root(spec, store, parent_root)
        assert spec.get_head(store).payload_status == spec.PAYLOAD_STATUS_EMPTY
        output_head_check(spec, store, test_steps)

    yield "steps", test_steps


@with_heze_and_later
@spec_state_test
def test_unsatisfied_payload_is_head_in_its_own_slot(spec, state):
    """
    Test that an unsatisfied payload is the head in its own slot, because
    inclusion list satisfaction only decides whether the next slot extends it.
    """
    with cached_inclusion_list_store(spec):
        test_steps = []
        store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
        yield "anchor_state", state
        yield "anchor_block", anchor_block

        yield from _add_timely_inclusion_lists(1, included=0)(spec, store, state, test_steps)
        block_root = yield from _add_payload(spec, store, state, test_steps)

        assert not store.payload_inclusion_list_satisfaction[block_root]
        check_head_against_root(spec, store, block_root)
        assert spec.get_head(store).payload_status == spec.PAYLOAD_STATUS_FULL
        output_head_check(spec, store, test_steps)

    yield "steps", test_steps
