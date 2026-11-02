from eth_consensus_specs.test.context import (
    spec_state_test,
    with_heze_and_later,
    with_presets,
)
from eth_consensus_specs.test.helpers.attestations import get_valid_attestation
from eth_consensus_specs.test.helpers.block import (
    build_empty_block,
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
    add_payload_attestation_message,
    add_payload_inclusion_list_satisfaction_check,
    add_payload_vote_checks,
    add_signed_empty_block,
    check_head_against_root,
    on_tick_and_append_step,
    output_head_check,
    setup_genesis_store,
    setup_one_block_store,
    tick_and_add_block,
    tick_and_run_on_attestation,
    tick_store_to_slot,
)
from eth_consensus_specs.test.helpers.inclusion_list import (
    cached_inclusion_list_store,
    get_dependent_root_state,
    get_sample_signed_inclusion_list,
    get_sample_signed_inclusion_list_for_dependent_root,
    get_sample_transactions,
)
from eth_consensus_specs.test.helpers.keys import privkeys
from eth_consensus_specs.test.helpers.state import (
    state_transition_and_sign_block,
    transition_to,
)


def _add_payload(spec, store, state, test_steps, transactions=(), block=None):
    """
    Add ``block``, or else the next empty block, and its payload with
    ``transactions``, and emit the payload's inclusion list satisfaction check.
    """
    if block is None:
        block = build_empty_block_for_next_slot(spec, state)
    # Payloads with different transactions must not share a block hash
    block.body.signed_execution_payload_bid.message.block_hash = spec.Hash32(
        spec.BeaconBlockHeader(
            slot=block.slot,
            parent_root=block.parent_root,
            body_root=spec.Transactions(data=transactions).hash_tree_root(),
        ).hash_tree_root()
    )
    signed_block = state_transition_and_sign_block(spec, state, block)
    yield from tick_and_add_block(spec, store, signed_block, test_steps)
    block_root = signed_block.message.hash_tree_root()
    envelope = build_signed_execution_payload_envelope(
        spec, state, block_root, signed_block
    ).message
    envelope.payload.transactions = spec.Transactions(data=transactions)
    signed_envelope = sign_execution_payload_envelope(spec, state, signed_block, envelope)
    yield from add_execution_payload(spec, store, signed_envelope, test_steps)
    add_payload_inclusion_list_satisfaction_check(store, block_root, test_steps)
    return block_root


def _check_head(spec, store, block_root, payload_status, test_steps):
    check_head_against_root(spec, store, block_root)
    assert spec.get_head(store).payload_status == payload_status
    output_head_check(spec, store, test_steps)


def _check_head_payload_extended(spec, store, block_root, extended, test_steps):
    """
    Tick to the slot after ``block_root`` and check whether fork choice extends its payload.
    """
    tick_store_to_slot(spec, store, store.blocks[block_root].slot + 1, test_steps)
    status = spec.PAYLOAD_STATUS_FULL if extended else spec.PAYLOAD_STATUS_EMPTY
    _check_head(spec, store, block_root, status, test_steps)


def _run_inclusion_list_scenario(spec, state, add_inclusion_lists, satisfied, after_payload=None):
    """
    Add inclusion lists for slot 0 with ``add_inclusion_lists``, which returns the
    payload transactions, add the next block with that payload, run
    ``after_payload`` with the slot 0 state, and check that the payload is
    ``satisfied`` and extended in the next slot only if it is.
    """
    with cached_inclusion_list_store(spec):
        store, test_steps = yield from setup_genesis_store(spec, state)

        inclusion_list_state = state.copy()
        transactions = yield from add_inclusion_lists(spec, store, state, test_steps)
        block_root = yield from _add_payload(spec, store, state, test_steps, transactions)
        if after_payload is not None:
            yield from after_payload(spec, store, inclusion_list_state, block_root, test_steps)
            add_payload_inclusion_list_satisfaction_check(store, block_root, test_steps)

        assert store.payload_inclusion_list_satisfaction[block_root] == satisfied
        _check_head_payload_extended(spec, store, block_root, satisfied, test_steps)

    yield "steps", test_steps


def _get_inclusion_list(spec, store, state, committee_position=0, slot=None):
    if slot is None:
        slot = state.slot
    committee = spec.get_inclusion_list_committee(state, slot)
    return get_sample_signed_inclusion_list(
        spec, store, state, slot=slot, validator_index=committee[committee_position]
    )


def _tick_into_slot_0(spec, store, time_into_slot_ms, test_steps):
    # Test vectors express ticks in whole seconds
    assert time_into_slot_ms % 1000 == 0
    on_tick_and_append_step(spec, store, store.genesis_time_ms + time_into_slot_ms, test_steps)


def _last_second_before_due_ms(spec):
    return (spec.get_inclusion_list_due_ms() - 1) // 1000 * 1000


def _first_second_after_due_ms(spec):
    return (spec.get_inclusion_list_due_ms() // 1000 + 1) * 1000


def _next_slot_ms(spec):
    return spec.config.SLOT_DURATION_MS


#
# Satisfaction
#


def _add_timely_inclusion_lists(count, included=()):
    """
    Add timely inclusion lists from the first ``count`` committee members and
    return the transactions of those at the ``included`` positions.
    """

    def add_inclusion_lists(spec, store, state, test_steps):
        inclusion_lists = [_get_inclusion_list(spec, store, state, i) for i in range(count)]
        for inclusion_list in inclusion_lists:
            yield from add_inclusion_list(spec, store, inclusion_list, test_steps)
        return [tx for i in included for tx in inclusion_lists[i].message.transactions]

    return add_inclusion_lists


@with_heze_and_later
@spec_state_test
def test_payload_satisfies_inclusion_list(spec, state):
    """
    Test that a payload containing every timely inclusion list transaction is
    satisfied and extended in the next slot.
    """
    yield from _run_inclusion_list_scenario(
        spec, state, _add_timely_inclusion_lists(1, included=[0]), satisfied=True
    )


@with_heze_and_later
@spec_state_test
def test_payload_missing_inclusion_list_transactions(spec, state):
    """
    Test that a payload missing a timely inclusion list transaction remains valid
    but is not extended in the next slot.
    """
    yield from _run_inclusion_list_scenario(
        spec, state, _add_timely_inclusion_lists(1), satisfied=False
    )


@with_heze_and_later
@spec_state_test
def test_payload_satisfies_only_one_of_two_inclusion_lists(spec, state):
    """
    Test that a payload containing the transactions of only the first of two
    timely inclusion lists is not extended in the next slot.
    """
    yield from _run_inclusion_list_scenario(
        spec, state, _add_timely_inclusion_lists(2, included=[0]), satisfied=False
    )


@with_heze_and_later
@spec_state_test
def test_payload_satisfies_only_second_of_two_inclusion_lists(spec, state):
    """
    Test that a payload containing the transactions of only the second of two
    timely inclusion lists is not extended in the next slot.
    """
    yield from _run_inclusion_list_scenario(
        spec, state, _add_timely_inclusion_lists(2, included=[1]), satisfied=False
    )


#
# Inclusion list slot
#


def _add_inclusion_list_for_next_slot(spec, store, state, test_steps):
    """
    Add a timely inclusion list for slot 1, the slot of the block, and return no
    payload transactions.
    """
    tick_store_to_slot(spec, store, state.slot + 1, test_steps)
    inclusion_list = _get_inclusion_list(spec, store, state, slot=state.slot + 1)
    yield from add_inclusion_list(spec, store, inclusion_list, test_steps)
    return []


@with_heze_and_later
@spec_state_test
def test_inclusion_lists_for_block_slot_are_not_enforced(spec, state):
    """
    Test that timely inclusion lists for the block's own slot do not constrain
    its payload.
    """
    yield from _run_inclusion_list_scenario(
        spec, state, _add_inclusion_list_for_next_slot, satisfied=True
    )


def _add_inclusion_lists_around_skipped_slot(include_skipped_slot):
    """
    Add a timely inclusion list for slot 0 and one for the skipped slot 1, so the
    next block is at slot 2, and return the transactions of the skipped slot's
    inclusion list if ``include_skipped_slot``, else those of slot 0's.
    """

    def add_inclusion_lists(spec, store, state, test_steps):
        parent_slot_inclusion_list = _get_inclusion_list(spec, store, state)
        yield from add_inclusion_list(spec, store, parent_slot_inclusion_list, test_steps)
        spec.process_slots(state, state.slot + 1)
        tick_store_to_slot(spec, store, state.slot, test_steps)
        skipped_slot_inclusion_list = _get_inclusion_list(spec, store, state)
        yield from add_inclusion_list(spec, store, skipped_slot_inclusion_list, test_steps)
        included = (
            skipped_slot_inclusion_list if include_skipped_slot else parent_slot_inclusion_list
        )
        return included.message.transactions

    return add_inclusion_lists


@with_heze_and_later
@spec_state_test
def test_skipped_slot_inclusion_lists_are_enforced(spec, state):
    """
    Test that the payload of a block after a skipped slot is constrained by the
    inclusion lists of the skipped slot.
    """
    yield from _run_inclusion_list_scenario(
        spec,
        state,
        _add_inclusion_lists_around_skipped_slot(include_skipped_slot=False),
        satisfied=False,
    )


@with_heze_and_later
@spec_state_test
def test_parent_slot_inclusion_lists_are_not_enforced_after_skipped_slot(spec, state):
    """
    Test that the payload of a block after a skipped slot is not constrained by
    the inclusion lists of its parent's slot.
    """
    yield from _run_inclusion_list_scenario(
        spec,
        state,
        _add_inclusion_lists_around_skipped_slot(include_skipped_slot=True),
        satisfied=True,
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
        spec, state, _add_inclusion_list_at(_next_slot_ms), satisfied=True
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
def test_equivocation_in_next_slot_before_payload_cancels_inclusion_list(spec, state):
    """
    Test that an equivocating inclusion list received in the next slot, before
    the payload, cancels the validator's timely inclusion list.
    """
    yield from _run_inclusion_list_scenario(
        spec,
        state,
        _add_inclusion_list_twice(equivocate=True, second_at=_next_slot_ms),
        satisfied=True,
    )


def _add_late_inclusion_list(spec, store, state, block_root, test_steps):
    """
    Add an inclusion list for slot 0 from the first committee member after the payload.
    """
    yield from add_inclusion_list(spec, store, _get_inclusion_list(spec, store, state), test_steps)


@with_heze_and_later
@spec_state_test
def test_equivocation_after_payload_does_not_change_satisfaction(spec, state):
    """
    Test that an equivocating inclusion list received after the payload does not
    make the unsatisfied payload satisfied.
    """
    yield from _run_inclusion_list_scenario(
        spec,
        state,
        _add_timely_inclusion_lists(1),
        satisfied=False,
        after_payload=_add_late_inclusion_list,
    )


def _add_equivocating_and_honest_inclusion_lists(spec, store, state, test_steps):
    """
    Add an inclusion list from one validator, then a timely inclusion list from
    another validator, then an equivocating inclusion list from the first, and
    return no payload transactions.
    """
    inclusion_list_1 = _get_inclusion_list(spec, store, state)
    honest_inclusion_list = _get_inclusion_list(spec, store, state, committee_position=1)
    inclusion_list_2 = _get_inclusion_list(spec, store, state)
    for inclusion_list in [inclusion_list_1, honest_inclusion_list, inclusion_list_2]:
        yield from add_inclusion_list(spec, store, inclusion_list, test_steps)
    return []


@with_heze_and_later
@spec_state_test
def test_equivocation_does_not_cancel_other_inclusion_lists(spec, state):
    """
    Test that an equivocating validator does not cancel the timely inclusion
    list of another validator received in between its inclusion lists.
    """
    yield from _run_inclusion_list_scenario(
        spec,
        state,
        _add_equivocating_and_honest_inclusion_lists,
        satisfied=False,
    )


def _add_reordered_inclusion_lists(spec, store, state, test_steps):
    """
    Add two inclusion lists from the same validator with the same transactions
    in reverse order, and return no payload transactions.
    """
    transactions = get_sample_transactions(spec, max_transaction_count=2)
    reordered = spec.Transactions(data=list(reversed(transactions)))
    assert transactions != reordered
    validator_index = spec.get_inclusion_list_committee(state, state.slot)[0]
    for txs in [transactions, reordered]:
        inclusion_list = get_sample_signed_inclusion_list(
            spec, store, state, validator_index=validator_index, transactions=txs
        )
        yield from add_inclusion_list(spec, store, inclusion_list, test_steps)
    return []


@with_heze_and_later
@spec_state_test
def test_reordered_inclusion_list_is_an_equivocation(spec, state):
    """
    Test that a validator publishing the same transactions in a different order
    equivocates, so neither inclusion list is enforced.
    """
    yield from _run_inclusion_list_scenario(
        spec, state, _add_reordered_inclusion_lists, satisfied=True
    )


@with_heze_and_later
@spec_state_test
def test_duplicate_inclusion_list_after_due_keeps_timeliness(spec, state):
    """
    Test that receiving a timely inclusion list again after the inclusion list
    due is neither an equivocation nor makes it untimely.
    """
    yield from _run_inclusion_list_scenario(
        spec,
        state,
        _add_inclusion_list_twice(equivocate=False, second_at=_first_second_after_due_ms),
        satisfied=False,
    )


def _add_inclusion_lists_in_two_epochs(spec, store, state, test_steps):
    """
    Add timely inclusion lists from one validator for slot 0 and for a slot of
    epoch 1, so the next block follows that slot, and return no payload
    transactions.
    """
    first_committee = spec.get_inclusion_list_committee(state, state.slot)
    second_slot, validator_index = next(
        (slot, validator_index)
        for slot in range(spec.SLOTS_PER_EPOCH, 2 * spec.SLOTS_PER_EPOCH - 1)
        for validator_index in spec.get_inclusion_list_committee(state, slot)
        if validator_index in first_committee
    )
    first = get_sample_signed_inclusion_list(spec, store, state, validator_index=validator_index)
    second = get_sample_signed_inclusion_list(
        spec, store, state, slot=second_slot, validator_index=validator_index
    )
    assert first.message.dependent_root == second.message.dependent_root
    yield from add_inclusion_list(spec, store, first, test_steps)
    tick_store_to_slot(spec, store, second_slot, test_steps)
    yield from add_inclusion_list(spec, store, second, test_steps)
    spec.process_slots(state, second_slot)
    return []


@with_heze_and_later
@spec_state_test
def test_validator_in_committees_of_two_epochs_is_not_an_equivocator(spec, state):
    """
    Test that a validator publishing inclusion lists for slots of two epochs
    with the same dependent root does not equivocate.
    """
    yield from _run_inclusion_list_scenario(
        spec, state, _add_inclusion_lists_in_two_epochs, satisfied=False
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
# Forks
#


def _setup_forked_dependent_roots(spec, state):
    """
    Build two forks with different shuffling dependent roots for epoch
    ``MIN_SEED_LOOKAHEAD + 1``: fork A has a block at the shuffling dependent
    slot and fork B skips it. Both forks have a block after the dependent slot,
    at different slots so that no proposer equivocates.
    Return the first slot of that epoch and each fork's state and dependent root.
    """
    store, test_steps = yield from setup_genesis_store(spec, state)

    epoch = spec.MIN_SEED_LOOKAHEAD + 1
    dependent_slot = spec.compute_start_slot_at_epoch(epoch - spec.MIN_SEED_LOOKAHEAD) - 1
    while state.slot < dependent_slot - 1:
        fork_root, _, _ = yield from add_signed_empty_block(spec, store, state, test_steps)
    forks = []
    for fork_slots in [[dependent_slot, dependent_slot + 2], [dependent_slot + 1]]:
        fork_state = state.copy()
        dependent_root = fork_root
        for slot in fork_slots:
            block = build_empty_block(spec, fork_state, slot=slot)
            signed_block = state_transition_and_sign_block(spec, fork_state, block)
            yield from tick_and_add_block(spec, store, signed_block, test_steps)
            if slot == dependent_slot:
                dependent_root = block.hash_tree_root()
        assert dependent_root == spec.get_shuffling_dependent_root(
            store, block.hash_tree_root(), epoch
        )
        forks.append((fork_state, dependent_root))

    return store, spec.compute_start_slot_at_epoch(epoch), forks, test_steps


def _get_committee(spec, store, slot, dependent_root):
    state = get_dependent_root_state(spec, store, slot, dependent_root)
    return spec.get_inclusion_list_committee(state, slot)


def _add_fork_payloads(spec, store, slot, forks, transactions, test_steps):
    """
    Add the block at ``slot`` and its payload with the matching ``transactions``
    on each fork, then tick to the next slot.
    """
    roots = []
    for (fork_state, _), fork_transactions in zip(forks, transactions, strict=True):
        block = build_empty_block(spec, fork_state, slot=slot)
        roots.append(
            (yield from _add_payload(spec, store, fork_state, test_steps, fork_transactions, block))
        )
    tick_store_to_slot(spec, store, slot + 1, test_steps)
    output_head_check(spec, store, test_steps)
    return roots


@with_heze_and_later
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_forked_dependent_roots_have_independent_satisfaction(spec, state):
    """
    Test that each fork's payload is checked only against the inclusion lists of
    its own shuffling dependent root.
    """
    with cached_inclusion_list_store(spec):
        store, slot, forks, test_steps = yield from _setup_forked_dependent_roots(spec, state)
        (_, dependent_root_a), (_, dependent_root_b) = forks
        tick_store_to_slot(spec, store, slot, test_steps)
        committee_a = _get_committee(spec, store, slot, dependent_root_a)
        committee_b = _get_committee(spec, store, slot, dependent_root_b)

        # Each validator is only in the committee of its own fork's shuffling
        inclusion_list_a = get_sample_signed_inclusion_list_for_dependent_root(
            spec,
            store,
            slot,
            dependent_root_a,
            validator_index=next(i for i in committee_a if i not in committee_b),
        )
        inclusion_list_b = get_sample_signed_inclusion_list_for_dependent_root(
            spec,
            store,
            slot,
            dependent_root_b,
            validator_index=next(i for i in committee_b if i not in committee_a),
        )
        yield from add_inclusion_list(spec, store, inclusion_list_a, test_steps)
        yield from add_inclusion_list(spec, store, inclusion_list_b, test_steps)

        # Both forks get the same payload, with only fork A's transactions
        transactions = inclusion_list_a.message.transactions
        root_a, root_b = yield from _add_fork_payloads(
            spec, store, slot + 1, forks, [transactions, transactions], test_steps
        )

    assert (
        store.payloads[root_a].payload.transactions == store.payloads[root_b].payload.transactions
    )
    assert store.payload_inclusion_list_satisfaction[root_a]
    assert not store.payload_inclusion_list_satisfaction[root_b]

    yield "steps", test_steps


@with_heze_and_later
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_same_validator_under_two_dependent_roots_is_not_an_equivocator(spec, state):
    """
    Test that a validator publishing different inclusion lists for the same slot
    under two dependent roots does not equivocate.
    """
    with cached_inclusion_list_store(spec):
        store, slot, forks, test_steps = yield from _setup_forked_dependent_roots(spec, state)
        (_, dependent_root_a), (_, dependent_root_b) = forks
        # Use the first slot of the epoch whose committees under both dependent
        # roots share a validator
        slot, validator_index = next(
            (slot + offset, validator_index)
            for offset in range(spec.SLOTS_PER_EPOCH - 1)
            for validator_index in sorted(
                set(_get_committee(spec, store, slot + offset, dependent_root_a))
                & set(_get_committee(spec, store, slot + offset, dependent_root_b))
            )
        )
        tick_store_to_slot(spec, store, slot, test_steps)
        inclusion_list_a, inclusion_list_b = [
            get_sample_signed_inclusion_list_for_dependent_root(
                spec, store, slot, dependent_root, validator_index=validator_index
            )
            for dependent_root in [dependent_root_a, dependent_root_b]
        ]
        yield from add_inclusion_list(spec, store, inclusion_list_a, test_steps)
        yield from add_inclusion_list(spec, store, inclusion_list_b, test_steps)

        # Fork A misses its transactions, fork B includes its own
        root_a, root_b = yield from _add_fork_payloads(
            spec,
            store,
            slot + 1,
            forks,
            [[], inclusion_list_b.message.transactions],
            test_steps,
        )

    assert not store.payload_inclusion_list_satisfaction[root_a]
    assert store.payload_inclusion_list_satisfaction[root_b]

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
        store, test_steps = yield from setup_genesis_store(spec, state)

        yield from _add_timely_inclusion_lists(1)(spec, store, state, test_steps)
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
        _check_head(spec, store, parent_root, spec.PAYLOAD_STATUS_EMPTY, test_steps)

    yield "steps", test_steps


@with_heze_and_later
@spec_state_test
def test_satisfied_child_of_unsatisfied_parent_is_head(spec, state):
    """
    Test that a payload's satisfaction is not inherited from its unsatisfied
    parent, so fork choice extends a satisfied child on the empty parent in the
    next slot.
    """
    with cached_inclusion_list_store(spec):
        store, test_steps = yield from setup_genesis_store(spec, state)

        yield from _add_timely_inclusion_lists(1)(spec, store, state, test_steps)
        parent_root = yield from _add_payload(spec, store, state, test_steps)

        transactions = yield from _add_timely_inclusion_lists(1, included=[0])(
            spec, store, state, test_steps
        )
        child_root = yield from _add_payload(spec, store, state, test_steps, transactions)

        assert not spec.is_parent_node_full(store, store.blocks[child_root])
        assert not store.payload_inclusion_list_satisfaction[parent_root]
        assert store.payload_inclusion_list_satisfaction[child_root]

        # Apply in slot 3 an attestation from slot 2 for the child
        attestation = get_valid_attestation(spec, state, slot=state.slot, signed=True)
        assert attestation.data.beacon_block_root == child_root
        yield from tick_and_run_on_attestation(spec, store, attestation, test_steps)
        assert spec.get_current_slot(store) == state.slot + 1

        _check_head(spec, store, child_root, spec.PAYLOAD_STATUS_FULL, test_steps)

    yield "steps", test_steps


@with_heze_and_later
@spec_state_test
def test_unsatisfied_payload_is_head_in_its_own_slot(spec, state):
    """
    Test that an unsatisfied payload is the head in its own slot, because
    inclusion list satisfaction only decides whether the next slot extends it.
    """
    with cached_inclusion_list_store(spec):
        store, test_steps = yield from setup_genesis_store(spec, state)

        yield from _add_timely_inclusion_lists(1)(spec, store, state, test_steps)
        block_root = yield from _add_payload(spec, store, state, test_steps)

        assert not store.payload_inclusion_list_satisfaction[block_root]
        _check_head(spec, store, block_root, spec.PAYLOAD_STATUS_FULL, test_steps)

    yield "steps", test_steps


def _add_ptc_votes(spec, store, state, block_root, test_steps):
    """
    Add a message from every PTC member voting the payload present and its data available.
    """
    block_state = store.block_states[block_root]
    for validator_index in sorted(set(spec.get_ptc(block_state, block_state.slot))):
        message = spec.PayloadAttestationMessage(
            validator_index=validator_index,
            data=spec.PayloadAttestationData(
                beacon_block_root=block_root,
                slot=block_state.slot,
                payload_present=True,
                blob_data_available=True,
            ),
        )
        message.signature = spec.get_payload_attestation_message_signature(
            block_state, message, privkeys[validator_index]
        )
        yield from add_payload_attestation_message(spec, store, message, test_steps)
    assert spec.payload_timeliness(store, block_root, timely=True)
    assert spec.payload_data_availability(store, block_root, available=True)
    add_payload_vote_checks(store, block_root, test_steps)


@with_heze_and_later
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_ptc_votes_do_not_override_unsatisfied_payload(spec, state):
    """
    Test that a PTC supermajority voting the payload present and its data
    available does not make fork choice extend an unsatisfied payload.
    """
    yield from _run_inclusion_list_scenario(
        spec, state, _add_timely_inclusion_lists(1), satisfied=False, after_payload=_add_ptc_votes
    )


@with_heze_and_later
@spec_state_test
def test_attestations_for_full_extend_unsatisfied_payload(spec, state):
    """
    Test that attestations voting full for the block of an unsatisfied payload
    outweigh an empty vote and make fork choice extend that payload after the
    decision slot.
    """
    with cached_inclusion_list_store(spec):
        store, test_steps = yield from setup_genesis_store(spec, state)

        yield from _add_timely_inclusion_lists(1)(spec, store, state, test_steps)
        block_root = yield from _add_payload(spec, store, state, test_steps)
        assert not store.payload_inclusion_list_satisfaction[block_root]

        # Apply in slot 3 attestations from slot 2: one committee member votes
        # empty, then the rest of the committee votes full
        transition_to(spec, state, state.slot + 1)
        for payload_index, participants, payload_status in [
            (0, lambda committee: {min(committee)}, spec.PAYLOAD_STATUS_EMPTY),
            (1, lambda committee: set(committee) - {min(committee)}, spec.PAYLOAD_STATUS_FULL),
        ]:
            attestation = get_valid_attestation(
                spec,
                state,
                slot=state.slot,
                payload_index=payload_index,
                filter_participant_set=participants,
                signed=True,
            )
            assert attestation.data.beacon_block_root == block_root
            yield from tick_and_run_on_attestation(spec, store, attestation, test_steps)
            assert spec.get_current_slot(store) == state.slot + 1
            _check_head(spec, store, block_root, payload_status, test_steps)

    yield "steps", test_steps
