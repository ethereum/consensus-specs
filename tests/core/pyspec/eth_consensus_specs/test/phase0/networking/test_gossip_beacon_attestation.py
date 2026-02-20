from eth_consensus_specs.test.context import (
    spec_state_test,
    with_phases,
)
from eth_consensus_specs.test.helpers.attestations import (
    get_valid_attestation,
)
from eth_consensus_specs.test.helpers.block import (
    build_empty_block_for_next_slot,
)
from eth_consensus_specs.test.helpers.constants import PHASE0
from eth_consensus_specs.test.helpers.fork_choice import (
    get_genesis_forkchoice_store_and_block,
)
from eth_consensus_specs.test.helpers.gossip import get_filename, get_seen
from eth_consensus_specs.test.helpers.keys import privkeys
from eth_consensus_specs.test.helpers.state import (
    next_slot,
    state_transition_and_sign_block,
)


def wrap_genesis_block(spec, block):
    """Wrap an unsigned genesis block in a SignedBeaconBlock with empty signature."""
    return spec.SignedBeaconBlock(message=block)


def get_correct_subnet_for_attestation(spec, state, attestation):
    """Get the correct subnet for an attestation."""
    committees_per_slot = spec.get_committee_count_per_slot(state, attestation.data.target.epoch)
    return spec.compute_subnet_for_attestation(
        committees_per_slot, attestation.data.slot, attestation.data.index
    )


def run_validate_beacon_attestation_gossip(
    spec, seen, store, state, attestation, subnet_id, current_time_ms
):
    """
    Run validate_beacon_attestation_gossip and return the result.
    Returns: tuple of (result, reason) where result is "valid", "ignore", or "reject"
             and reason is the exception message (or None for valid).
    """
    try:
        spec.validate_beacon_attestation_gossip(
            seen, store, state, attestation, subnet_id, current_time_ms
        )
        return "valid", None
    except spec.GossipIgnore as e:
        return "ignore", str(e)
    except spec.GossipReject as e:
        return "reject", str(e)


@with_phases([PHASE0])
@spec_state_test
def test_gossip_beacon_attestation__valid(spec, state):
    """
    Test that a valid unaggregated attestation passes gossip validation.
    """
    yield "topic", "meta", "beacon_attestation"
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    anchor_root = anchor_block.hash_tree_root()

    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    next_slot(spec, state)

    # Create an unaggregated attestation (single validator) referencing anchor block
    attestation = get_valid_attestation(
        spec, state, signed=True, index=0, beacon_block_root=anchor_root
    )

    # Make sure it's unaggregated (exactly one bit set)
    committee = spec.get_beacon_committee(state, attestation.data.slot, attestation.data.index)
    single_bit = [False] * len(committee)
    single_bit[0] = True
    attestation.aggregation_bits = spec.Bitlist[spec.MAX_VALIDATORS_PER_COMMITTEE](*single_bit)
    attestation.signature = spec.get_attestation_signature(
        state, attestation.data, privkeys[committee[0]]
    )

    yield get_filename(attestation), attestation

    block_time_ms = spec.compute_time_at_slot_ms(store, attestation.data.slot)

    yield "current_time_ms", "meta", int(block_time_ms)

    subnet_id = get_correct_subnet_for_attestation(spec, state, attestation)
    result, reason = run_validate_beacon_attestation_gossip(
        spec, seen, store, state, attestation, subnet_id, block_time_ms + 500
    )
    assert result == "valid", f"Expected valid but got {result}: {reason}"
    assert reason is None

    yield (
        "messages",
        "meta",
        [
            {
                "subnet_id": int(subnet_id),
                "offset_ms": 500,
                "message": get_filename(attestation),
                "expected": "valid",
            }
        ],
    )


