from eth_consensus_specs.test.context import (
    spec_state_test,
    with_gloas_and_later,
)
from eth_consensus_specs.test.helpers.block import (
    build_empty_block_for_next_slot,
)
from eth_consensus_specs.test.helpers.fork_choice import (
    add_payload_attestation_message,
    get_genesis_forkchoice_store_and_block,
    on_tick_and_append_step,
    tick_and_add_block,
)
from eth_consensus_specs.test.helpers.keys import privkeys
from eth_consensus_specs.test.helpers.state import (
    state_transition_and_sign_block,
)


def _build_signed_payload_attestation_message(
    spec, state, block_root, validator_index, payload_present=True, blob_data_available=True
):
    """
    Build a signed PayloadAttestationMessage for a given block root and validator.
    """
    data = spec.PayloadAttestationData(
        beacon_block_root=block_root,
        slot=state.slot,
        payload_present=payload_present,
        blob_data_available=blob_data_available,
    )

    domain = spec.get_domain(state, spec.DOMAIN_PTC_ATTESTER, spec.compute_epoch_at_slot(data.slot))
    signing_root = spec.compute_signing_root(data, domain)
    signature = spec.bls.Sign(privkeys[validator_index], signing_root)

    return spec.PayloadAttestationMessage(
        validator_index=validator_index,
        data=data,
        signature=signature,
    )


def _setup_store(spec, state, test_steps):
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block

    current_time = state.slot * (spec.config.SLOT_DURATION_MS // 1000) + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    return store


def _setup_ptc_block(spec, store, state, test_steps):
    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block)
    yield from tick_and_add_block(spec, store, signed_block, test_steps)

    block_root = signed_block.message.hash_tree_root()
    block_state = store.block_states[block_root]
    ptc = spec.get_ptc(block_state, block_state.slot)
    assert len(ptc) > 0

    return block_root, block_state, ptc


