from eth_consensus_specs.test.context import (
    always_bls,
    spec_state_test,
    with_altair_and_later,
)
from eth_consensus_specs.test.helpers.gossip import get_filename, get_seen, run_validate_gossip
from eth_consensus_specs.test.helpers.keys import privkeys
from eth_consensus_specs.utils import bls


def get_sync_committee_member(spec, state):
    """Find a validator that is in the current sync committee and return (index, subnet_id)."""
    for validator_index in range(len(state.validators)):
        subnets = spec.compute_subnets_for_sync_committee(state, validator_index)
        if len(subnets) > 0:
            return validator_index, next(iter(subnets))
    raise Exception("No sync committee member found")


def create_valid_sync_committee_message(spec, state, validator_index, slot=None, block_root=None):
    """Create a valid SyncCommitteeMessage."""
    if slot is None:
        slot = state.slot
    if block_root is None:
        block_root = spec.Root()

    epoch = spec.compute_epoch_at_slot(slot)
    domain = spec.get_domain(state, spec.DOMAIN_SYNC_COMMITTEE, epoch)
    signing_root = spec.compute_signing_root(block_root, domain)
    signature = bls.Sign(privkeys[validator_index], signing_root)

    return spec.SyncCommitteeMessage(
        slot=slot,
        beacon_block_root=block_root,
        validator_index=validator_index,
        signature=signature,
    )


@with_altair_and_later
@spec_state_test
@always_bls
def test_gossip_sync_committee_message__valid(spec, state):
    """Test that a valid sync committee message passes gossip validation."""
    yield "topic", "meta", "sync_committee"
    yield "state", state

    seen = get_seen(spec)
    validator_index, subnet_id = get_sync_committee_member(spec, state)
    message = create_valid_sync_committee_message(spec, state, validator_index)

    yield get_filename(message), message

    current_time_ms = spec.compute_time_at_slot_ms(state, state.slot)

    yield "current_time_ms", "meta", int(current_time_ms)

    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        state=state,
        sync_committee_message=message,
        current_time_ms=current_time_ms + 500,
        subnet_id=subnet_id,
    )
    assert result == "valid"
    assert reason is None

    yield (
        "messages",
        "meta",
        [
            {
                "offset_ms": 500,
                "subnet_id": int(subnet_id),
                "message": get_filename(message),
                "expected": "valid",
            }
        ],
    )


@with_altair_and_later
@spec_state_test
def test_gossip_sync_committee_message__ignore_future_slot(spec, state):
    """Test that a sync committee message from a future slot is ignored."""
    yield "topic", "meta", "sync_committee"
    yield "state", state

    seen = get_seen(spec)
    validator_index, subnet_id = get_sync_committee_member(spec, state)

    # Create message for a future slot
    future_slot = state.slot + 1
    message = create_valid_sync_committee_message(spec, state, validator_index, slot=future_slot)

    yield get_filename(message), message

    current_time_ms = spec.compute_time_at_slot_ms(state, state.slot)

    yield "current_time_ms", "meta", int(current_time_ms)

    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        state=state,
        sync_committee_message=message,
        current_time_ms=current_time_ms,
        subnet_id=subnet_id,
    )
    assert result == "ignore"
    assert reason == "message is not for the current slot"

    yield (
        "messages",
        "meta",
        [
            {
                "offset_ms": 0,
                "subnet_id": int(subnet_id),
                "message": get_filename(message),
                "expected": "ignore",
                "reason": reason,
            }
        ],
    )


@with_altair_and_later
@spec_state_test
def test_gossip_sync_committee_message__ignore_past_slot(spec, state):
    """Test that a sync committee message from a past slot is ignored."""
    yield "topic", "meta", "sync_committee"

    seen = get_seen(spec)
    validator_index, subnet_id = get_sync_committee_member(spec, state)

    # Advance state so there's a past slot (gap >= 2 needed to exceed MAXIMUM_GOSSIP_CLOCK_DISPARITY)
    state.slot += 3

    yield "state", state

    # Create message for a past slot
    past_slot = state.slot - 2
    message = create_valid_sync_committee_message(spec, state, validator_index, slot=past_slot)

    yield get_filename(message), message

    current_time_ms = spec.compute_time_at_slot_ms(state, state.slot)

    yield "current_time_ms", "meta", int(current_time_ms)

    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        state=state,
        sync_committee_message=message,
        current_time_ms=current_time_ms,
        subnet_id=subnet_id,
    )
    assert result == "ignore"
    assert reason == "message is not for the current slot"

    yield (
        "messages",
        "meta",
        [
            {
                "offset_ms": 0,
                "subnet_id": int(subnet_id),
                "message": get_filename(message),
                "expected": "ignore",
                "reason": reason,
            }
        ],
    )


@with_altair_and_later
@spec_state_test
def test_gossip_sync_committee_message__reject_wrong_subnet(spec, state):
    """Test that a sync committee message on the wrong subnet is rejected."""
    yield "topic", "meta", "sync_committee"
    yield "state", state

    seen = get_seen(spec)
    validator_index, correct_subnet_id = get_sync_committee_member(spec, state)
    message = create_valid_sync_committee_message(spec, state, validator_index)

    yield get_filename(message), message

    current_time_ms = spec.compute_time_at_slot_ms(state, state.slot)

    yield "current_time_ms", "meta", int(current_time_ms)

    # Use a wrong subnet_id
    wrong_subnet_id = (correct_subnet_id + 1) % spec.SYNC_COMMITTEE_SUBNET_COUNT

    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        state=state,
        sync_committee_message=message,
        current_time_ms=current_time_ms + 500,
        subnet_id=wrong_subnet_id,
    )
    assert result == "reject"
    assert reason == "subnet_id is not valid for the validator"

    yield (
        "messages",
        "meta",
        [
            {
                "offset_ms": 500,
                "subnet_id": int(wrong_subnet_id),
                "message": get_filename(message),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_altair_and_later
@spec_state_test
def test_gossip_sync_committee_message__reject_validator_index_out_of_range(spec, state):
    """Test that a sync committee message with validator index out of range is rejected."""
    yield "topic", "meta", "sync_committee"
    yield "state", state

    seen = get_seen(spec)
    validator_index, subnet_id = get_sync_committee_member(spec, state)
    message = create_valid_sync_committee_message(spec, state, validator_index)

    message.validator_index = len(state.validators)

    yield get_filename(message), message

    current_time_ms = spec.compute_time_at_slot_ms(state, state.slot)

    yield "current_time_ms", "meta", int(current_time_ms)

    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        state=state,
        sync_committee_message=message,
        current_time_ms=current_time_ms + 500,
        subnet_id=subnet_id,
    )
    assert result == "reject"
    assert reason == "validator index out of range"

    yield (
        "messages",
        "meta",
        [
            {
                "offset_ms": 500,
                "subnet_id": int(subnet_id),
                "message": get_filename(message),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_altair_and_later
@spec_state_test
def test_gossip_sync_committee_message__ignore_duplicate(spec, state):
    """Test that a duplicate sync committee message is ignored."""
    yield "topic", "meta", "sync_committee"
    yield "state", state

    messages = []
    seen = get_seen(spec)
    validator_index, subnet_id = get_sync_committee_member(spec, state)
    message = create_valid_sync_committee_message(spec, state, validator_index)

    yield get_filename(message), message

    current_time_ms = spec.compute_time_at_slot_ms(state, state.slot)

    yield "current_time_ms", "meta", int(current_time_ms)

    # First validation should pass
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        state=state,
        sync_committee_message=message,
        current_time_ms=current_time_ms + 500,
        subnet_id=subnet_id,
    )
    assert result == "valid"
    assert reason is None
    messages.append(
        {
            "offset_ms": 500,
            "subnet_id": int(subnet_id),
            "message": get_filename(message),
            "expected": "valid",
        }
    )

    # Second validation should be ignored
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        state=state,
        sync_committee_message=message,
        current_time_ms=current_time_ms + 600,
        subnet_id=subnet_id,
    )
    assert result == "ignore"
    assert reason == "already seen message from this validator for this slot and subnet"
    messages.append(
        {
            "offset_ms": 600,
            "subnet_id": int(subnet_id),
            "message": get_filename(message),
            "expected": "ignore",
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_altair_and_later
@spec_state_test
@always_bls
def test_gossip_sync_committee_message__reject_invalid_signature(spec, state):
    """Test that a sync committee message with invalid signature is rejected."""
    yield "topic", "meta", "sync_committee"
    yield "state", state

    seen = get_seen(spec)
    validator_index, subnet_id = get_sync_committee_member(spec, state)

    # Create message with wrong key
    block_root = spec.Root()
    epoch = spec.compute_epoch_at_slot(state.slot)
    domain = spec.get_domain(state, spec.DOMAIN_SYNC_COMMITTEE, epoch)
    signing_root = spec.compute_signing_root(block_root, domain)
    # Sign with a different validator's key
    wrong_key = privkeys[(validator_index + 1) % len(privkeys)]
    signature = bls.Sign(wrong_key, signing_root)

    message = spec.SyncCommitteeMessage(
        slot=state.slot,
        beacon_block_root=block_root,
        validator_index=validator_index,
        signature=signature,
    )

    yield get_filename(message), message

    current_time_ms = spec.compute_time_at_slot_ms(state, state.slot)

    yield "current_time_ms", "meta", int(current_time_ms)

    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        state=state,
        sync_committee_message=message,
        current_time_ms=current_time_ms + 500,
        subnet_id=subnet_id,
    )
    assert result == "reject"
    assert reason == "invalid sync committee message signature"

    yield (
        "messages",
        "meta",
        [
            {
                "offset_ms": 500,
                "subnet_id": int(subnet_id),
                "message": get_filename(message),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )
