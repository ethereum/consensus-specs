from eth_consensus_specs.test.context import (
    always_bls,
    spec_state_test,
    with_altair_and_later,
    with_phases,
)
from eth_consensus_specs.test.helpers.block import build_empty_block_for_next_slot
from eth_consensus_specs.test.helpers.constants import ALTAIR
from eth_consensus_specs.test.helpers.fork_choice import (
    get_genesis_forkchoice_store,
    get_genesis_forkchoice_store_and_block,
)
from eth_consensus_specs.test.helpers.gossip import get_filename, get_seen, wrap_genesis_block
from eth_consensus_specs.test.helpers.keys import privkeys
from eth_consensus_specs.test.helpers.state import state_transition_and_sign_block
from eth_consensus_specs.utils import bls


def setup_store_with_anchor(spec, state):
    """Return a store seeded with the genesis anchor block."""
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    return store, anchor_block


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


def run_validate_sync_committee_message_gossip(
    spec, seen, store, state, message, subnet_id, current_time_ms
):
    """Run validate_sync_committee_message_gossip and return the result."""
    try:
        spec.validate_sync_committee_message_gossip(
            seen,
            store,
            state,
            message,
            current_time_ms,
            subnet_id,
        )
        return "valid", None
    except spec.GossipIgnore as e:
        return "ignore", str(e)
    except spec.GossipReject as e:
        return "reject", str(e)


