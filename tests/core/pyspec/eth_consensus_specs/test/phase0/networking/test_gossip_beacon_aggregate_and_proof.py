from eth_consensus_specs.test.context import (
    default_activation_threshold,
    single_phase,
    spec_state_test,
    spec_test,
    with_custom_state,
    with_phases,
    with_presets,
)
from eth_consensus_specs.test.helpers.attestations import (
    get_valid_attestation,
    sign_attestation,
)
from eth_consensus_specs.test.helpers.block import (
    build_empty_block_for_next_slot,
)
from eth_consensus_specs.test.helpers.constants import MAINNET, PHASE0
from eth_consensus_specs.test.helpers.fork_choice import (
    get_genesis_forkchoice_store_and_block,
)
from eth_consensus_specs.test.helpers.gossip import get_filename, get_seen
from eth_consensus_specs.test.helpers.keys import privkeys
from eth_consensus_specs.test.helpers.state import (
    next_slot,
    state_transition_and_sign_block,
)


def large_validator_balances(spec):
    """
    Create enough validators to have committees with >= 32 members,
    so that there's a chance of non-aggregators (modulo >= 2).
    """
    num_validators = 32 * spec.SLOTS_PER_EPOCH
    return [spec.MAX_EFFECTIVE_BALANCE] * num_validators


def wrap_genesis_block(spec, block):
    """Wrap an unsigned genesis block in a SignedBeaconBlock with empty signature."""
    return spec.SignedBeaconBlock(message=block)


def create_signed_aggregate_and_proof(spec, state, attestation, aggregator_index=None):
    """
    Create a valid SignedAggregateAndProof for the given attestation.
    """
    committee = spec.get_beacon_committee(state, attestation.data.slot, attestation.data.index)

    if aggregator_index is None:
        for index in committee:
            privkey = privkeys[index]
            selection_proof = spec.get_slot_signature(state, attestation.data.slot, privkey)
            if spec.is_aggregator(
                state, attestation.data.slot, attestation.data.index, selection_proof
            ):
                aggregator_index = index
                break

        if aggregator_index is None:
            aggregator_index = committee[0]

    privkey = privkeys[aggregator_index]
    aggregate_and_proof = spec.get_aggregate_and_proof(
        state, aggregator_index, attestation, privkey
    )
    signature = spec.get_aggregate_and_proof_signature(state, aggregate_and_proof, privkey)

    return spec.SignedAggregateAndProof(
        message=aggregate_and_proof,
        signature=signature,
    )


def run_validate_beacon_aggregate_and_proof_gossip(
    spec, seen, store, state, signed_aggregate_and_proof, current_time_ms
):
    """
    Run validate_beacon_aggregate_and_proof_gossip and return the result.
    Returns: tuple of (result, reason) where result is "valid", "ignore", or "reject"
             and reason is the exception message (or None for valid).
    """
    try:
        spec.validate_beacon_aggregate_and_proof_gossip(
            seen, store, state, signed_aggregate_and_proof, current_time_ms
        )
        return "valid", None
    except spec.GossipIgnore as e:
        return "ignore", str(e)
    except spec.GossipReject as e:
        return "reject", str(e)


@with_phases([PHASE0])
@spec_state_test
def test_gossip_beacon_aggregate_and_proof__valid(spec, state):
    """
    Test that a valid aggregate and proof passes gossip validation.
    """
    yield "topic", "meta", "beacon_aggregate_and_proof"
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    anchor_root = anchor_block.hash_tree_root()

    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    next_slot(spec, state)

    attestation = get_valid_attestation(spec, state, signed=True, beacon_block_root=anchor_root)
    signed_agg = create_signed_aggregate_and_proof(spec, state, attestation)

    yield get_filename(signed_agg), signed_agg

    block_time_ms = spec.compute_time_at_slot_ms(store, attestation.data.slot)

    yield "current_time_ms", "meta", int(block_time_ms)

    result, reason = run_validate_beacon_aggregate_and_proof_gossip(
        spec, seen, store, state, signed_agg, block_time_ms + 500
    )
    assert result == "valid", f"Expected valid but got {result}: {reason}"
    assert reason is None

    yield (
        "messages",
        "meta",
        [{"offset_ms": 500, "message": get_filename(signed_agg), "expected": "valid"}],
    )


