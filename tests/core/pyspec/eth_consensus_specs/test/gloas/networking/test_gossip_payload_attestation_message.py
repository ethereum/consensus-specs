from eth_consensus_specs.test.context import (
    spec_state_test,
    with_gloas_and_later,
)
from eth_consensus_specs.test.helpers.block import build_empty_block_for_next_slot
from eth_consensus_specs.test.helpers.fork_choice import (
    get_genesis_forkchoice_store_and_block,
)
from eth_consensus_specs.test.helpers.gossip import (
    get_filename,
    get_seen,
    run_validate_gossip,
    wrap_genesis_block,
)
from eth_consensus_specs.test.helpers.keys import privkeys
from eth_consensus_specs.test.helpers.state import next_slot, state_transition_and_sign_block


def setup_store_with_one_block(spec, state):
    """
    Build the genesis store, then apply one block at the next slot so that we
    have a known beacon_block_root the PTC can attest to.
    """
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block)
    block_root = signed_block.message.hash_tree_root()
    store.blocks[block_root] = signed_block.message
    store.block_states[block_root] = state.copy()
    return store, [signed_anchor, signed_block], block_root


def build_payload_attestation_message(
    spec,
    state,
    slot,
    beacon_block_root,
    validator_index,
    payload_present=True,
    valid_signature=True,
):
    """Construct a PayloadAttestationMessage signed by ``validator_index``."""
    data = spec.PayloadAttestationData(
        beacon_block_root=beacon_block_root,
        slot=slot,
        payload_present=payload_present,
        blob_data_available=True,
    )
    message = spec.PayloadAttestationMessage(
        validator_index=validator_index,
        data=data,
        signature=spec.BLSSignature(),
    )
    if valid_signature:
        domain = spec.get_domain(state, spec.DOMAIN_PTC_ATTESTER, spec.compute_epoch_at_slot(slot))
        signing_root = spec.compute_signing_root(data, domain)
        message.signature = spec.bls.Sign(privkeys[validator_index], signing_root)
    return message