@with_phases([PHASE0])
@spec_state_test
def test_gossip_beacon_attestation__reject_committee_index_out_of_range(spec, state):
    """
    Test that an attestation with committee index out of range is rejected.
    """
    yield "topic", "meta", "beacon_attestation"
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    anchor_root = anchor_block.hash_tree_root()

    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    next_slot(spec, state)

    attestation = get_valid_attestation(spec, state, signed=True, beacon_block_root=anchor_root)

    # Set committee index out of range
    committees_per_slot = spec.get_committee_count_per_slot(state, attestation.data.target.epoch)
    attestation.data.index = committees_per_slot + 10

    yield get_filename(attestation), attestation

    block_time_ms = spec.compute_time_at_slot_ms(store, attestation.data.slot)

    yield "current_time_ms", "meta", int(block_time_ms)

    subnet_id = spec.uint64(0)
    result, reason = run_validate_beacon_attestation_gossip(
        spec, seen, store, state, attestation, subnet_id, block_time_ms + 500
    )
    assert result == "reject"
    assert reason == "committee index out of range"

    yield (
        "messages",
        "meta",
        [
            {
                "subnet_id": int(subnet_id),
                "offset_ms": 500,
                "message": get_filename(attestation),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_phases([PHASE0])
@spec_state_test
def test_gossip_beacon_attestation__reject_wrong_subnet(spec, state):
    """
    Test that an attestation sent to the wrong subnet is rejected.
    """
    yield "topic", "meta", "beacon_attestation"
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    anchor_root = anchor_block.hash_tree_root()

    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    next_slot(spec, state)

    attestation = get_valid_attestation(spec, state, signed=True, beacon_block_root=anchor_root)

    yield get_filename(attestation), attestation

    # Get correct subnet and use a different one
    correct_subnet = get_correct_subnet_for_attestation(spec, state, attestation)
    wrong_subnet = spec.uint64((correct_subnet + 1) % spec.config.ATTESTATION_SUBNET_COUNT)
    block_time_ms = spec.compute_time_at_slot_ms(store, attestation.data.slot)

    yield "current_time_ms", "meta", int(block_time_ms)

    result, reason = run_validate_beacon_attestation_gossip(
        spec, seen, store, state, attestation, wrong_subnet, block_time_ms + 500
    )
    assert result == "reject"
    assert reason == "attestation is for wrong subnet"

    yield (
        "messages",
        "meta",
        [
            {
                "subnet_id": int(wrong_subnet),
                "offset_ms": 500,
                "message": get_filename(attestation),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_phases([PHASE0])
@spec_state_test
def test_gossip_beacon_attestation__ignore_slot_not_in_range(spec, state):
    """
    Test that an attestation with slot not in propagation range is ignored.
    """
    yield "topic", "meta", "beacon_attestation"
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    anchor_root = anchor_block.hash_tree_root()

    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    next_slot(spec, state)

    # Create an unaggregated attestation referencing anchor block
    attestation = get_valid_attestation(spec, state, signed=False, beacon_block_root=anchor_root)

    # Make it unaggregated (exactly one bit set)
    committee = spec.get_beacon_committee(state, attestation.data.slot, attestation.data.index)
    single_bit = [False] * len(committee)
    single_bit[0] = True
    attestation.aggregation_bits = spec.Bitlist[spec.MAX_VALIDATORS_PER_COMMITTEE](*single_bit)
    attestation.signature = spec.get_attestation_signature(
        state, attestation.data, privkeys[committee[0]]
    )

    yield get_filename(attestation), attestation

    # Set current time to be before the attestation slot (too far in future)
    attestation_time_ms = spec.compute_time_at_slot_ms(store, attestation.data.slot)
    current_time_ms = attestation_time_ms - spec.config.MAXIMUM_GOSSIP_CLOCK_DISPARITY - 1

    yield "current_time_ms", "meta", int(current_time_ms)

    subnet_id = get_correct_subnet_for_attestation(spec, state, attestation)
    result, reason = run_validate_beacon_attestation_gossip(
        spec, seen, store, state, attestation, subnet_id, current_time_ms
    )
    assert result == "ignore"
    assert reason == "attestation slot not within propagation range"

    yield (
        "messages",
        "meta",
        [
            {
                "subnet_id": int(subnet_id),
                "offset_ms": 0,
                "message": get_filename(attestation),
                "expected": "ignore",
                "reason": reason,
            }
        ],
    )


@with_phases([PHASE0])
@spec_state_test
def test_gossip_beacon_attestation__valid_within_clock_disparity(spec, state):
    """
    Test that an attestation at exactly the clock disparity boundary is valid.
    """
    yield "topic", "meta", "beacon_attestation"
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    anchor_root = anchor_block.hash_tree_root()

    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    next_slot(spec, state)

    # Create an unaggregated attestation referencing anchor block
    attestation = get_valid_attestation(spec, state, signed=False, beacon_block_root=anchor_root)

    # Make it unaggregated (exactly one bit set)
    committee = spec.get_beacon_committee(state, attestation.data.slot, attestation.data.index)
    single_bit = [False] * len(committee)
    single_bit[0] = True
    attestation.aggregation_bits = spec.Bitlist[spec.MAX_VALIDATORS_PER_COMMITTEE](*single_bit)
    attestation.signature = spec.get_attestation_signature(
        state, attestation.data, privkeys[committee[0]]
    )

    yield get_filename(attestation), attestation

    # Set current time to exactly the boundary (should still be valid)
    attestation_time_ms = spec.compute_time_at_slot_ms(store, attestation.data.slot)
    current_time_ms = attestation_time_ms - spec.config.MAXIMUM_GOSSIP_CLOCK_DISPARITY

    yield "current_time_ms", "meta", int(current_time_ms)

    subnet_id = get_correct_subnet_for_attestation(spec, state, attestation)
    result, reason = run_validate_beacon_attestation_gossip(
        spec, seen, store, state, attestation, subnet_id, current_time_ms
    )
    assert result == "valid", f"Expected valid but got {result}: {reason}"
    assert reason is None

    yield (
        "messages",
        "meta",
        [
            {
                "subnet_id": int(subnet_id),
                "offset_ms": 0,
                "message": get_filename(attestation),
                "expected": "valid",
            }
        ],
    )


@with_phases([PHASE0])
@spec_state_test
def test_gossip_beacon_attestation__reject_epoch_mismatch(spec, state):
    """
    Test that an attestation with mismatched epoch and target is rejected.
    """
    yield "topic", "meta", "beacon_attestation"
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    anchor_root = anchor_block.hash_tree_root()

    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    next_slot(spec, state)

    attestation = get_valid_attestation(spec, state, signed=True, beacon_block_root=anchor_root)

    # Modify target epoch to not match slot
    attestation.data.target.epoch = spec.Epoch(100)

    yield get_filename(attestation), attestation

    block_time_ms = spec.compute_time_at_slot_ms(store, attestation.data.slot)

    yield "current_time_ms", "meta", int(block_time_ms)

    subnet_id = get_correct_subnet_for_attestation(spec, state, attestation)
    result, reason = run_validate_beacon_attestation_gossip(
        spec, seen, store, state, attestation, subnet_id, block_time_ms + 500
    )
    assert result == "reject"
    assert reason == "attestation epoch does not match target epoch"

    yield (
        "messages",
        "meta",
        [
            {
                "subnet_id": int(subnet_id),
                "offset_ms": 500,
                "message": get_filename(attestation),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_phases([PHASE0])
@spec_state_test
def test_gossip_beacon_attestation__reject_not_unaggregated(spec, state):
    """
    Test that an aggregated attestation (more than one bit set) is rejected.
    """
    yield "topic", "meta", "beacon_attestation"
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    anchor_root = anchor_block.hash_tree_root()

    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    next_slot(spec, state)

    # Create an attestation with multiple bits set (aggregated) referencing anchor block
    attestation = get_valid_attestation(spec, state, signed=True, beacon_block_root=anchor_root)

    # Set multiple bits (this makes it aggregated, not unaggregated)
    committee = spec.get_beacon_committee(state, attestation.data.slot, attestation.data.index)
    if len(committee) >= 2:
        multi_bits = [False] * len(committee)
        multi_bits[0] = True
        multi_bits[1] = True
        attestation.aggregation_bits = spec.Bitlist[spec.MAX_VALIDATORS_PER_COMMITTEE](*multi_bits)

    yield get_filename(attestation), attestation

    block_time_ms = spec.compute_time_at_slot_ms(store, attestation.data.slot)

    yield "current_time_ms", "meta", int(block_time_ms)

    subnet_id = get_correct_subnet_for_attestation(spec, state, attestation)
    result, reason = run_validate_beacon_attestation_gossip(
        spec, seen, store, state, attestation, subnet_id, block_time_ms + 500
    )
    assert result == "reject"
    assert reason == "attestation is not unaggregated"

    yield (
        "messages",
        "meta",
        [
            {
                "subnet_id": int(subnet_id),
                "offset_ms": 500,
                "message": get_filename(attestation),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_phases([PHASE0])
@spec_state_test
def test_gossip_beacon_attestation__reject_aggregation_bits_size_mismatch(spec, state):
    """
    Test that an attestation with wrong aggregation bits size is rejected.
    """
    yield "topic", "meta", "beacon_attestation"
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    anchor_root = anchor_block.hash_tree_root()

    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    next_slot(spec, state)

    attestation = get_valid_attestation(spec, state, signed=True, beacon_block_root=anchor_root)

    # Make aggregation bits wrong size
    committee = spec.get_beacon_committee(state, attestation.data.slot, attestation.data.index)
    wrong_size = len(committee) + 5
    wrong_bits = [False] * wrong_size
    wrong_bits[0] = True  # Single bit set (unaggregated)
    attestation.aggregation_bits = spec.Bitlist[spec.MAX_VALIDATORS_PER_COMMITTEE](*wrong_bits)

    yield get_filename(attestation), attestation

    block_time_ms = spec.compute_time_at_slot_ms(store, attestation.data.slot)

    yield "current_time_ms", "meta", int(block_time_ms)

    subnet_id = get_correct_subnet_for_attestation(spec, state, attestation)
    result, reason = run_validate_beacon_attestation_gossip(
        spec, seen, store, state, attestation, subnet_id, block_time_ms + 500
    )
    assert result == "reject"
    assert reason == "aggregation bits length does not match committee size"

    yield (
        "messages",
        "meta",
        [
            {
                "subnet_id": int(subnet_id),
                "offset_ms": 500,
                "message": get_filename(attestation),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_phases([PHASE0])
@spec_state_test
def test_gossip_beacon_attestation__ignore_already_seen(spec, state):
    """
    Test that a duplicate attestation from same validator/epoch is ignored.
    """
    yield "topic", "meta", "beacon_attestation"
    yield "state", state

    messages = []
    seen = get_seen(spec)
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    anchor_root = anchor_block.hash_tree_root()

    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    next_slot(spec, state)

    # Create an unaggregated attestation referencing anchor block
    attestation = get_valid_attestation(spec, state, signed=False, beacon_block_root=anchor_root)

    # Make it unaggregated (exactly one bit set)
    committee = spec.get_beacon_committee(state, attestation.data.slot, attestation.data.index)
    single_bit = [False] * len(committee)
    single_bit[0] = True
    attestation.aggregation_bits = spec.Bitlist[spec.MAX_VALIDATORS_PER_COMMITTEE](*single_bit)
    attestation.signature = spec.get_attestation_signature(
        state, attestation.data, privkeys[committee[0]]
    )

    yield get_filename(attestation), attestation

    block_time_ms = spec.compute_time_at_slot_ms(store, attestation.data.slot)

    yield "current_time_ms", "meta", int(block_time_ms)

    # First validation should pass
    subnet_id = get_correct_subnet_for_attestation(spec, state, attestation)
    result, reason = run_validate_beacon_attestation_gossip(
        spec, seen, store, state, attestation, subnet_id, block_time_ms + 500
    )
    assert result == "valid"
    messages.append(
        {
            "subnet_id": int(subnet_id),
            "offset_ms": 500,
            "message": get_filename(attestation),
            "expected": "valid",
        }
    )

    # Second validation should be ignored
    result, reason = run_validate_beacon_attestation_gossip(
        spec, seen, store, state, attestation, subnet_id, block_time_ms + 600
    )
    assert result == "ignore"
    assert reason == "already seen attestation from this validator for this epoch"
    messages.append(
        {
            "subnet_id": int(subnet_id),
            "offset_ms": 600,
            "message": get_filename(attestation),
            "expected": "ignore",
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_phases([PHASE0])
@spec_state_test
def test_gossip_beacon_attestation__ignore_block_not_seen(spec, state):
    """
    Test that an attestation for an unseen block is ignored.
    """
    yield "topic", "meta", "beacon_attestation"
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)

    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    next_slot(spec, state)

    # Build and apply a block (but don't add to store)
    block = build_empty_block_for_next_slot(spec, state)
    state_transition_and_sign_block(spec, state, block)

    # Create an attestation for the block that's not in store
    attestation = get_valid_attestation(spec, state, signed=False)

    # Make it unaggregated
    committee = spec.get_beacon_committee(state, attestation.data.slot, attestation.data.index)
    single_bit = [False] * len(committee)
    single_bit[0] = True
    attestation.aggregation_bits = spec.Bitlist[spec.MAX_VALIDATORS_PER_COMMITTEE](*single_bit)
    attestation.signature = spec.get_attestation_signature(
        state, attestation.data, privkeys[committee[0]]
    )

    yield get_filename(attestation), attestation

    block_time_ms = spec.compute_time_at_slot_ms(store, attestation.data.slot)

    yield "current_time_ms", "meta", int(block_time_ms)

    subnet_id = get_correct_subnet_for_attestation(spec, state, attestation)
    result, reason = run_validate_beacon_attestation_gossip(
        spec, seen, store, state, attestation, subnet_id, block_time_ms + 500
    )
    assert result == "ignore"
    assert reason == "block being voted for has not been seen"

    yield (
        "messages",
        "meta",
        [
            {
                "subnet_id": int(subnet_id),
                "offset_ms": 500,
                "message": get_filename(attestation),
                "expected": "ignore",
                "reason": reason,
            }
        ],
    )


@with_phases([PHASE0])
@spec_state_test
def test_gossip_beacon_attestation__reject_block_failed_validation(spec, state):
    """
    Test that an attestation for a block that failed validation is rejected.
    """
    yield "topic", "meta", "beacon_attestation"
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)

    yield get_filename(signed_anchor), signed_anchor

    next_slot(spec, state)

    # Build and apply a block
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

    # Create an attestation
    attestation = get_valid_attestation(spec, state, signed=False)

    # Make it unaggregated
    committee = spec.get_beacon_committee(state, attestation.data.slot, attestation.data.index)
    single_bit = [False] * len(committee)
    single_bit[0] = True
    attestation.aggregation_bits = spec.Bitlist[spec.MAX_VALIDATORS_PER_COMMITTEE](*single_bit)
    attestation.signature = spec.get_attestation_signature(
        state, attestation.data, privkeys[committee[0]]
    )

    yield get_filename(attestation), attestation

    block_time_ms = spec.compute_time_at_slot_ms(store, attestation.data.slot)

    yield "current_time_ms", "meta", int(block_time_ms)

    subnet_id = get_correct_subnet_for_attestation(spec, state, attestation)
    result, reason = run_validate_beacon_attestation_gossip(
        spec, seen, store, state, attestation, subnet_id, block_time_ms + 500
    )
    assert result == "reject"
    assert reason == "block being voted for failed validation"

    yield (
        "messages",
        "meta",
        [
            {
                "subnet_id": int(subnet_id),
                "offset_ms": 500,
                "message": get_filename(attestation),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_phases([PHASE0])
@spec_state_test
def test_gossip_beacon_attestation__reject_invalid_signature(spec, state):
    """
    Test that an attestation with invalid signature is rejected.
    """
    yield "topic", "meta", "beacon_attestation"
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    anchor_root = anchor_block.hash_tree_root()

    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    next_slot(spec, state)

    # Create an attestation without signing, referencing anchor block
    attestation = get_valid_attestation(spec, state, signed=False, beacon_block_root=anchor_root)

    # Make it unaggregated
    committee = spec.get_beacon_committee(state, attestation.data.slot, attestation.data.index)
    single_bit = [False] * len(committee)
    single_bit[0] = True
    attestation.aggregation_bits = spec.Bitlist[spec.MAX_VALIDATORS_PER_COMMITTEE](*single_bit)
    # Invalid signature (zeros)
    attestation.signature = spec.BLSSignature(b"\x00" * 96)

    yield get_filename(attestation), attestation

    block_time_ms = spec.compute_time_at_slot_ms(store, attestation.data.slot)

    yield "current_time_ms", "meta", int(block_time_ms)

    subnet_id = get_correct_subnet_for_attestation(spec, state, attestation)
    result, reason = run_validate_beacon_attestation_gossip(
        spec, seen, store, state, attestation, subnet_id, block_time_ms + 500
    )
    assert result == "reject"
    assert reason == "invalid attestation signature"

    yield (
        "messages",
        "meta",
        [
            {
                "subnet_id": int(subnet_id),
                "offset_ms": 500,
                "message": get_filename(attestation),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_phases([PHASE0])
@spec_state_test
def test_gossip_beacon_attestation__reject_target_not_ancestor(spec, state):
    """
    Test that an attestation whose target is not an ancestor of LMD vote is rejected.
    """
    yield "topic", "meta", "beacon_attestation"
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    anchor_root = anchor_block.hash_tree_root()

    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    next_slot(spec, state)

    # Create an attestation with wrong target root, referencing anchor block
    attestation = get_valid_attestation(spec, state, signed=False, beacon_block_root=anchor_root)
    attestation.data.target.root = spec.Root(b"\xcd" * 32)  # Invalid target root

    # Make it unaggregated
    committee = spec.get_beacon_committee(state, attestation.data.slot, attestation.data.index)
    single_bit = [False] * len(committee)
    single_bit[0] = True
    attestation.aggregation_bits = spec.Bitlist[spec.MAX_VALIDATORS_PER_COMMITTEE](*single_bit)
    # Sign with the modified data
    attestation.signature = spec.get_attestation_signature(
        state, attestation.data, privkeys[committee[0]]
    )

    yield get_filename(attestation), attestation

    block_time_ms = spec.compute_time_at_slot_ms(store, attestation.data.slot)

    yield "current_time_ms", "meta", int(block_time_ms)

    subnet_id = get_correct_subnet_for_attestation(spec, state, attestation)
    result, reason = run_validate_beacon_attestation_gossip(
        spec, seen, store, state, attestation, subnet_id, block_time_ms + 500
    )
    assert result == "reject"
    assert reason == "target block is not an ancestor of LMD vote block"

    yield (
        "messages",
        "meta",
        [
            {
                "subnet_id": int(subnet_id),
                "offset_ms": 500,
                "message": get_filename(attestation),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_phases([PHASE0])
@spec_state_test
def test_gossip_beacon_attestation__ignore_finalized_not_ancestor(spec, state):
    """
    Test that an attestation for a block not descending from finalized checkpoint is ignored.
    """
    yield "topic", "meta", "beacon_attestation"
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)

    yield get_filename(signed_anchor), signed_anchor

    next_slot(spec, state)

    # Build and apply a block
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

    # Create an attestation
    attestation = get_valid_attestation(spec, state, signed=False)

    # Make it unaggregated
    committee = spec.get_beacon_committee(state, attestation.data.slot, attestation.data.index)
    single_bit = [False] * len(committee)
    single_bit[0] = True
    attestation.aggregation_bits = spec.Bitlist[spec.MAX_VALIDATORS_PER_COMMITTEE](*single_bit)
    attestation.signature = spec.get_attestation_signature(
        state, attestation.data, privkeys[committee[0]]
    )

    yield get_filename(attestation), attestation

    # Set finalized checkpoint to something that is NOT an ancestor of the block
    store.finalized_checkpoint = spec.Checkpoint(
        epoch=spec.Epoch(0),
        root=spec.Root(b"\xef" * 32),
    )

    yield "finalized_checkpoint", "meta", {"epoch": 0, "root": "0x" + "ef" * 32}

    block_time_ms = spec.compute_time_at_slot_ms(store, attestation.data.slot)

    yield "current_time_ms", "meta", int(block_time_ms)

    subnet_id = get_correct_subnet_for_attestation(spec, state, attestation)
    result, reason = run_validate_beacon_attestation_gossip(
        spec, seen, store, state, attestation, subnet_id, block_time_ms + 500
    )
    assert result == "ignore"
    assert reason == "finalized checkpoint is not an ancestor of block"

    yield (
        "messages",
        "meta",
        [
            {
                "subnet_id": int(subnet_id),
                "offset_ms": 500,
                "message": get_filename(attestation),
                "expected": "ignore",
                "reason": reason,
            }
        ],
    )