@with_altair_and_later
@spec_state_test
@always_bls
def test_gossip_sync_committee_message__valid(spec, state):
    """Test that a valid sync committee message passes gossip validation."""
    yield "topic", "meta", "sync_committee"
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = setup_store_with_anchor(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    anchor_root = spec.Root(anchor_block.hash_tree_root())
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]
    validator_index, subnet_id = get_sync_committee_member(spec, state)
    message = create_valid_sync_committee_message(
        spec, state, validator_index, block_root=anchor_root
    )

    yield get_filename(message), message

    current_time_ms = spec.compute_time_at_slot_ms(state, state.slot)

    yield "current_time_ms", "meta", int(current_time_ms)

    result, reason = run_validate_sync_committee_message_gossip(
        spec,
        seen,
        store,
        state,
        message,
        subnet_id,
        current_time_ms + 500,
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
    store = get_genesis_forkchoice_store(spec, state)
    validator_index, subnet_id = get_sync_committee_member(spec, state)

    # Create message for a future slot
    future_slot = state.slot + 1
    message = create_valid_sync_committee_message(spec, state, validator_index, slot=future_slot)

    yield get_filename(message), message

    current_time_ms = spec.compute_time_at_slot_ms(state, state.slot)

    yield "current_time_ms", "meta", int(current_time_ms)

    result, reason = run_validate_sync_committee_message_gossip(
        spec,
        seen,
        store,
        state,
        message,
        subnet_id,
        current_time_ms,
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
    store = get_genesis_forkchoice_store(spec, state)
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

    result, reason = run_validate_sync_committee_message_gossip(
        spec,
        seen,
        store,
        state,
        message,
        subnet_id,
        current_time_ms,
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
    store = get_genesis_forkchoice_store(spec, state)
    validator_index, correct_subnet_id = get_sync_committee_member(spec, state)
    message = create_valid_sync_committee_message(spec, state, validator_index)

    yield get_filename(message), message

    current_time_ms = spec.compute_time_at_slot_ms(state, state.slot)

    yield "current_time_ms", "meta", int(current_time_ms)

    # Use a wrong subnet_id
    wrong_subnet_id = (correct_subnet_id + 1) % spec.SYNC_COMMITTEE_SUBNET_COUNT

    result, reason = run_validate_sync_committee_message_gossip(
        spec,
        seen,
        store,
        state,
        message,
        wrong_subnet_id,
        current_time_ms + 500,
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
    store = get_genesis_forkchoice_store(spec, state)
    validator_index, subnet_id = get_sync_committee_member(spec, state)
    message = create_valid_sync_committee_message(spec, state, validator_index)

    message.validator_index = len(state.validators)

    yield get_filename(message), message

    current_time_ms = spec.compute_time_at_slot_ms(state, state.slot)

    yield "current_time_ms", "meta", int(current_time_ms)

    result, reason = run_validate_sync_committee_message_gossip(
        spec,
        seen,
        store,
        state,
        message,
        subnet_id,
        current_time_ms + 500,
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
    store, anchor_block = setup_store_with_anchor(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    anchor_root = spec.Root(anchor_block.hash_tree_root())
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]
    validator_index, subnet_id = get_sync_committee_member(spec, state)
    message = create_valid_sync_committee_message(
        spec, state, validator_index, block_root=anchor_root
    )

    yield get_filename(message), message

    current_time_ms = spec.compute_time_at_slot_ms(state, state.slot)

    yield "current_time_ms", "meta", int(current_time_ms)

    # First validation should pass
    result, reason = run_validate_sync_committee_message_gossip(
        spec,
        seen,
        store,
        state,
        message,
        subnet_id,
        current_time_ms + 500,
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
    result, reason = run_validate_sync_committee_message_gossip(
        spec,
        seen,
        store,
        state,
        message,
        subnet_id,
        current_time_ms + 600,
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


@with_phases([ALTAIR])
@spec_state_test
@always_bls
def test_gossip_sync_committee_message__allow_second_for_head(spec, state):
    """Test that a head message is allowed even after a stale message for a non-head block."""
    yield "topic", "meta", "sync_committee"

    store, anchor_block = setup_store_with_anchor(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    anchor_root = spec.Root(anchor_block.hash_tree_root())

    # Build a child block
    child_block = build_empty_block_for_next_slot(spec, state)
    signed_child = state_transition_and_sign_block(spec, state, child_block)
    spec.on_tick(
        store,
        store.genesis_time + signed_child.message.slot * spec.config.SLOT_DURATION_MS // 1000,
    )
    spec.on_block(store, signed_child)
    head_root = spec.Root(signed_child.message.hash_tree_root())
    assert spec.get_head(store).root == head_root
    assert head_root != anchor_root

    yield get_filename(signed_anchor), signed_anchor
    yield get_filename(signed_child), signed_child
    yield (
        "blocks",
        "meta",
        [
            {"block": get_filename(signed_anchor)},
            {"block": get_filename(signed_child)},
        ],
    )
    yield "state", state

    messages = []
    seen = get_seen(spec)
    validator_index, subnet_id = get_sync_committee_member(spec, state)
    stale_message = create_valid_sync_committee_message(
        spec, state, validator_index, block_root=anchor_root
    )
    yield get_filename(stale_message), stale_message
    head_message = create_valid_sync_committee_message(
        spec, state, validator_index, block_root=head_root
    )
    yield get_filename(head_message), head_message

    current_time_ms = spec.compute_time_at_slot_ms(state, state.slot)

    yield "current_time_ms", "meta", int(current_time_ms)

    # First validation should pass
    result, reason = run_validate_sync_committee_message_gossip(
        spec,
        seen,
        store,
        state,
        stale_message,
        subnet_id,
        current_time_ms + 500,
    )
    assert result == "valid"
    assert reason is None
    messages.append(
        {
            "offset_ms": 500,
            "subnet_id": int(subnet_id),
            "message": get_filename(stale_message),
            "expected": "valid",
        }
    )

    # Second validation should pass
    result, reason = run_validate_sync_committee_message_gossip(
        spec,
        seen,
        store,
        state,
        head_message,
        subnet_id,
        current_time_ms + 600,
    )
    assert result == "valid"
    assert reason is None
    messages.append(
        {
            "offset_ms": 600,
            "subnet_id": int(subnet_id),
            "message": get_filename(head_message),
            "expected": "valid",
        }
    )

    # Third validation should be ignored
    result, reason = run_validate_sync_committee_message_gossip(
        spec,
        seen,
        store,
        state,
        head_message,
        subnet_id,
        current_time_ms + 700,
    )
    assert result == "ignore"
    assert reason == "already seen message from this validator for this slot and subnet"
    messages.append(
        {
            "offset_ms": 700,
            "subnet_id": int(subnet_id),
            "message": get_filename(head_message),
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
    store, anchor_block = setup_store_with_anchor(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    anchor_root = spec.Root(anchor_block.hash_tree_root())
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]
    validator_index, subnet_id = get_sync_committee_member(spec, state)

    # Create message with wrong key
    block_root = anchor_root
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

    result, reason = run_validate_sync_committee_message_gossip(
        spec,
        seen,
        store,
        state,
        message,
        subnet_id,
        current_time_ms + 500,
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


@with_altair_and_later
@spec_state_test
def test_gossip_sync_committee_message__ignore_block_not_seen(spec, state):
    """Test that a message for an unseen block is ignored."""
    yield "topic", "meta", "sync_committee"
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = setup_store_with_anchor(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)

    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    # Build and apply a block (but don't add to store)
    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block)

    # Create a message referencing the unseen block
    validator_index, subnet_id = get_sync_committee_member(spec, state)
    message = create_valid_sync_committee_message(
        spec, state, validator_index, block_root=spec.Root(signed_block.message.hash_tree_root())
    )

    yield get_filename(message), message

    current_time_ms = spec.compute_time_at_slot_ms(state, state.slot)

    yield "current_time_ms", "meta", int(current_time_ms)

    result, reason = run_validate_sync_committee_message_gossip(
        spec,
        seen,
        store,
        state,
        message,
        subnet_id,
        current_time_ms + 500,
    )
    assert result == "ignore"
    assert reason == "block being signed has not been seen"

    yield (
        "messages",
        "meta",
        [
            {
                "offset_ms": 500,
                "subnet_id": int(subnet_id),
                "message": get_filename(message),
                "expected": "ignore",
                "reason": reason,
            }
        ],
    )