@with_gloas_and_later
@spec_state_test
def test_gossip_payload_attestation_message__valid(spec, state):
    """A PayloadAttestationMessage from a PTC member for the current slot passes."""
    yield "topic", "meta", "payload_attestation_message"

    store, blocks, block_root = setup_store_with_one_block(spec, state)
    yield "state", state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    seen = get_seen(spec)
    ptc = spec.get_ptc(state, state.slot)
    validator_index = ptc[0]
    message = build_payload_attestation_message(
        spec, state, state.slot, block_root, validator_index
    )
    yield get_filename(message), message

    time_ms = spec.compute_time_at_slot_ms(state, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 100
    result, reason = run_validate_gossip(spec, seen, store, state, message, current_time_ms=time_ms)
    assert result == "valid"
    assert reason is None
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(message),
            "expected": result,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_payload_attestation_message__ignore_not_current_slot(spec, state):
    """A message whose slot is not the current slot is ignored."""
    yield "topic", "meta", "payload_attestation_message"

    store, blocks, block_root = setup_store_with_one_block(spec, state)
    yield "state", state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    seen = get_seen(spec)
    ptc = spec.get_ptc(state, state.slot)
    validator_index = ptc[0]
    message = build_payload_attestation_message(
        spec, state, state.slot, block_root, validator_index
    )
    yield get_filename(message), message

    # Use a current_time well past the message's slot.
    time_ms = spec.compute_time_at_slot_ms(state, state.slot) + 1000 * 1000
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    result, reason = run_validate_gossip(spec, seen, store, state, message, current_time_ms=time_ms)
    assert result == "ignore"
    assert reason == "payload attestation message slot is not the current slot"
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(message),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_payload_attestation_message__ignore_duplicate(spec, state):
    """The second valid message from the same validator for the same slot is ignored."""
    yield "topic", "meta", "payload_attestation_message"

    store, blocks, block_root = setup_store_with_one_block(spec, state)
    yield "state", state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    seen = get_seen(spec)
    ptc = spec.get_ptc(state, state.slot)
    validator_index = ptc[0]
    message = build_payload_attestation_message(
        spec, state, state.slot, block_root, validator_index
    )
    yield get_filename(message), message

    time_ms = spec.compute_time_at_slot_ms(state, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 100
    result, reason = run_validate_gossip(spec, seen, store, state, message, current_time_ms=time_ms)
    assert result == "valid"
    assert reason is None
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(message),
            "expected": result,
        }
    )

    time_ms += 100
    result, reason = run_validate_gossip(spec, seen, store, state, message, current_time_ms=time_ms)
    assert result == "ignore"
    assert reason == "already seen payload attestation message from this validator"
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(message),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_payload_attestation_message__ignore_block_unseen(spec, state):
    """A message attesting to an unknown beacon block is ignored."""
    yield "topic", "meta", "payload_attestation_message"

    store, blocks, _ = setup_store_with_one_block(spec, state)
    yield "state", state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    seen = get_seen(spec)
    ptc = spec.get_ptc(state, state.slot)
    validator_index = ptc[0]
    unknown_root = spec.Root(b"\xee" * 32)
    message = build_payload_attestation_message(
        spec, state, state.slot, unknown_root, validator_index
    )
    yield get_filename(message), message

    time_ms = spec.compute_time_at_slot_ms(state, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 100
    result, reason = run_validate_gossip(spec, seen, store, state, message, current_time_ms=time_ms)
    assert result == "ignore"
    assert reason == "message's block has not been seen"
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(message),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_payload_attestation_message__reject_validator_not_in_ptc(spec, state):
    """A message from a validator not in the PTC is rejected."""
    yield "topic", "meta", "payload_attestation_message"

    store, blocks, block_root = setup_store_with_one_block(spec, state)
    yield "state", state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    seen = get_seen(spec)
    ptc = set(spec.get_ptc(state, state.slot))
    outsider = next(spec.ValidatorIndex(i) for i in range(len(state.validators)) if i not in ptc)
    message = build_payload_attestation_message(spec, state, state.slot, block_root, outsider)
    yield get_filename(message), message

    time_ms = spec.compute_time_at_slot_ms(state, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 100
    result, reason = run_validate_gossip(spec, seen, store, state, message, current_time_ms=time_ms)
    assert result == "reject"
    assert reason == "validator is not in the payload timeliness committee"
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(message),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_payload_attestation_message__reject_invalid_signature(spec, state):
    """A message with an invalid signature is rejected."""
    yield "topic", "meta", "payload_attestation_message"

    store, blocks, block_root = setup_store_with_one_block(spec, state)
    yield "state", state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    seen = get_seen(spec)
    ptc = spec.get_ptc(state, state.slot)
    validator_index = ptc[0]
    message = build_payload_attestation_message(
        spec, state, state.slot, block_root, validator_index, valid_signature=False
    )
    yield get_filename(message), message

    time_ms = spec.compute_time_at_slot_ms(state, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 100
    result, reason = run_validate_gossip(spec, seen, store, state, message, current_time_ms=time_ms)
    assert result == "reject"
    assert reason == "invalid payload attestation message signature"
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(message),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_payload_attestation_message__reject_block_failed_validation(spec, state):
    """A message whose block is in store.blocks but not in store.block_states is rejected."""
    yield "topic", "meta", "payload_attestation_message"

    store, blocks, block_root = setup_store_with_one_block(spec, state)
    # Drop the block's state so the post-validation check fires.
    del store.block_states[block_root]
    yield "state", state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    seen = get_seen(spec)
    ptc = spec.get_ptc(state, state.slot)
    validator_index = ptc[0]
    message = build_payload_attestation_message(
        spec, state, state.slot, block_root, validator_index
    )
    yield get_filename(message), message

    time_ms = spec.compute_time_at_slot_ms(state, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 100
    result, reason = run_validate_gossip(spec, seen, store, state, message, current_time_ms=time_ms)
    assert result == "reject"
    assert reason == "message's block failed validation"
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(message),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_payload_attestation_message__reject_validator_index_out_of_range(spec, state):
    """A message whose validator index is past the validator registry is rejected."""
    yield "topic", "meta", "payload_attestation_message"

    store, blocks, block_root = setup_store_with_one_block(spec, state)
    yield "state", state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    seen = get_seen(spec)
    out_of_range_index = spec.ValidatorIndex(len(state.validators))
    # Build the message by hand because build_payload_attestation_message indexes
    # into privkeys for signing, which would fail for an out-of-range index.
    data = spec.PayloadAttestationData(
        beacon_block_root=block_root,
        slot=state.slot,
        payload_present=True,
        blob_data_available=True,
    )
    message = spec.PayloadAttestationMessage(
        validator_index=out_of_range_index,
        data=data,
        signature=spec.BLSSignature(),
    )
    yield get_filename(message), message

    time_ms = spec.compute_time_at_slot_ms(state, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 100
    result, reason = run_validate_gossip(spec, seen, store, state, message, current_time_ms=time_ms)
    assert result == "reject"
    assert reason == "validator index out of range"
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(message),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_payload_attestation_message__ignore_block_not_at_assigned_slot(spec, state):
    """A PTC message whose block.slot does not equal data.slot is ignored (assigned slot was empty)."""
    yield "topic", "meta", "payload_attestation_message"

    # Apply a block at slot 1, advance state to slot 2 without applying a block
    # there. The PTC member for slot 2 would attest against the slot-1 block,
    # which the gossip rule must ignore because slot 2 was empty.
    store, blocks, block_1_root = setup_store_with_one_block(spec, state)
    next_slot(spec, state)
    assert state.slot == 2
    yield "state", state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    seen = get_seen(spec)
    ptc = spec.get_ptc(state, state.slot)
    validator_index = ptc[0]
    message = build_payload_attestation_message(
        spec, state, state.slot, block_1_root, validator_index
    )
    yield get_filename(message), message

    time_ms = spec.compute_time_at_slot_ms(state, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 100
    result, reason = run_validate_gossip(spec, seen, store, state, message, current_time_ms=time_ms)
    assert result == "ignore"
    assert reason == "message's block is not at the assigned slot"
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(message),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages
