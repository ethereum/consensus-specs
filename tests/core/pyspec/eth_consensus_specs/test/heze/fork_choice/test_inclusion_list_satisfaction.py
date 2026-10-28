from eth_consensus_specs.test.context import (
    spec_state_test,
    with_heze_and_later,
    with_presets,
)
from eth_consensus_specs.test.helpers.block import (
    build_empty_block_for_next_slot,
)
from eth_consensus_specs.test.helpers.constants import MAINNET, MINIMAL
from eth_consensus_specs.test.helpers.execution_payload import (
    build_signed_execution_payload_envelope,
    sign_execution_payload_envelope,
)
from eth_consensus_specs.test.helpers.fork_choice import (
    add_execution_payload,
    add_inclusion_list,
    add_payload_inclusion_list_satisfaction_check,
    check_head_against_root,
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


def _get_inclusion_list(spec, store, state, committee_position=0):
    committee = spec.get_inclusion_list_committee(state, state.slot)
    return get_sample_signed_inclusion_list(
        spec, store, state, validator_index=committee[committee_position]
    )


def _tick_into_slot(spec, store, slot, time_into_slot_ms, test_steps):
    time_ms = spec.compute_time_at_slot_ms(store.genesis_time_ms, slot) + time_into_slot_ms
    # Test vectors express ticks in whole seconds
    assert time_ms % 1000 == 0
    on_tick_and_append_step(spec, store, time_ms, test_steps)


def _add_next_block(spec, store, parent_state, test_steps):
    state = parent_state.copy()
    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block)
    yield from tick_and_add_block(spec, store, signed_block, test_steps)
    return signed_block.message.hash_tree_root(), state, signed_block


def _build_envelope(spec, state, block_root, signed_block, transactions):
    signed_envelope = build_signed_execution_payload_envelope(spec, state, block_root, signed_block)
    envelope = signed_envelope.message
    envelope.payload.transactions = spec.Transactions(data=transactions)
    return sign_execution_payload_envelope(spec, state, signed_block, envelope)


def _run_inclusion_list_scenario(spec, state, add_inclusion_lists, get_payload_transactions):
    """
    Seed inclusion lists for slot 1 with ``add_inclusion_lists``, add the block at
    slot 2 with a payload containing ``get_payload_transactions(inclusion_lists)``,
    and tick to slot 3, where fork choice decides whether to extend that payload.
    """
    store, _, block_state, _, test_steps = yield from setup_one_block_store(spec, state)

    inclusion_lists = yield from add_inclusion_lists(spec, store, block_state, test_steps)

    block_root, state, signed_block = yield from _add_next_block(
        spec, store, block_state, test_steps
    )
    envelope = _build_envelope(
        spec, state, block_root, signed_block, get_payload_transactions(inclusion_lists)
    )
    yield from add_execution_payload(spec, store, envelope, test_steps)
    add_payload_inclusion_list_satisfaction_check(store, block_root, test_steps)

    tick_store_to_slot(spec, store, state.slot + 1, test_steps)
    check_head_against_root(spec, store, block_root)
    output_head_check(spec, store, test_steps)

    return store, block_root, test_steps


def _all_transactions(inclusion_lists):
    return [
        transaction
        for inclusion_list in inclusion_lists
        for transaction in inclusion_list.message.transactions
    ]


def _no_transactions(_inclusion_lists):
    return []


def _add_timely_inclusion_lists(count):
    def add_inclusion_lists(spec, store, state, test_steps):
        inclusion_lists = [
            _get_inclusion_list(spec, store, state, committee_position=i) for i in range(count)
        ]
        for inclusion_list in inclusion_lists:
            yield from add_inclusion_list(spec, store, inclusion_list, test_steps)
        return inclusion_lists

    return add_inclusion_lists


#
# Satisfaction
#


@with_heze_and_later
@spec_state_test
def test_payload_satisfies_inclusion_list(spec, state):
    """
    Test that a payload containing every timely inclusion list transaction is
    satisfied and extended in the next slot.
    """
    with cached_inclusion_list_store(spec):
        store, block_root, test_steps = yield from _run_inclusion_list_scenario(
            spec, state, _add_timely_inclusion_lists(1), _all_transactions
        )

    assert store.payload_inclusion_list_satisfaction[block_root]
    assert spec.get_head(store).payload_status == spec.PAYLOAD_STATUS_FULL

    yield "steps", test_steps


