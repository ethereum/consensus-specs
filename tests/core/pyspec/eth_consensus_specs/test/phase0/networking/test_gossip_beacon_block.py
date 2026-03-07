from eth_consensus_specs.test.context import (
    spec_state_test,
    with_phases,
)
from eth_consensus_specs.test.helpers.block import (
    build_empty_block_for_next_slot,
    sign_block,
)
from eth_consensus_specs.test.helpers.constants import PHASE0
from eth_consensus_specs.test.helpers.fork_choice import (
    get_genesis_forkchoice_store_and_block,
)
from eth_consensus_specs.test.helpers.gossip import get_filename, get_seen
from eth_consensus_specs.test.helpers.state import (
    state_transition_and_sign_block,
)


def wrap_genesis_block(spec, block):
    """Wrap an unsigned genesis block in a SignedBeaconBlock with empty signature."""
    return spec.SignedBeaconBlock(message=block)


def run_validate_beacon_block_gossip(spec, seen, store, state, signed_block, current_time_ms):
    """
    Run validate_beacon_block_gossip and return the result.
    Returns: tuple of (result, reason) where result is "valid", "ignore", or "reject"
             and reason is the exception message (or None for valid).
    """
    try:
        spec.validate_beacon_block_gossip(seen, store, state, signed_block, current_time_ms)
        return "valid", None
    except spec.GossipIgnore as e:
        return "ignore", str(e)
    except spec.GossipReject as e:
        return "reject", str(e)


@with_phases([PHASE0])
@spec_state_test
def test_gossip_beacon_block__valid_block(spec, state):
    """
    Test that a valid block passes gossip validation.
    """
    yield "topic", "meta", "beacon_block"
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)

    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block)

    yield get_filename(signed_block), signed_block

    block_time_ms = spec.compute_time_at_slot_ms(store, signed_block.message.slot)

    yield "current_time_ms", "meta", int(block_time_ms)

    result, reason = run_validate_beacon_block_gossip(
        spec, seen, store, state, signed_block, block_time_ms + 500
    )
    assert result == "valid"
    assert reason is None

    yield (
        "messages",
        "meta",
        [{"offset_ms": 500, "message": get_filename(signed_block), "expected": "valid"}],
    )


@with_phases([PHASE0])
@spec_state_test
def test_gossip_beacon_block__ignore_future_slot(spec, state):
    """
    Test that a block from a future slot is ignored.
    """
    yield "topic", "meta", "beacon_block"
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)

    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block)

    yield get_filename(signed_block), signed_block

    block_time_ms = spec.compute_time_at_slot_ms(store, signed_block.message.slot)
    current_time_ms = block_time_ms - spec.config.MAXIMUM_GOSSIP_CLOCK_DISPARITY - 1

    yield "current_time_ms", "meta", int(current_time_ms)

    result, reason = run_validate_beacon_block_gossip(
        spec, seen, store, state, signed_block, current_time_ms
    )
    assert result == "ignore"
    assert reason == "block is from a future slot"

    yield (
        "messages",
        "meta",
        [
            {
                "offset_ms": 0,
                "message": get_filename(signed_block),
                "expected": "ignore",
                "reason": reason,
            }
        ],
    )


@with_phases([PHASE0])
@spec_state_test
def test_gossip_beacon_block__valid_within_clock_disparity(spec, state):
    """
    Test that a block from a slightly future slot is valid within clock disparity.
    """
    yield "topic", "meta", "beacon_block"
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)

    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block)

    yield get_filename(signed_block), signed_block

    block_time_ms = spec.compute_time_at_slot_ms(store, signed_block.message.slot)
    current_time_ms = block_time_ms - spec.config.MAXIMUM_GOSSIP_CLOCK_DISPARITY

    yield "current_time_ms", "meta", int(current_time_ms)

    result, reason = run_validate_beacon_block_gossip(
        spec, seen, store, state, signed_block, current_time_ms
    )
    assert result == "valid"
    assert reason is None

    yield (
        "messages",
        "meta",
        [{"offset_ms": 0, "message": get_filename(signed_block), "expected": "valid"}],
    )


