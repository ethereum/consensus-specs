from eth_consensus_specs.test.context import (
    spec_state_test,
    with_gloas_and_later,
)
from eth_consensus_specs.test.helpers.block import (
    build_empty_block_for_next_slot,
)
from eth_consensus_specs.test.helpers.fork_choice import (
    add_payload_attestation_message,
    add_payload_vote_checks,
    get_genesis_forkchoice_store_and_block,
    on_tick_and_append_step,
    tick_and_add_block,
)
from eth_consensus_specs.test.helpers.keys import privkeys
from eth_consensus_specs.test.helpers.state import (
    state_transition_and_sign_block,
)


def _build_signed_payload_attestation_message(
    spec,
    state,
    block_root,
    validator_index,
    payload_present=True,
    blob_data_available=True,
    slot=None,
):
    """
    Build a signed PayloadAttestationMessage for a given block root and validator.
    """
    if slot is None:
        slot = state.slot
    data = spec.PayloadAttestationData(
        beacon_block_root=block_root,
        slot=slot,
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


def _move_store_to_slot(spec, store, slot, test_steps):
    slot_time = store.genesis_time + slot * (spec.config.SLOT_DURATION_MS // 1000)
    if store.time < slot_time:
        on_tick_and_append_step(spec, store, slot_time, test_steps)


def _setup_test(spec, state):
    test_steps = []

    # Build genesis store
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block
    current_time = state.slot * (spec.config.SLOT_DURATION_MS // 1000) + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)

    # Apply one block at slot 1
    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block)
    yield from tick_and_add_block(spec, store, signed_block, test_steps)
    block_root = signed_block.message.hash_tree_root()
    block_state = store.block_states[block_root]
    ptc = spec.get_ptc(block_state, block_state.slot)
    assert len(ptc) > 0

    _move_store_to_slot(spec, store, block_state.slot, test_steps)
    return store, block_root, block_state, ptc, test_steps


@with_gloas_and_later
@spec_state_test
def test_on_payload_attestation_message_unknown_block_root(spec, state):
    """
    Test that messages for an unknown beacon_block_root are rejected.
    """
    store, block_root, block_state, ptc, test_steps = yield from _setup_test(spec, state)

    # Sign the message over an unknown block root
    unknown_root = spec.Root(b"\xff" * 32)
    ptc_message = _build_signed_payload_attestation_message(
        spec,
        block_state,
        unknown_root,
        ptc[0],
        payload_present=True,
    )

    yield from add_payload_attestation_message(
        spec,
        store,
        ptc_message,
        test_steps,
        valid=False,
    )

    # Vote arrays for the known block must remain at their default values
    assert all(v == None for v in store.payload_timeliness_vote[block_root])
    assert all(v == None for v in store.payload_data_availability_vote[block_root])
    add_payload_vote_checks(store, block_root, test_steps)

    yield "steps", test_steps


@with_gloas_and_later
@spec_state_test
def test_on_payload_attestation_message_slot_mismatch(spec, state):
    """
    Test that a message whose slot doesn't match the block's slot is dropped without error.
    """
    store, block_root, block_state, ptc, test_steps = yield from _setup_test(spec, state)

    # Build message signed over a mismatching slot
    ptc_message = _build_signed_payload_attestation_message(
        spec,
        block_state,
        block_root,
        ptc[0],
        payload_present=True,
        slot=spec.Slot(block_state.slot + 1),
    )

    # Spec function runs without error but returns early on the slot mismatch
    yield from add_payload_attestation_message(spec, store, ptc_message, test_steps)

    # Vote arrays must remain at their default values
    assert all(v == None for v in store.payload_timeliness_vote[block_root])
    assert all(v == None for v in store.payload_data_availability_vote[block_root])
    add_payload_vote_checks(store, block_root, test_steps)

    yield "steps", test_steps


@with_gloas_and_later
@spec_state_test
def test_on_payload_attestation_message_not_ptc_member(spec, state):
    """
    Test that a message from a validator outside the PTC is rejected.
    """
    store, block_root, block_state, ptc, test_steps = yield from _setup_test(spec, state)

    # Pick a validator outside the PTC
    ptc_set = set(ptc)
    non_ptc_member = next(i for i in range(len(state.validators)) if i not in ptc_set)
    ptc_message = _build_signed_payload_attestation_message(
        spec,
        block_state,
        block_root,
        non_ptc_member,
        payload_present=True,
    )

    yield from add_payload_attestation_message(
        spec,
        store,
        ptc_message,
        test_steps,
        valid=False,
    )

    # Assert rejected message didn't mutate the block vote arrays
    assert all(v == None for v in store.payload_timeliness_vote[block_root])
    assert all(v == None for v in store.payload_data_availability_vote[block_root])
    add_payload_vote_checks(store, block_root, test_steps)

    yield "steps", test_steps


@with_gloas_and_later
@spec_state_test
def test_on_payload_attestation_message_current_slot_and_signature(spec, state):
    """
    Test that current slot and signature checks reject invalid messages.
    """
    store, block_root, block_state, ptc, test_steps = yield from _setup_test(spec, state)

    # Bad signature
    invalid_sig_msg = _build_signed_payload_attestation_message(
        spec,
        block_state,
        block_root,
        ptc[0],
        payload_present=True,
    )
    invalid_sig_msg.signature = spec.BLSSignature()
    yield from add_payload_attestation_message(
        spec,
        store,
        invalid_sig_msg,
        test_steps,
        valid=False,
    )

    # Vote arrays must remain at their default values
    assert all(v == None for v in store.payload_timeliness_vote[block_root])
    assert all(v == None for v in store.payload_data_availability_vote[block_root])
    add_payload_vote_checks(store, block_root, test_steps)

    # Valid signature, stale slot
    valid_msg = _build_signed_payload_attestation_message(
        spec,
        block_state,
        block_root,
        ptc[0],
        payload_present=True,
    )
    _move_store_to_slot(spec, store, block_state.slot + 1, test_steps)
    yield from add_payload_attestation_message(
        spec,
        store,
        valid_msg,
        test_steps,
        valid=False,
    )

    # Rejected message must not partially mutate vote arrays
    assert all(v == None for v in store.payload_timeliness_vote[block_root])
    assert all(v == None for v in store.payload_data_availability_vote[block_root])
    add_payload_vote_checks(store, block_root, test_steps)

    yield "steps", test_steps


@with_gloas_and_later
@spec_state_test
def test_on_payload_attestation_message_valid(spec, state):
    """
    Test that valid messages update attestations.
    """
    store, block_root, block_state, ptc, test_steps = yield from _setup_test(spec, state)

    # Initial state: no votes recorded for this block
    assert all(v == None for v in store.payload_timeliness_vote[block_root])
    assert all(v == None for v in store.payload_data_availability_vote[block_root])

    ptc_member = ptc[0]
    voter_positions = [i for i, v in enumerate(ptc) if v == ptc_member]
    other_positions = [i for i in range(len(ptc)) if i not in voter_positions]

    # Attest both values
    msg_1 = _build_signed_payload_attestation_message(
        spec,
        block_state,
        block_root,
        ptc_member,
        payload_present=True,
        blob_data_available=True,
    )
    yield from add_payload_attestation_message(spec, store, msg_1, test_steps)

    for i in voter_positions:
        assert store.payload_timeliness_vote[block_root][i] == True
        assert store.payload_data_availability_vote[block_root][i] == True
    for i in other_positions:
        assert store.payload_timeliness_vote[block_root][i] == None
        assert store.payload_data_availability_vote[block_root][i] == None
    add_payload_vote_checks(store, block_root, test_steps)

    # Re-vote with both fields False
    msg_2 = _build_signed_payload_attestation_message(
        spec,
        block_state,
        block_root,
        ptc_member,
        payload_present=False,
        blob_data_available=False,
    )
    yield from add_payload_attestation_message(spec, store, msg_2, test_steps)

    for i in voter_positions:
        assert store.payload_timeliness_vote[block_root][i] == False
        assert store.payload_data_availability_vote[block_root][i] == False
    for i in other_positions:
        assert store.payload_timeliness_vote[block_root][i] == None
        assert store.payload_data_availability_vote[block_root][i] == None
    add_payload_vote_checks(store, block_root, test_steps)

    yield "steps", test_steps


@with_gloas_and_later
@spec_state_test
def test_on_payload_attestation_message_multiple_ptc_members_vote_independently(spec, state):
    """
    Test that two different PTC members voting for the same block update independent vote sets.
    """
    # Set two different validators on the PTC
    block_slot = state.slot + 1
    window_idx = spec.SLOTS_PER_EPOCH + block_slot % spec.SLOTS_PER_EPOCH
    state.ptc_window[window_idx][0] = spec.ValidatorIndex(0)
    state.ptc_window[window_idx][1] = spec.ValidatorIndex(1)

    store, block_root, block_state, ptc, test_steps = yield from _setup_test(spec, state)

    ptc_member_a = ptc[0]
    ptc_member_b = ptc[1]
    assert ptc_member_a != ptc_member_b

    # Compute every position each validator appears at
    positions_a = [i for i, v in enumerate(ptc) if v == ptc_member_a]
    positions_b = [i for i, v in enumerate(ptc) if v == ptc_member_b]
    other_positions = [i for i in range(len(ptc)) if i not in positions_a and i not in positions_b]

    msg_a = _build_signed_payload_attestation_message(
        spec,
        block_state,
        block_root,
        ptc_member_a,
        payload_present=True,
        blob_data_available=True,
    )
    yield from add_payload_attestation_message(spec, store, msg_a, test_steps)

    msg_b = _build_signed_payload_attestation_message(
        spec,
        block_state,
        block_root,
        ptc_member_b,
        payload_present=True,
        blob_data_available=False,
    )
    yield from add_payload_attestation_message(spec, store, msg_b, test_steps)

    timeliness = store.payload_timeliness_vote[block_root]
    availability = store.payload_data_availability_vote[block_root]

    # Validator A's votes landed at every position A occupies
    for i in positions_a:
        assert timeliness[i] == True
        assert availability[i] == True

    # Validator B's votes landed at every position B occupies
    for i in positions_b:
        assert timeliness[i] == True
        assert availability[i] == False

    # Other positions stayed at their default values
    for i in other_positions:
        assert timeliness[i] == None
        assert availability[i] == None

    add_payload_vote_checks(store, block_root, test_steps)

    yield "steps", test_steps


@with_gloas_and_later
@spec_state_test
def test_on_payload_attestation_message_from_block(spec, state):
    """
    Test that a PayloadAttestation included in a block updates the vote arrays
    """
    store, block_root, block_state, ptc, test_steps = yield from _setup_test(spec, state)

    # Pick a subset of the PTC to vote
    ptc_list = list(ptc)
    voters = ptc_list[:3]
    voter_set = set(voters)

    # Build the validator messages
    ptc_messages = []
    for validator_index in voters:
        ptc_messages.append(
            _build_signed_payload_attestation_message(
                spec,
                block_state,
                block_root,
                validator_index,
                payload_present=True,
                blob_data_available=True,
            )
        )

    # Build the PayloadAttestation aggregate
    aggregation_bits = spec.Bitvector[spec.PTC_SIZE]()
    for i, validator_index in enumerate(ptc_list):
        if validator_index in voter_set:
            aggregation_bits[i] = True

    sig_by_index = {m.validator_index: m.signature for m in ptc_messages}
    aggregate_sig = spec.bls.Aggregate([sig_by_index[v] for v in ptc_list if v in voter_set])

    aggregate = spec.PayloadAttestation(
        aggregation_bits=aggregation_bits,
        data=ptc_messages[0].data,
        signature=aggregate_sig,
    )

    # Build the next block and add the aggregate
    block_n1 = build_empty_block_for_next_slot(spec, state)
    block_n1.body.payload_attestations.append(aggregate)
    signed_block_n1 = state_transition_and_sign_block(spec, state, block_n1)

    # Apply block
    yield from tick_and_add_block(spec, store, signed_block_n1, test_steps)

    # Votes landed at every PTC position each voter occupies
    for i, validator_index in enumerate(ptc_list):
        if validator_index in voter_set:
            assert store.payload_timeliness_vote[block_root][i] == True
            assert store.payload_data_availability_vote[block_root][i] == True
        else:
            assert store.payload_timeliness_vote[block_root][i] == None
            assert store.payload_data_availability_vote[block_root][i] == None

    add_payload_vote_checks(store, block_root, test_steps)
    yield "steps", test_steps