@with_heze_and_later
@spec_state_test
def test_payload_missing_inclusion_list_transactions(spec, state):
    """
    Test that a payload missing a timely inclusion list transaction remains valid
    but is not extended in the next slot.
    """
    with cached_inclusion_list_store(spec):
        store, block_root, test_steps = yield from _run_inclusion_list_scenario(
            spec, state, _add_timely_inclusion_lists(1), _no_transactions
        )

    assert block_root in store.payloads
    assert not store.payload_inclusion_list_satisfaction[block_root]
    assert spec.get_head(store).payload_status == spec.PAYLOAD_STATUS_EMPTY

    yield "steps", test_steps


@with_heze_and_later
@spec_state_test
def test_payload_satisfies_only_one_of_two_inclusion_lists(spec, state):
    """
    Test that a payload containing the transactions of only one of two timely
    inclusion lists is not extended in the next slot.
    """
    with cached_inclusion_list_store(spec):
        store, block_root, test_steps = yield from _run_inclusion_list_scenario(
            spec,
            state,
            _add_timely_inclusion_lists(2),
            lambda inclusion_lists: _all_transactions(inclusion_lists[:1]),
        )

    assert not store.payload_inclusion_list_satisfaction[block_root]
    assert spec.get_head(store).payload_status == spec.PAYLOAD_STATUS_EMPTY

    yield "steps", test_steps


#
# Timeliness
#


def _add_inclusion_list_at(time_into_slot_ms_fn):
    def add_inclusion_lists(spec, store, state, test_steps):
        inclusion_list = _get_inclusion_list(spec, store, state)
        _tick_into_slot(spec, store, state.slot, time_into_slot_ms_fn(spec), test_steps)
        yield from add_inclusion_list(spec, store, inclusion_list, test_steps)
        return [inclusion_list]

    return add_inclusion_lists


@with_heze_and_later
@spec_state_test
@with_presets([MAINNET], reason="the inclusion list due is a whole second only on mainnet")
def test_inclusion_list_at_due_is_not_enforced(spec, state):
    """
    Test that an inclusion list received exactly at the inclusion list due is
    untimely and does not constrain the payload.
    """
    with cached_inclusion_list_store(spec):
        store, block_root, test_steps = yield from _run_inclusion_list_scenario(
            spec,
            state,
            _add_inclusion_list_at(lambda spec: spec.get_inclusion_list_due_ms()),
            _no_transactions,
        )

    assert store.payload_inclusion_list_satisfaction[block_root]
    assert spec.get_head(store).payload_status == spec.PAYLOAD_STATUS_FULL

    yield "steps", test_steps


@with_heze_and_later
@spec_state_test
def test_inclusion_list_before_due_is_enforced(spec, state):
    """
    Test that an inclusion list received in the last whole second before the
    inclusion list due is timely and constrains the payload.
    """
    with cached_inclusion_list_store(spec):
        store, block_root, test_steps = yield from _run_inclusion_list_scenario(
            spec,
            state,
            _add_inclusion_list_at(
                lambda spec: (spec.get_inclusion_list_due_ms() - 1) // 1000 * 1000
            ),
            _no_transactions,
        )

    assert not store.payload_inclusion_list_satisfaction[block_root]
    assert spec.get_head(store).payload_status == spec.PAYLOAD_STATUS_EMPTY

    yield "steps", test_steps


@with_heze_and_later
@spec_state_test
def test_inclusion_list_after_due_is_not_enforced(spec, state):
    """
    Test that an inclusion list received in the first whole second after the
    inclusion list due is untimely and does not constrain the payload.
    """
    with cached_inclusion_list_store(spec):
        store, block_root, test_steps = yield from _run_inclusion_list_scenario(
            spec,
            state,
            _add_inclusion_list_at(
                lambda spec: (spec.get_inclusion_list_due_ms() + 999) // 1000 * 1000
            ),
            _no_transactions,
        )

    assert store.payload_inclusion_list_satisfaction[block_root]
    assert spec.get_head(store).payload_status == spec.PAYLOAD_STATUS_FULL

    yield "steps", test_steps


@with_heze_and_later
@spec_state_test
def test_inclusion_list_in_next_slot_is_not_enforced(spec, state):
    """
    Test that an inclusion list received in the slot after its own slot is
    untimely and does not constrain the payload.
    """
    with cached_inclusion_list_store(spec):
        store, block_root, test_steps = yield from _run_inclusion_list_scenario(
            spec,
            state,
            _add_inclusion_list_at(lambda spec: spec.config.SLOT_DURATION_MS),
            _no_transactions,
        )

    assert store.payload_inclusion_list_satisfaction[block_root]
    assert spec.get_head(store).payload_status == spec.PAYLOAD_STATUS_FULL

    yield "steps", test_steps


#
# Equivocation
#


def _add_equivocating_inclusion_lists(second_time_into_slot_ms_fn):
    def add_inclusion_lists(spec, store, state, test_steps):
        inclusion_list_1 = _get_inclusion_list(spec, store, state)
        inclusion_list_2 = _get_inclusion_list(spec, store, state)
        assert inclusion_list_1 != inclusion_list_2
        yield from add_inclusion_list(spec, store, inclusion_list_1, test_steps)
        time_into_slot_ms = second_time_into_slot_ms_fn(spec)
        if time_into_slot_ms is not None:
            _tick_into_slot(spec, store, state.slot, time_into_slot_ms, test_steps)
        yield from add_inclusion_list(spec, store, inclusion_list_2, test_steps)
        return [inclusion_list_1, inclusion_list_2]

    return add_inclusion_lists


@with_heze_and_later
@spec_state_test
def test_equivocating_inclusion_lists_are_not_enforced(spec, state):
    """
    Test that two different timely inclusion lists from the same validator
    are both ignored and do not constrain the payload.
    """
    with cached_inclusion_list_store(spec):
        store, block_root, test_steps = yield from _run_inclusion_list_scenario(
            spec,
            state,
            _add_equivocating_inclusion_lists(lambda spec: None),
            _no_transactions,
        )

    assert store.payload_inclusion_list_satisfaction[block_root]
    assert spec.get_head(store).payload_status == spec.PAYLOAD_STATUS_FULL

    yield "steps", test_steps


@with_heze_and_later
@spec_state_test
def test_equivocation_after_due_cancels_timely_inclusion_list(spec, state):
    """
    Test that an equivocating inclusion list received after the inclusion list
    due still cancels the validator's earlier timely inclusion list.
    """
    with cached_inclusion_list_store(spec):
        store, block_root, test_steps = yield from _run_inclusion_list_scenario(
            spec,
            state,
            _add_equivocating_inclusion_lists(
                lambda spec: (spec.get_inclusion_list_due_ms() + 999) // 1000 * 1000
            ),
            _no_transactions,
        )

    assert store.payload_inclusion_list_satisfaction[block_root]
    assert spec.get_head(store).payload_status == spec.PAYLOAD_STATUS_FULL

    yield "steps", test_steps


def _add_duplicate_inclusion_list(second_time_into_slot_ms_fn):
    def add_inclusion_lists(spec, store, state, test_steps):
        inclusion_list = _get_inclusion_list(spec, store, state)
        yield from add_inclusion_list(spec, store, inclusion_list, test_steps)
        time_into_slot_ms = second_time_into_slot_ms_fn(spec)
        if time_into_slot_ms is not None:
            _tick_into_slot(spec, store, state.slot, time_into_slot_ms, test_steps)
        yield from add_inclusion_list(spec, store, inclusion_list, test_steps)
        return [inclusion_list]

    return add_inclusion_lists


@with_heze_and_later
@spec_state_test
def test_duplicate_inclusion_list_is_enforced(spec, state):
    """
    Test that receiving the same inclusion list twice is not an equivocation,
    so the inclusion list still constrains the payload.
    """
    with cached_inclusion_list_store(spec):
        store, block_root, test_steps = yield from _run_inclusion_list_scenario(
            spec,
            state,
            _add_duplicate_inclusion_list(lambda spec: None),
            _no_transactions,
        )

    assert not store.payload_inclusion_list_satisfaction[block_root]
    assert spec.get_head(store).payload_status == spec.PAYLOAD_STATUS_EMPTY

    yield "steps", test_steps


@with_heze_and_later
@spec_state_test
def test_duplicate_inclusion_list_after_due_keeps_timeliness(spec, state):
    """
    Test that receiving a timely inclusion list again after the inclusion list
    due does not make it untimely.
    """
    with cached_inclusion_list_store(spec):
        store, block_root, test_steps = yield from _run_inclusion_list_scenario(
            spec,
            state,
            _add_duplicate_inclusion_list(
                lambda spec: (spec.get_inclusion_list_due_ms() + 999) // 1000 * 1000
            ),
            _no_transactions,
        )

    assert not store.payload_inclusion_list_satisfaction[block_root]
    assert spec.get_head(store).payload_status == spec.PAYLOAD_STATUS_EMPTY

    yield "steps", test_steps


#
# Epoch boundary
#


@with_heze_and_later
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_payload_at_epoch_start_uses_previous_epoch_dependent_root(spec, state):
    """
    Test that the payload of the first block of an epoch is checked against the
    inclusion lists of the last slot of the previous epoch, which are keyed by
    the previous epoch's shuffling dependent root.
    """
    with cached_inclusion_list_store(spec):
        store, block_root, block_state, _, test_steps = yield from setup_one_block_store(
            spec, state
        )

        # Advance to the last slot of an epoch whose shuffling dependent root
        # differs from the next epoch's
        epoch = spec.MIN_SEED_LOOKAHEAD + 2
        while block_state.slot < spec.compute_start_slot_at_epoch(epoch) - 1:
            block_root, block_state, _ = yield from _add_next_block(
                spec, store, block_state, test_steps
            )

        inclusion_list = _get_inclusion_list(spec, store, block_state)
        yield from add_inclusion_list(spec, store, inclusion_list, test_steps)

        block_root, state, signed_block = yield from _add_next_block(
            spec, store, block_state, test_steps
        )
        assert spec.compute_epoch_at_slot(state.slot) == epoch
        assert inclusion_list.message.dependent_root != spec.get_shuffling_dependent_root(
            store, block_root, epoch
        )

        envelope = _build_envelope(spec, state, block_root, signed_block, [])
        yield from add_execution_payload(spec, store, envelope, test_steps)
        add_payload_inclusion_list_satisfaction_check(store, block_root, test_steps)

        tick_store_to_slot(spec, store, state.slot + 1, test_steps)
        check_head_against_root(spec, store, block_root)
        output_head_check(spec, store, test_steps)

    assert not store.payload_inclusion_list_satisfaction[block_root]
    assert spec.get_head(store).payload_status == spec.PAYLOAD_STATUS_EMPTY

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
        store, _, block_state, _, test_steps = yield from setup_one_block_store(spec, state)
        yield from _add_timely_inclusion_lists(1)(spec, store, block_state, test_steps)

        parent_root, parent_state, signed_parent = yield from _add_next_block(
            spec, store, block_state, test_steps
        )
        envelope = _build_envelope(spec, parent_state, parent_root, signed_parent, [])
        yield from add_execution_payload(spec, store, envelope, test_steps)
        add_payload_inclusion_list_satisfaction_check(store, parent_root, test_steps)

        # Build a child that claims the parent is FULL
        tick_store_to_slot(spec, store, parent_state.slot + 1, test_steps)
        child_state = parent_state.copy()
        child = build_empty_block_for_next_slot(spec, child_state)
        child.body.signed_execution_payload_bid.message.parent_block_hash = (
            signed_parent.message.body.signed_execution_payload_bid.message.block_hash
        )
        child.body.signed_execution_payload_bid.message.block_hash = spec.Hash32(b"\x42" * 32)
        signed_child = state_transition_and_sign_block(spec, child_state, child)
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
        store, _, block_state, _, test_steps = yield from setup_one_block_store(spec, state)
        yield from _add_timely_inclusion_lists(1)(spec, store, block_state, test_steps)

        block_root, state, signed_block = yield from _add_next_block(
            spec, store, block_state, test_steps
        )
        envelope = _build_envelope(spec, state, block_root, signed_block, [])
        yield from add_execution_payload(spec, store, envelope, test_steps)
        add_payload_inclusion_list_satisfaction_check(store, block_root, test_steps)

        assert not store.payload_inclusion_list_satisfaction[block_root]
        check_head_against_root(spec, store, block_root)
        assert spec.get_head(store).payload_status == spec.PAYLOAD_STATUS_FULL
        output_head_check(spec, store, test_steps)

    yield "steps", test_steps