@with_phases([PHASE0])
@spec_state_test
def test_gossip_beacon_block__ignore_already_seen_proposer_slot(spec, state):
    """
    Test that a duplicate block for the same proposer/slot is ignored.
    """
    yield "topic", "meta", "beacon_block"
    yield "state", state

    messages = []
    seen = get_seen(spec)
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)

    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block)

    yield get_filename(signed_block), signed_block

    block_time_ms = spec.compute_time_at_slot_ms(store, signed_block.message.slot)

    yield "current_time_ms", "meta", int(block_time_ms)

    # First block should be valid
    result, reason = run_validate_beacon_block_gossip(
        spec, seen, store, state, signed_block, block_time_ms + 500
    )
    assert result == "valid"
    assert reason is None
    messages.append({"offset_ms": 500, "message": get_filename(signed_block), "expected": "valid"})

    # Second block with same proposer/slot should be ignored
    result, reason = run_validate_beacon_block_gossip(
        spec, seen, store, state, signed_block, block_time_ms + 600
    )
    assert result == "ignore"
    assert reason == "block is not the first valid block for this proposer and slot"
    messages.append(
        {
            "offset_ms": 600,
            "message": get_filename(signed_block),
            "expected": "ignore",
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_phases([PHASE0])
@spec_state_test
def test_gossip_beacon_block__ignore_slot_not_greater_than_finalized(spec, state):
    """
    Test that a block at or before the finalized slot is ignored.
    """
    yield "topic", "meta", "beacon_block"
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)

    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    # Set finalized checkpoint to epoch 1 (slot 8 in minimal preset)
    store.finalized_checkpoint = spec.Checkpoint(
        epoch=spec.Epoch(1),
        root=anchor_block.hash_tree_root(),
    )
    finalized_slot = spec.compute_start_slot_at_epoch(store.finalized_checkpoint.epoch)

    yield (
        "finalized_checkpoint",
        "meta",
        {
            "epoch": int(store.finalized_checkpoint.epoch),
            "block": get_filename(signed_anchor),
        },
    )

    # Process state to the finalized slot to get correct proposer
    temp_state = state.copy()
    spec.process_slots(temp_state, finalized_slot)
    proposer_index = spec.get_beacon_proposer_index(temp_state)

    # Build a block at the finalized slot (should be ignored)
    block = spec.BeaconBlock(
        slot=finalized_slot,
        proposer_index=proposer_index,
        parent_root=anchor_block.hash_tree_root(),
        state_root=temp_state.hash_tree_root(),
    )
    signed_block = sign_block(spec, temp_state, block, proposer_index=proposer_index)

    yield get_filename(signed_block), signed_block

    block_time_ms = spec.compute_time_at_slot_ms(store, block.slot)

    yield "current_time_ms", "meta", int(block_time_ms)

    result, reason = run_validate_beacon_block_gossip(
        spec, seen, store, state, signed_block, block_time_ms + 500
    )
    assert result == "ignore"
    assert reason == "block is not from a slot greater than the latest finalized slot"

    yield (
        "messages",
        "meta",
        [
            {
                "offset_ms": 500,
                "message": get_filename(signed_block),
                "expected": "ignore",
                "reason": reason,
            }
        ],
    )


@with_phases([PHASE0])
@spec_state_test
def test_gossip_beacon_block__ignore_parent_not_seen(spec, state):
    """
    Test that a block whose parent is not in the store is ignored.
    """
    yield "topic", "meta", "beacon_block"
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)

    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block)

    # Modify parent_root to something unknown
    signed_block.message.parent_root = b"\x12" * 32
    # Re-sign after mutating the block so signature checks do not mask parent checks.
    signed_block = sign_block(
        spec,
        state,
        signed_block.message,
        proposer_index=signed_block.message.proposer_index,
    )

    yield get_filename(signed_block), signed_block

    block_time_ms = spec.compute_time_at_slot_ms(store, signed_block.message.slot)

    yield "current_time_ms", "meta", int(block_time_ms)

    result, reason = run_validate_beacon_block_gossip(
        spec, seen, store, state, signed_block, block_time_ms + 500
    )
    assert result == "ignore"
    assert reason == "block's parent has not been seen"

    yield (
        "messages",
        "meta",
        [
            {
                "offset_ms": 500,
                "message": get_filename(signed_block),
                "expected": "ignore",
                "reason": reason,
            }
        ],
    )