@with_phases([PHASE0])
@spec_state_test
def test_gossip_beacon_aggregate_and_proof__reject_committee_index_out_of_range(spec, state):
    """
    Test that an aggregate with committee index out of range is rejected.
    """
    yield "topic", "meta", "beacon_aggregate_and_proof"
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    anchor_root = anchor_block.hash_tree_root()

    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    next_slot(spec, state)

    attestation = get_valid_attestation(spec, state, signed=True, beacon_block_root=anchor_root)
    signed_agg = create_signed_aggregate_and_proof(spec, state, attestation)

    # Modify committee index to be out of range
    committee_count = spec.get_committee_count_per_slot(state, attestation.data.target.epoch)
    signed_agg.message.aggregate.data.index = committee_count + 10

    yield get_filename(signed_agg), signed_agg

    block_time_ms = spec.compute_time_at_slot_ms(store, attestation.data.slot)

    yield "current_time_ms", "meta", int(block_time_ms)

    result, reason = run_validate_beacon_aggregate_and_proof_gossip(
        spec, seen, store, state, signed_agg, block_time_ms + 500
    )
    assert result == "reject"
    assert reason == "committee index out of range"

    yield (
        "messages",
        "meta",
        [
            {
                "offset_ms": 500,
                "message": get_filename(signed_agg),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_phases([PHASE0])
@spec_state_test
def test_gossip_beacon_aggregate_and_proof__ignore_slot_not_within_range(spec, state):
    """
    Test that an aggregate from a slot too far in the future is ignored.
    """
    yield "topic", "meta", "beacon_aggregate_and_proof"
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    anchor_root = anchor_block.hash_tree_root()

    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    next_slot(spec, state)

    attestation = get_valid_attestation(spec, state, signed=True, beacon_block_root=anchor_root)
    signed_agg = create_signed_aggregate_and_proof(spec, state, attestation)

    yield get_filename(signed_agg), signed_agg

    # Set current time to be before the attestation's slot (too far in future)
    attestation_time_ms = spec.compute_time_at_slot_ms(store, attestation.data.slot)
    current_time_ms = attestation_time_ms - spec.config.MAXIMUM_GOSSIP_CLOCK_DISPARITY - 1

    yield "current_time_ms", "meta", int(current_time_ms)

    result, reason = run_validate_beacon_aggregate_and_proof_gossip(
        spec, seen, store, state, signed_agg, current_time_ms
    )
    assert result == "ignore"
    assert reason == "attestation slot not within propagation range"

    yield (
        "messages",
        "meta",
        [
            {
                "offset_ms": 0,
                "message": get_filename(signed_agg),
                "expected": "ignore",
                "reason": reason,
            }
        ],
    )


@with_phases([PHASE0])
@spec_state_test
def test_gossip_beacon_aggregate_and_proof__valid_within_clock_disparity(spec, state):
    """
    Test that an aggregate at exactly the clock disparity boundary is valid.
    """
    yield "topic", "meta", "beacon_aggregate_and_proof"
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    anchor_root = anchor_block.hash_tree_root()

    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    next_slot(spec, state)

    attestation = get_valid_attestation(spec, state, signed=True, beacon_block_root=anchor_root)
    signed_agg = create_signed_aggregate_and_proof(spec, state, attestation)

    yield get_filename(signed_agg), signed_agg

    # Set current time to exactly the boundary (should still be valid)
    attestation_time_ms = spec.compute_time_at_slot_ms(store, attestation.data.slot)
    current_time_ms = attestation_time_ms - spec.config.MAXIMUM_GOSSIP_CLOCK_DISPARITY

    yield "current_time_ms", "meta", int(current_time_ms)

    result, reason = run_validate_beacon_aggregate_and_proof_gossip(
        spec, seen, store, state, signed_agg, current_time_ms
    )
    assert result == "valid", f"Expected valid but got {result}: {reason}"
    assert reason is None

    yield (
        "messages",
        "meta",
        [
            {
                "offset_ms": 0,
                "message": get_filename(signed_agg),
                "expected": "valid",
            }
        ],
    )


@with_phases([PHASE0])
@spec_state_test
def test_gossip_beacon_aggregate_and_proof__reject_epoch_mismatch(spec, state):
    """
    Test that an aggregate whose epoch doesn't match target is rejected.
    """
    yield "topic", "meta", "beacon_aggregate_and_proof"
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    anchor_root = anchor_block.hash_tree_root()

    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    next_slot(spec, state)

    attestation = get_valid_attestation(spec, state, signed=True, beacon_block_root=anchor_root)
    signed_agg = create_signed_aggregate_and_proof(spec, state, attestation)

    # Modify target epoch to not match slot epoch
    signed_agg.message.aggregate.data.target.epoch = spec.Epoch(100)

    yield get_filename(signed_agg), signed_agg

    block_time_ms = spec.compute_time_at_slot_ms(store, attestation.data.slot)

    yield "current_time_ms", "meta", int(block_time_ms)

    result, reason = run_validate_beacon_aggregate_and_proof_gossip(
        spec, seen, store, state, signed_agg, block_time_ms + 500
    )
    assert result == "reject"
    assert reason == "attestation epoch does not match target epoch"

    yield (
        "messages",
        "meta",
        [
            {
                "offset_ms": 500,
                "message": get_filename(signed_agg),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_phases([PHASE0])
@spec_state_test
def test_gossip_beacon_aggregate_and_proof__ignore_already_seen_aggregate(spec, state):
    """
    Test that a duplicate aggregate data root is ignored.
    """
    yield "topic", "meta", "beacon_aggregate_and_proof"
    yield "state", state

    messages = []
    seen = get_seen(spec)
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    anchor_root = anchor_block.hash_tree_root()

    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    next_slot(spec, state)

    attestation = get_valid_attestation(spec, state, signed=True, beacon_block_root=anchor_root)
    signed_agg = create_signed_aggregate_and_proof(spec, state, attestation)

    yield get_filename(signed_agg), signed_agg

    block_time_ms = spec.compute_time_at_slot_ms(store, attestation.data.slot)

    yield "current_time_ms", "meta", int(block_time_ms)

    # First validation should pass
    result, reason = run_validate_beacon_aggregate_and_proof_gossip(
        spec, seen, store, state, signed_agg, block_time_ms + 500
    )
    assert result == "valid"
    messages.append({"offset_ms": 500, "message": get_filename(signed_agg), "expected": "valid"})

    # Second validation should be ignored (already seen aggregate data)
    result, reason = run_validate_beacon_aggregate_and_proof_gossip(
        spec, seen, store, state, signed_agg, block_time_ms + 600
    )
    assert result == "ignore"
    assert reason == "already seen aggregate for this data"
    messages.append(
        {
            "offset_ms": 600,
            "message": get_filename(signed_agg),
            "expected": "ignore",
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_phases([PHASE0])
@spec_state_test
def test_gossip_beacon_aggregate_and_proof__ignore_same_data_root_without_superset(spec, state):
    """
    Test that dedup does not trigger for the same aggregate data root unless
    a prior aggregate has a non-strict superset of aggregation bits.
    """
    yield "topic", "meta", "beacon_aggregate_and_proof"
    yield "state", state

    messages = []
    seen = get_seen(spec)
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    anchor_root = anchor_block.hash_tree_root()

    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    next_slot(spec, state)

    attestation = get_valid_attestation(
        spec,
        state,
        signed=True,
        beacon_block_root=anchor_root,
        filter_participant_set=lambda participants: {sorted(participants)[0]},
    )
    signed_agg_1 = create_signed_aggregate_and_proof(spec, state, attestation)

    yield get_filename(signed_agg_1), signed_agg_1

    block_time_ms = spec.compute_time_at_slot_ms(store, attestation.data.slot)

    yield "current_time_ms", "meta", int(block_time_ms)

    # First validation should pass and seed dedup state.
    result, reason = run_validate_beacon_aggregate_and_proof_gossip(
        spec, seen, store, state, signed_agg_1, block_time_ms + 500
    )
    assert result == "valid"
    assert reason is None
    messages.append({"offset_ms": 500, "message": get_filename(signed_agg_1), "expected": "valid"})

    # Build a second aggregate with the same data root but a different bitfield
    # that is not a subset of the first one.
    modified_bits = [bool(bit) for bit in signed_agg_1.message.aggregate.aggregation_bits]
    assert len(modified_bits) > 1, "Need committee size > 1 for this test"
    for i, bit in enumerate(modified_bits):
        if not bit:
            modified_bits[i] = True
            break
    else:
        assert False, "Need at least one additional committee participant for this test"

    signed_agg_2 = spec.SignedAggregateAndProof(
        message=spec.AggregateAndProof(
            aggregator_index=signed_agg_1.message.aggregator_index,
            aggregate=spec.Attestation(
                aggregation_bits=spec.Bitlist[spec.MAX_VALIDATORS_PER_COMMITTEE](*modified_bits),
                data=signed_agg_1.message.aggregate.data,
                signature=signed_agg_1.message.aggregate.signature,
            ),
            selection_proof=signed_agg_1.message.selection_proof,
        ),
        signature=signed_agg_1.signature,
    )

    yield get_filename(signed_agg_2), signed_agg_2

    # Dedup should not trigger here; the ignore result is from the aggregator
    # uniqueness rule because aggregator/epoch are unchanged.
    result, reason = run_validate_beacon_aggregate_and_proof_gossip(
        spec, seen, store, state, signed_agg_2, block_time_ms + 600
    )
    assert result == "ignore"
    assert reason == "already seen aggregate from this aggregator for this epoch"
    messages.append(
        {
            "offset_ms": 600,
            "message": get_filename(signed_agg_2),
            "expected": "ignore",
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_phases([PHASE0])
@spec_state_test
def test_gossip_beacon_aggregate_and_proof__ignore_block_not_seen(spec, state):
    """
    Test that an aggregate for an unseen block is ignored.
    """
    yield "topic", "meta", "beacon_aggregate_and_proof"
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)

    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    next_slot(spec, state)

    # Build and apply a block (but don't add to store)
    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block)

    # Create an attestation referencing the unseen block
    attestation = get_valid_attestation(
        spec, state, signed=True, beacon_block_root=signed_block.message.hash_tree_root()
    )
    signed_agg = create_signed_aggregate_and_proof(spec, state, attestation)

    yield get_filename(signed_agg), signed_agg

    block_time_ms = spec.compute_time_at_slot_ms(store, attestation.data.slot)

    yield "current_time_ms", "meta", int(block_time_ms)

    result, reason = run_validate_beacon_aggregate_and_proof_gossip(
        spec, seen, store, state, signed_agg, block_time_ms + 500
    )
    assert result == "ignore"
    assert reason == "block being voted for has not been seen"

    yield (
        "messages",
        "meta",
        [
            {
                "offset_ms": 500,
                "message": get_filename(signed_agg),
                "expected": "ignore",
                "reason": reason,
            }
        ],
    )


@with_phases([PHASE0])
@spec_state_test
def test_gossip_beacon_aggregate_and_proof__reject_aggregation_bits_size_mismatch(spec, state):
    """
    Test that an aggregate with wrong aggregation bits size is rejected.
    """
    yield "topic", "meta", "beacon_aggregate_and_proof"
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    anchor_root = anchor_block.hash_tree_root()

    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    next_slot(spec, state)

    attestation = get_valid_attestation(spec, state, signed=True, beacon_block_root=anchor_root)
    signed_agg = create_signed_aggregate_and_proof(spec, state, attestation)

    # Modify aggregation_bits to have wrong length
    committee = spec.get_beacon_committee(state, attestation.data.slot, attestation.data.index)
    wrong_size = len(committee) + 5
    wrong_bits = [False] * wrong_size
    wrong_bits[0] = True
    signed_agg.message.aggregate.aggregation_bits = spec.Bitlist[spec.MAX_VALIDATORS_PER_COMMITTEE](
        *wrong_bits
    )

    yield get_filename(signed_agg), signed_agg

    block_time_ms = spec.compute_time_at_slot_ms(store, attestation.data.slot)

    yield "current_time_ms", "meta", int(block_time_ms)

    result, reason = run_validate_beacon_aggregate_and_proof_gossip(
        spec, seen, store, state, signed_agg, block_time_ms + 500
    )
    assert result == "reject"
    assert reason == "aggregation bits length does not match committee size"

    yield (
        "messages",
        "meta",
        [
            {
                "offset_ms": 500,
                "message": get_filename(signed_agg),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_phases([PHASE0])
@spec_state_test
def test_gossip_beacon_aggregate_and_proof__reject_no_participants(spec, state):
    """
    Test that an aggregate with no participants is rejected.
    """
    yield "topic", "meta", "beacon_aggregate_and_proof"
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    anchor_root = anchor_block.hash_tree_root()

    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    next_slot(spec, state)

    attestation = get_valid_attestation(spec, state, signed=True, beacon_block_root=anchor_root)
    signed_agg = create_signed_aggregate_and_proof(spec, state, attestation)

    # Set all aggregation bits to False (no participants)
    committee = spec.get_beacon_committee(state, attestation.data.slot, attestation.data.index)
    empty_bits = [False] * len(committee)
    signed_agg.message.aggregate.aggregation_bits = spec.Bitlist[spec.MAX_VALIDATORS_PER_COMMITTEE](
        *empty_bits
    )

    yield get_filename(signed_agg), signed_agg

    block_time_ms = spec.compute_time_at_slot_ms(store, attestation.data.slot)

    yield "current_time_ms", "meta", int(block_time_ms)

    result, reason = run_validate_beacon_aggregate_and_proof_gossip(
        spec, seen, store, state, signed_agg, block_time_ms + 500
    )
    assert result == "reject"
    assert reason == "aggregate has no participants"

    yield (
        "messages",
        "meta",
        [
            {
                "offset_ms": 500,
                "message": get_filename(signed_agg),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_phases([PHASE0])
@spec_state_test
def test_gossip_beacon_aggregate_and_proof__ignore_already_seen_aggregator(spec, state):
    """
    Test that a second aggregate from the same aggregator in the same epoch is ignored.
    """
    yield "topic", "meta", "beacon_aggregate_and_proof"
    yield "state", state

    messages = []
    seen = get_seen(spec)
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    anchor_root = anchor_block.hash_tree_root()

    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    next_slot(spec, state)

    attestation1 = get_valid_attestation(spec, state, signed=True, beacon_block_root=anchor_root)
    signed_agg1 = create_signed_aggregate_and_proof(spec, state, attestation1)

    yield get_filename(signed_agg1), signed_agg1

    block_time_ms = spec.compute_time_at_slot_ms(store, attestation1.data.slot)

    yield "current_time_ms", "meta", int(block_time_ms)

    # First validation should pass
    result, reason = run_validate_beacon_aggregate_and_proof_gossip(
        spec, seen, store, state, signed_agg1, block_time_ms + 500
    )
    assert result == "valid"
    messages.append({"offset_ms": 500, "message": get_filename(signed_agg1), "expected": "valid"})

    # Create a second attestation with different data but same aggregator
    attestation2 = get_valid_attestation(spec, state, signed=True, beacon_block_root=anchor_root)
    attestation2.data.beacon_block_root = spec.Root(b"\xab" * 32)

    aggregator_index = signed_agg1.message.aggregator_index
    signed_agg2 = create_signed_aggregate_and_proof(spec, state, attestation2, aggregator_index)

    yield get_filename(signed_agg2), signed_agg2

    # Second validation should be ignored (same aggregator, same epoch)
    result, reason = run_validate_beacon_aggregate_and_proof_gossip(
        spec, seen, store, state, signed_agg2, block_time_ms + 600
    )
    assert result == "ignore"
    assert reason == "already seen aggregate from this aggregator for this epoch"
    messages.append(
        {
            "offset_ms": 600,
            "message": get_filename(signed_agg2),
            "expected": "ignore",
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_phases([PHASE0])
@with_presets([MAINNET], reason="minimal preset has committees < 16, so everyone is an aggregator")
@spec_test
@with_custom_state(
    balances_fn=large_validator_balances,
    threshold_fn=default_activation_threshold,
)
@single_phase
def test_gossip_beacon_aggregate_and_proof__reject_not_aggregator(spec, state):
    """
    Test that an aggregate from a validator not selected as aggregator is rejected.
    """
    yield "topic", "meta", "beacon_aggregate_and_proof"
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    anchor_root = anchor_block.hash_tree_root()

    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    next_slot(spec, state)

    # Search for a non-aggregator at the current slot across all committees
    non_aggregator_index = None
    target_committee_index = None
    current_slot = state.slot

    committees_per_slot = spec.get_committee_count_per_slot(state, spec.get_current_epoch(state))
    for committee_index in range(committees_per_slot):
        committee = spec.get_beacon_committee(state, current_slot, committee_index)

        for index in committee:
            privkey = privkeys[index]
            selection_proof = spec.get_slot_signature(state, current_slot, privkey)
            if not spec.is_aggregator(state, current_slot, committee_index, selection_proof):
                non_aggregator_index = index
                target_committee_index = committee_index
                break

        if non_aggregator_index is not None:
            break

    assert non_aggregator_index is not None, "Could not find a non-aggregator in any committee"

    attestation = get_valid_attestation(
        spec, state, index=target_committee_index, signed=True, beacon_block_root=anchor_root
    )

    # Create aggregate with non-aggregator
    privkey = privkeys[non_aggregator_index]
    aggregate_and_proof = spec.get_aggregate_and_proof(
        state, non_aggregator_index, attestation, privkey
    )
    signature = spec.get_aggregate_and_proof_signature(state, aggregate_and_proof, privkey)
    signed_agg = spec.SignedAggregateAndProof(
        message=aggregate_and_proof,
        signature=signature,
    )

    yield get_filename(signed_agg), signed_agg

    block_time_ms = spec.compute_time_at_slot_ms(store, attestation.data.slot)

    yield "current_time_ms", "meta", int(block_time_ms)

    result, reason = run_validate_beacon_aggregate_and_proof_gossip(
        spec, seen, store, state, signed_agg, block_time_ms + 500
    )
    assert result == "reject"
    assert reason == "validator is not selected as aggregator"

    yield (
        "messages",
        "meta",
        [
            {
                "offset_ms": 500,
                "message": get_filename(signed_agg),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_phases([PHASE0])
@spec_state_test
def test_gossip_beacon_aggregate_and_proof__reject_aggregator_not_in_committee(spec, state):
    """
    Test that an aggregate from a validator not in the committee is rejected.
    """
    yield "topic", "meta", "beacon_aggregate_and_proof"
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    anchor_root = anchor_block.hash_tree_root()

    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    next_slot(spec, state)

    attestation = get_valid_attestation(spec, state, signed=True, beacon_block_root=anchor_root)
    signed_agg = create_signed_aggregate_and_proof(spec, state, attestation)

    # Find a validator NOT in the committee
    committee = spec.get_beacon_committee(state, attestation.data.slot, attestation.data.index)
    non_committee_index = None
    for i in range(len(state.validators)):
        if i not in committee:
            non_committee_index = i
            break

    # Change aggregator_index to someone not in committee
    signed_agg.message.aggregator_index = non_committee_index

    yield get_filename(signed_agg), signed_agg

    block_time_ms = spec.compute_time_at_slot_ms(store, attestation.data.slot)

    yield "current_time_ms", "meta", int(block_time_ms)

    result, reason = run_validate_beacon_aggregate_and_proof_gossip(
        spec, seen, store, state, signed_agg, block_time_ms + 500
    )
    assert result == "reject"
    assert reason == "aggregator index not in committee"

    yield (
        "messages",
        "meta",
        [
            {
                "offset_ms": 500,
                "message": get_filename(signed_agg),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_phases([PHASE0])
@spec_state_test
def test_gossip_beacon_aggregate_and_proof__reject_aggregator_index_out_of_range(spec, state):
    """
    Test that an aggregate with out-of-range aggregator index is rejected.
    """
    yield "topic", "meta", "beacon_aggregate_and_proof"
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    anchor_root = anchor_block.hash_tree_root()

    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    next_slot(spec, state)

    attestation = get_valid_attestation(spec, state, signed=True, beacon_block_root=anchor_root)
    signed_agg = create_signed_aggregate_and_proof(spec, state, attestation)

    signed_agg.message.aggregator_index = len(state.validators) + 1

    yield get_filename(signed_agg), signed_agg

    block_time_ms = spec.compute_time_at_slot_ms(store, attestation.data.slot)

    yield "current_time_ms", "meta", int(block_time_ms)

    result, reason = run_validate_beacon_aggregate_and_proof_gossip(
        spec, seen, store, state, signed_agg, block_time_ms + 500
    )
    assert result == "reject"
    assert reason == "aggregator index not in committee"

    yield (
        "messages",
        "meta",
        [
            {
                "offset_ms": 500,
                "message": get_filename(signed_agg),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_phases([PHASE0])
@spec_state_test
def test_gossip_beacon_aggregate_and_proof__reject_invalid_selection_proof(spec, state):
    """
    Test that an aggregate with invalid selection proof signature is rejected.
    """
    yield "topic", "meta", "beacon_aggregate_and_proof"
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    anchor_root = anchor_block.hash_tree_root()

    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    next_slot(spec, state)

    attestation = get_valid_attestation(spec, state, signed=True, beacon_block_root=anchor_root)
    signed_agg = create_signed_aggregate_and_proof(spec, state, attestation)

    # Corrupt the selection proof
    signed_agg.message.selection_proof = b"\x00" * 96

    yield get_filename(signed_agg), signed_agg

    block_time_ms = spec.compute_time_at_slot_ms(store, attestation.data.slot)

    yield "current_time_ms", "meta", int(block_time_ms)

    result, reason = run_validate_beacon_aggregate_and_proof_gossip(
        spec, seen, store, state, signed_agg, block_time_ms + 500
    )
    assert result == "reject"
    assert reason == "invalid selection proof signature"

    yield (
        "messages",
        "meta",
        [
            {
                "offset_ms": 500,
                "message": get_filename(signed_agg),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_phases([PHASE0])
@spec_state_test
def test_gossip_beacon_aggregate_and_proof__reject_invalid_aggregator_signature(spec, state):
    """
    Test that an aggregate with invalid aggregator signature is rejected.
    """
    yield "topic", "meta", "beacon_aggregate_and_proof"
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    anchor_root = anchor_block.hash_tree_root()

    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    next_slot(spec, state)

    attestation = get_valid_attestation(spec, state, signed=True, beacon_block_root=anchor_root)
    signed_agg = create_signed_aggregate_and_proof(spec, state, attestation)

    # Corrupt the aggregator signature
    signed_agg.signature = b"\x00" * 96

    yield get_filename(signed_agg), signed_agg

    block_time_ms = spec.compute_time_at_slot_ms(store, attestation.data.slot)

    yield "current_time_ms", "meta", int(block_time_ms)

    result, reason = run_validate_beacon_aggregate_and_proof_gossip(
        spec, seen, store, state, signed_agg, block_time_ms + 500
    )
    assert result == "reject"
    assert reason == "invalid aggregator signature"

    yield (
        "messages",
        "meta",
        [
            {
                "offset_ms": 500,
                "message": get_filename(signed_agg),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_phases([PHASE0])
@spec_state_test
def test_gossip_beacon_aggregate_and_proof__reject_invalid_aggregate_signature(spec, state):
    """
    Test that an aggregate with invalid aggregate attestation signature is rejected.
    """
    yield "topic", "meta", "beacon_aggregate_and_proof"
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    anchor_root = anchor_block.hash_tree_root()

    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    next_slot(spec, state)

    # Create an attestation with INVALID signature BEFORE creating the aggregate
    attestation = get_valid_attestation(spec, state, signed=False, beacon_block_root=anchor_root)
    attestation.signature = spec.BLSSignature(b"\x00" * 96)

    signed_agg = create_signed_aggregate_and_proof(spec, state, attestation)

    yield get_filename(signed_agg), signed_agg

    block_time_ms = spec.compute_time_at_slot_ms(store, attestation.data.slot)

    yield "current_time_ms", "meta", int(block_time_ms)

    result, reason = run_validate_beacon_aggregate_and_proof_gossip(
        spec, seen, store, state, signed_agg, block_time_ms + 500
    )
    assert result == "reject"
    assert reason == "invalid aggregate signature"

    yield (
        "messages",
        "meta",
        [
            {
                "offset_ms": 500,
                "message": get_filename(signed_agg),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_phases([PHASE0])
@spec_state_test
def test_gossip_beacon_aggregate_and_proof__reject_block_failed_validation(spec, state):
    """
    Test that an aggregate for a block that failed validation is rejected.
    """
    yield "topic", "meta", "beacon_aggregate_and_proof"
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

    attestation = get_valid_attestation(spec, state, signed=True)
    signed_agg = create_signed_aggregate_and_proof(spec, state, attestation)

    yield get_filename(signed_agg), signed_agg

    block_time_ms = spec.compute_time_at_slot_ms(store, attestation.data.slot)

    yield "current_time_ms", "meta", int(block_time_ms)

    result, reason = run_validate_beacon_aggregate_and_proof_gossip(
        spec, seen, store, state, signed_agg, block_time_ms + 500
    )
    assert result == "reject"
    assert reason == "block being voted for failed validation"

    yield (
        "messages",
        "meta",
        [
            {
                "offset_ms": 500,
                "message": get_filename(signed_agg),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_phases([PHASE0])
@spec_state_test
def test_gossip_beacon_aggregate_and_proof__reject_target_not_ancestor(spec, state):
    """
    Test that an aggregate whose target is not an ancestor of the LMD vote block is rejected.
    """
    yield "topic", "meta", "beacon_aggregate_and_proof"
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    anchor_root = anchor_block.hash_tree_root()

    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    next_slot(spec, state)

    # Create an attestation with wrong target root BEFORE signing
    attestation = get_valid_attestation(spec, state, signed=False, beacon_block_root=anchor_root)
    attestation.data.target.root = spec.Root(b"\xcd" * 32)
    sign_attestation(spec, state, attestation)

    signed_agg = create_signed_aggregate_and_proof(spec, state, attestation)

    yield get_filename(signed_agg), signed_agg

    block_time_ms = spec.compute_time_at_slot_ms(store, attestation.data.slot)

    yield "current_time_ms", "meta", int(block_time_ms)

    result, reason = run_validate_beacon_aggregate_and_proof_gossip(
        spec, seen, store, state, signed_agg, block_time_ms + 500
    )
    assert result == "reject"
    assert reason == "target block is not an ancestor of LMD vote block"

    yield (
        "messages",
        "meta",
        [
            {
                "offset_ms": 500,
                "message": get_filename(signed_agg),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_phases([PHASE0])
@spec_state_test
def test_gossip_beacon_aggregate_and_proof__ignore_finalized_not_ancestor(spec, state):
    """
    Test that an aggregate for a block not descending from finalized checkpoint is ignored.
    """
    yield "topic", "meta", "beacon_aggregate_and_proof"
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    anchor_root = anchor_block.hash_tree_root()

    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    next_slot(spec, state)

    attestation = get_valid_attestation(spec, state, signed=True, beacon_block_root=anchor_root)
    signed_agg = create_signed_aggregate_and_proof(spec, state, attestation)

    yield get_filename(signed_agg), signed_agg

    # Set finalized checkpoint to something that is NOT an ancestor of the block
    store.finalized_checkpoint = spec.Checkpoint(
        epoch=spec.Epoch(0),
        root=spec.Root(b"\xef" * 32),
    )

    yield "finalized_checkpoint", "meta", {"epoch": 0, "root": "0x" + "ef" * 32}

    block_time_ms = spec.compute_time_at_slot_ms(store, attestation.data.slot)

    yield "current_time_ms", "meta", int(block_time_ms)

    result, reason = run_validate_beacon_aggregate_and_proof_gossip(
        spec, seen, store, state, signed_agg, block_time_ms + 500
    )
    assert result == "ignore"
    assert reason == "finalized checkpoint is not an ancestor of block"

    yield (
        "messages",
        "meta",
        [
            {
                "offset_ms": 500,
                "message": get_filename(signed_agg),
                "expected": "ignore",
                "reason": reason,
            }
        ],
    )