def _move_store_to_slot(spec, store, slot, test_steps):
    slot_time = store.genesis_time + slot * (spec.config.SLOT_DURATION_MS // 1000)
    if store.time < slot_time:
        on_tick_and_append_step(spec, store, slot_time, test_steps)


def _setup_test(spec, state):
    test_steps = []
    store = yield from _setup_store(spec, state, test_steps)
    block_root, block_state, ptc = yield from _setup_ptc_block(spec, store, state, test_steps)
    _move_store_to_slot(spec, store, block_state.slot, test_steps)
    return store, block_root, block_state, ptc, test_steps


@with_gloas_and_later
@spec_state_test
def test_on_payload_attestation_duplicate_validator(spec, state):
    """
    Test that a vote from a validator occupying multiple PTC positions is recorded
    at every one of those positions.
    """
    # Force a duplicated validator in the PTC for the next slot
    block_slot = state.slot + 1
    window_idx = spec.SLOTS_PER_EPOCH + block_slot % spec.SLOTS_PER_EPOCH
    state.ptc_window[window_idx][1] = state.ptc_window[window_idx][0]

    store, block_root, block_state, ptc, test_steps = yield from _setup_test(spec, state)

    first_position = 0
    later_position = 1
    validator = ptc[first_position]
    assert ptc[later_position] == validator

    msg = _build_signed_payload_attestation_message(
        spec,
        block_state,
        block_root,
        validator,
        payload_present=True,
        blob_data_available=True,
    )
    yield from add_payload_attestation_message(spec, store, msg, test_steps)

    # Vote landed at both of the validator's positions
    assert store.payload_timeliness_vote[block_root][first_position]
    assert store.payload_data_availability_vote[block_root][first_position]
    assert store.payload_timeliness_vote[block_root][later_position]
    assert store.payload_data_availability_vote[block_root][later_position]

    yield "steps", test_steps


@with_gloas_and_later
@spec_state_test
def test_on_payload_attestation_duplicate_validator_equivocation(spec, state):
    """
    Test that a later vote with different data from a duplicated validator overwrites
    every position the validator occupies (latest-wins applied uniformly).
    """
    # Force a duplicated validator in the PTC for the next slot
    block_slot = state.slot + 1
    window_idx = spec.SLOTS_PER_EPOCH + block_slot % spec.SLOTS_PER_EPOCH
    state.ptc_window[window_idx][1] = state.ptc_window[window_idx][0]

    store, block_root, block_state, ptc, test_steps = yield from _setup_test(spec, state)

    first_position = 0
    later_position = 1
    validator = ptc[first_position]
    assert ptc[later_position] == validator

    # Initial vote: True/True
    msg_initial = _build_signed_payload_attestation_message(
        spec,
        block_state,
        block_root,
        validator,
        payload_present=True,
        blob_data_available=True,
    )
    yield from add_payload_attestation_message(spec, store, msg_initial, test_steps)

    assert store.payload_timeliness_vote[block_root][first_position]
    assert store.payload_data_availability_vote[block_root][first_position]
    assert store.payload_timeliness_vote[block_root][later_position]
    assert store.payload_data_availability_vote[block_root][later_position]

    # Equivocating vote with flipped values
    msg_flipped = _build_signed_payload_attestation_message(
        spec,
        block_state,
        block_root,
        validator,
        payload_present=False,
        blob_data_available=False,
    )
    yield from add_payload_attestation_message(spec, store, msg_flipped, test_steps)

    # Both positions reflect the latest vote
    for position in (first_position, later_position):
        timeliness = store.payload_timeliness_vote[block_root][position]
        availability = store.payload_data_availability_vote[block_root][position]
        assert timeliness is not None and not timeliness
        assert availability is not None and not availability

    yield "steps", test_steps


@with_gloas_and_later
@spec_state_test
def test_on_payload_attestation_message_from_block_with_duplicate_validator(spec, state):
    """
    Test that a PayloadAttestation aggregate included in a block with bits set at
    every position of a duplicated validator updates the vote at all those positions.
    """
    # Force a duplicated validator in the PTC for the next slot
    block_slot = state.slot + 1
    window_idx = spec.SLOTS_PER_EPOCH + block_slot % spec.SLOTS_PER_EPOCH
    state.ptc_window[window_idx][1] = state.ptc_window[window_idx][0]

    store, block_root, block_state, ptc, test_steps = yield from _setup_test(spec, state)

    first_position = 0
    later_position = 1
    validator = ptc[first_position]
    assert ptc[later_position] == validator

    # Build the validator's signed message
    msg = _build_signed_payload_attestation_message(
        spec,
        block_state,
        block_root,
        validator,
        payload_present=True,
        blob_data_available=True,
    )

    # Build a PayloadAttestation aggregate with bits set at both of the validator's positions
    aggregation_bits = spec.Bitvector[spec.PTC_SIZE]()
    aggregation_bits[first_position] = True
    aggregation_bits[later_position] = True

    # FastAggregateVerify checks against one pubkey per set bit, so the signature
    # must be aggregated once per set bit.
    aggregate_sig = spec.bls.Aggregate([msg.signature, msg.signature])

    aggregate = spec.PayloadAttestation(
        aggregation_bits=aggregation_bits,
        data=msg.data,
        signature=aggregate_sig,
    )

    # Build the next block including the aggregate
    next_block = build_empty_block_for_next_slot(spec, state)
    next_block.body.payload_attestations.append(aggregate)
    signed_next_block = state_transition_and_sign_block(spec, state, next_block)

    yield from tick_and_add_block(spec, store, signed_next_block, test_steps)

    # Vote landed at every position the validator occupies
    assert store.payload_timeliness_vote[block_root][first_position]
    assert store.payload_data_availability_vote[block_root][first_position]
    assert store.payload_timeliness_vote[block_root][later_position]
    assert store.payload_data_availability_vote[block_root][later_position]

    yield "steps", test_steps
