from eth_consensus_specs.test.context import (
    always_bls,
    spec_state_test,
    with_gloas_and_later,
)
from eth_consensus_specs.test.helpers.fork_choice import (
    add_proposer_slashing,
    on_tick_and_append_step,
    output_store_checks,
    setup_one_block_store,
    tick_store_to_slot,
)
from eth_consensus_specs.test.helpers.proposer_slashings import (
    get_valid_proposer_slashing,
)


def _equivocating_roots(proposer_slashing):
    return {
        proposer_slashing.signed_header_1.message.hash_tree_root(),
        proposer_slashing.signed_header_2.message.hash_tree_root(),
    }


def _tick_past_payload_attestation_due(spec, store, slot, test_steps):
    """
    Tick the store to just past the payload attestation deadline of ``slot``.
    """
    slot_start = store.genesis_time + slot * spec.config.SLOT_DURATION_MS // 1000
    late_time = slot_start + spec.get_payload_attestation_due_ms() // 1000 + 1
    if store.time < late_time:
        on_tick_and_append_step(spec, store, late_time, test_steps)


def _setup_test(spec, state):
    store, _, block_state, _, test_steps = yield from setup_one_block_store(spec, state)
    proposer_slashing = get_valid_proposer_slashing(
        spec, block_state, slot=block_state.slot, signed_1=True, signed_2=True
    )
    # The equivocating blocks are unknown to the store, which is the whole point
    # of the handler
    assert _equivocating_roots(proposer_slashing).isdisjoint(store.blocks)
    return store, block_state, proposer_slashing, test_steps


def _assert_recorded(spec, store, proposer_slashing, slot, is_timely):
    roots = _equivocating_roots(proposer_slashing)
    assert set(store.equivocating_proposals) == roots
    for root in roots:
        proposal = store.equivocating_proposals[root]
        assert proposal.slot == slot
        assert proposal.proposer_index == proposer_slashing.signed_header_1.message.proposer_index
        assert proposal.is_timely == is_timely
    assert roots.isdisjoint(store.blocks)


@with_gloas_and_later
@spec_state_test
def test_on_proposer_slashing_timely(spec, state):
    """
    A proposer slashing received before the payload attestation deadline of the
    equivocating slot records both block roots as timely, so the equivocation
    can suppress proposer boost.
    """
    store, block_state, proposer_slashing, test_steps = yield from _setup_test(spec, state)

    yield from add_proposer_slashing(spec, store, proposer_slashing, test_steps)

    _assert_recorded(spec, store, proposer_slashing, block_state.slot, is_timely=True)

    output_store_checks(spec, store, test_steps)
    yield "steps", test_steps


@with_gloas_and_later
@spec_state_test
def test_on_proposer_slashing_late(spec, state):
    """
    A proposer slashing received after the payload attestation deadline of the
    equivocating slot is recorded as untimely, so the equivocation does not
    suppress proposer boost.
    """
    store, block_state, proposer_slashing, test_steps = yield from _setup_test(spec, state)

    _tick_past_payload_attestation_due(spec, store, block_state.slot, test_steps)
    yield from add_proposer_slashing(spec, store, proposer_slashing, test_steps)

    _assert_recorded(spec, store, proposer_slashing, block_state.slot, is_timely=False)

    output_store_checks(spec, store, test_steps)
    yield "steps", test_steps


@with_gloas_and_later
@spec_state_test
def test_on_proposer_slashing_previous_slot(spec, state):
    """
    A proposer slashing for an earlier slot is recorded as untimely, whatever the
    time into the current slot.
    """
    store, block_state, proposer_slashing, test_steps = yield from _setup_test(spec, state)

    tick_store_to_slot(spec, store, block_state.slot + 1, test_steps)
    yield from add_proposer_slashing(spec, store, proposer_slashing, test_steps)

    _assert_recorded(spec, store, proposer_slashing, block_state.slot, is_timely=False)

    output_store_checks(spec, store, test_steps)
    yield "steps", test_steps


@with_gloas_and_later
@spec_state_test
def test_on_proposer_slashing_duplicate_keeps_first_timeliness(spec, state):
    """
    Re-receiving a slashing after the payload attestation deadline must not
    downgrade the timeliness recorded on its first arrival.
    """
    store, block_state, proposer_slashing, test_steps = yield from _setup_test(spec, state)

    yield from add_proposer_slashing(spec, store, proposer_slashing, test_steps)
    _assert_recorded(spec, store, proposer_slashing, block_state.slot, is_timely=True)

    _tick_past_payload_attestation_due(spec, store, block_state.slot, test_steps)
    yield from add_proposer_slashing(spec, store, proposer_slashing, test_steps)
    _assert_recorded(spec, store, proposer_slashing, block_state.slot, is_timely=True)

    output_store_checks(spec, store, test_steps)
    yield "steps", test_steps


@with_gloas_and_later
@spec_state_test
def test_on_proposer_slashing_slot_mismatch(spec, state):
    """
    Test that headers from different slots are rejected.
    """
    store, _, proposer_slashing, test_steps = yield from _setup_test(spec, state)

    proposer_slashing.signed_header_2.message.slot += 1

    yield from add_proposer_slashing(spec, store, proposer_slashing, test_steps, valid=False)

    assert len(store.equivocating_proposals) == 0

    output_store_checks(spec, store, test_steps)
    yield "steps", test_steps


@with_gloas_and_later
@spec_state_test
def test_on_proposer_slashing_proposer_index_mismatch(spec, state):
    """
    Test that headers from different proposers are rejected.
    """
    store, _, proposer_slashing, test_steps = yield from _setup_test(spec, state)

    proposer_slashing.signed_header_2.message.proposer_index += 1

    yield from add_proposer_slashing(spec, store, proposer_slashing, test_steps, valid=False)

    assert len(store.equivocating_proposals) == 0

    output_store_checks(spec, store, test_steps)
    yield "steps", test_steps


@with_gloas_and_later
@spec_state_test
def test_on_proposer_slashing_identical_headers(spec, state):
    """
    Test that a slashing with two identical headers is rejected, since it does
    not prove an equivocation.
    """
    store, _, proposer_slashing, test_steps = yield from _setup_test(spec, state)

    proposer_slashing.signed_header_2 = proposer_slashing.signed_header_1.copy()

    yield from add_proposer_slashing(spec, store, proposer_slashing, test_steps, valid=False)

    assert len(store.equivocating_proposals) == 0

    output_store_checks(spec, store, test_steps)
    yield "steps", test_steps


@with_gloas_and_later
@spec_state_test
def test_on_proposer_slashing_unknown_proposer_index(spec, state):
    """
    Test that a slashing naming a proposer that does not exist in the justified
    state is rejected.
    """
    store, _, proposer_slashing, test_steps = yield from _setup_test(spec, state)

    justified_state = store.block_states[store.justified_checkpoint.root]
    unknown_index = spec.ValidatorIndex(len(justified_state.validators))
    proposer_slashing.signed_header_1.message.proposer_index = unknown_index
    proposer_slashing.signed_header_2.message.proposer_index = unknown_index

    yield from add_proposer_slashing(spec, store, proposer_slashing, test_steps, valid=False)

    assert len(store.equivocating_proposals) == 0

    output_store_checks(spec, store, test_steps)
    yield "steps", test_steps


@with_gloas_and_later
@spec_state_test
@always_bls
def test_on_proposer_slashing_invalid_signature(spec, state):
    """
    Test that a slashing with an unsigned header is rejected.
    """
    store, block_state, _, test_steps = yield from _setup_test(spec, state)

    proposer_slashing = get_valid_proposer_slashing(
        spec, block_state, slot=block_state.slot, signed_1=True, signed_2=False
    )

    yield from add_proposer_slashing(spec, store, proposer_slashing, test_steps, valid=False)

    assert len(store.equivocating_proposals) == 0

    output_store_checks(spec, store, test_steps)
    yield "steps", test_steps