@with_phases([PHASE0])
@spec_state_test
def test_gossip_beacon_block__reject_parent_failed_validation(spec, state):
    """
    Test that a block whose parent failed validation is rejected.
    This happens when parent is in store.blocks but not in store.block_states.
    """
    yield "topic", "meta", "beacon_block"
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)

    yield get_filename(signed_anchor), signed_anchor

    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block)

    yield get_filename(signed_block), signed_block

    # Add block to store.blocks but NOT to store.block_states (simulating failed validation)
    store.blocks[signed_block.message.hash_tree_root()] = signed_block.message

    yield (
        "blocks",
        "meta",
        [
            {"block": get_filename(signed_anchor)},
            {"block": get_filename(signed_block), "failed": True},
        ],
    )

    # Get the correct proposer for the child block's slot
    child_slot = signed_block.message.slot + 1
    temp_state = state.copy()
    spec.process_slots(temp_state, child_slot)
    proposer_index = spec.get_beacon_proposer_index(temp_state)

    # Build a child block that references the "failed" parent
    child_block = spec.BeaconBlock(
        slot=child_slot,
        proposer_index=proposer_index,
        parent_root=signed_block.message.hash_tree_root(),
        state_root=temp_state.hash_tree_root(),
    )
    signed_child = sign_block(spec, temp_state, child_block, proposer_index=proposer_index)

    yield get_filename(signed_child), signed_child

    block_time_ms = spec.compute_time_at_slot_ms(store, child_block.slot)

    yield "current_time_ms", "meta", int(block_time_ms)

    result, reason = run_validate_beacon_block_gossip(
        spec, seen, store, state, signed_child, block_time_ms + 500
    )
    assert result == "reject"
    assert reason == "block's parent failed validation"

    yield (
        "messages",
        "meta",
        [
            {
                "offset_ms": 500,
                "message": get_filename(signed_child),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_phases([PHASE0])
@spec_state_test
def test_gossip_beacon_block__reject_slot_not_higher_than_parent(spec, state):
    """
    Test that a block with slot <= parent slot is rejected.
    """
    yield "topic", "meta", "beacon_block"
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)

    yield get_filename(signed_anchor), signed_anchor

    # First, build and add a valid block at slot 1 to be our parent
    parent_block = build_empty_block_for_next_slot(spec, state)
    signed_parent = state_transition_and_sign_block(spec, state, parent_block)

    yield get_filename(signed_parent), signed_parent

    # Add parent to store
    store.blocks[signed_parent.message.hash_tree_root()] = signed_parent.message
    store.block_states[signed_parent.message.hash_tree_root()] = state.copy()

    yield (
        "blocks",
        "meta",
        [
            {"block": get_filename(signed_anchor)},
            {"block": get_filename(signed_parent)},
        ],
    )

    # Get the correct proposer for the parent's slot (we're making a block with same slot)
    proposer_index = signed_parent.message.proposer_index

    # Now build a block that claims the parent but has same slot (not higher)
    block = spec.BeaconBlock(
        slot=signed_parent.message.slot,  # Same slot as parent - invalid!
        proposer_index=proposer_index,
        parent_root=signed_parent.message.hash_tree_root(),
        state_root=state.hash_tree_root(),
    )
    signed_block = sign_block(spec, state, block, proposer_index=proposer_index)

    yield get_filename(signed_block), signed_block

    block_time_ms = spec.compute_time_at_slot_ms(store, block.slot)

    yield "current_time_ms", "meta", int(block_time_ms)

    result, reason = run_validate_beacon_block_gossip(
        spec, seen, store, state, signed_block, block_time_ms + 500
    )
    assert result == "reject"
    assert reason == "block is not from a higher slot than its parent"

    yield (
        "messages",
        "meta",
        [
            {
                "offset_ms": 500,
                "message": get_filename(signed_block),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_phases([PHASE0])
@spec_state_test
def test_gossip_beacon_block__reject_finalized_checkpoint_not_ancestor(spec, state):
    """
    Test that a block whose finalized checkpoint is not an ancestor is rejected.
    """
    yield "topic", "meta", "beacon_block"
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)

    yield get_filename(signed_anchor), signed_anchor

    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block)

    yield get_filename(signed_block), signed_block

    # Add block to store
    store.blocks[signed_block.message.hash_tree_root()] = signed_block.message
    store.block_states[signed_block.message.hash_tree_root()] = state.copy()

    yield (
        "blocks",
        "meta",
        [
            {"block": get_filename(signed_anchor)},
            {"block": get_filename(signed_block)},
        ],
    )

    # Set finalized checkpoint to something that is NOT an ancestor of our block
    fake_finalized_root = spec.Root(b"\xab" * 32)
    store.finalized_checkpoint = spec.Checkpoint(
        epoch=spec.Epoch(0),
        root=fake_finalized_root,
    )

    yield "finalized_checkpoint", "meta", {"epoch": 0, "root": "0x" + "ab" * 32}

    # Get the correct proposer for the child block's slot
    child_slot = signed_block.message.slot + 1
    temp_state = state.copy()
    spec.process_slots(temp_state, child_slot)
    proposer_index = spec.get_beacon_proposer_index(temp_state)

    # Build a child block
    child_block = spec.BeaconBlock(
        slot=child_slot,
        proposer_index=proposer_index,
        parent_root=signed_block.message.hash_tree_root(),
        state_root=temp_state.hash_tree_root(),
    )
    signed_child = sign_block(spec, temp_state, child_block, proposer_index=proposer_index)

    yield get_filename(signed_child), signed_child

    block_time_ms = spec.compute_time_at_slot_ms(store, child_block.slot)

    yield "current_time_ms", "meta", int(block_time_ms)

    result, reason = run_validate_beacon_block_gossip(
        spec, seen, store, state, signed_child, block_time_ms + 500
    )
    assert result == "reject"
    assert reason == "finalized checkpoint is not an ancestor of block"

    yield (
        "messages",
        "meta",
        [
            {
                "offset_ms": 500,
                "message": get_filename(signed_child),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_phases([PHASE0])
@spec_state_test
def test_gossip_beacon_block__reject_invalid_proposer_signature(spec, state):
    """
    Test that a block with an invalid proposer signature is rejected.
    """
    yield "topic", "meta", "beacon_block"
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)

    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block)

    # Corrupt the signature
    signed_block.signature = b"\x00" * 96

    yield get_filename(signed_block), signed_block

    block_time_ms = spec.compute_time_at_slot_ms(store, signed_block.message.slot)

    yield "current_time_ms", "meta", int(block_time_ms)

    result, reason = run_validate_beacon_block_gossip(
        spec, seen, store, state, signed_block, block_time_ms + 500
    )
    assert result == "reject"
    assert reason == "invalid proposer signature"

    yield (
        "messages",
        "meta",
        [
            {
                "offset_ms": 500,
                "message": get_filename(signed_block),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_phases([PHASE0])
@spec_state_test
def test_gossip_beacon_block__reject_invalid_proposer_index(spec, state):
    """
    Test that a block with an out-of-range proposer_index is rejected.
    """
    yield "topic", "meta", "beacon_block"
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)

    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block)

    # Set proposer index to an invalid value.
    signed_block.message.proposer_index = len(state.validators)

    yield get_filename(signed_block), signed_block

    block_time_ms = spec.compute_time_at_slot_ms(store, signed_block.message.slot)

    yield "current_time_ms", "meta", int(block_time_ms)

    result, reason = run_validate_beacon_block_gossip(
        spec, seen, store, state, signed_block, block_time_ms + 500
    )
    assert result == "reject"
    assert reason == "invalid proposer signature"

    yield (
        "messages",
        "meta",
        [
            {
                "offset_ms": 500,
                "message": get_filename(signed_block),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_phases([PHASE0])
@spec_state_test
def test_gossip_beacon_block__reject_wrong_proposer_index(spec, state):
    """
    Test that a block with wrong proposer_index is rejected.
    """
    yield "topic", "meta", "beacon_block"
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)

    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    # Build a valid block for the next slot
    block = build_empty_block_for_next_slot(spec, state)

    # Change proposer_index to wrong value
    correct_proposer = block.proposer_index
    wrong_proposer = (correct_proposer + 1) % len(state.validators)
    block.proposer_index = wrong_proposer

    # Sign with the wrong proposer's key (matching the claimed proposer_index)
    # This way signature verification passes, but proposer_index check fails
    signed_block = sign_block(spec, state, block, proposer_index=wrong_proposer)

    yield get_filename(signed_block), signed_block

    block_time_ms = spec.compute_time_at_slot_ms(store, signed_block.message.slot)

    yield "current_time_ms", "meta", int(block_time_ms)

    result, reason = run_validate_beacon_block_gossip(
        spec, seen, store, state, signed_block, block_time_ms + 500
    )
    assert result == "reject"
    assert reason == "block proposer_index does not match expected proposer"

    yield (
        "messages",
        "meta",
        [
            {
                "offset_ms": 500,
                "message": get_filename(signed_block),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )
