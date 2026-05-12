from eth_consensus_specs.test.context import (
    spec_state_test,
    with_phases,
    with_presets,
)
from eth_consensus_specs.test.helpers.attestations import (
    get_valid_attestation,
)
from eth_consensus_specs.test.helpers.constants import ELECTRA, MINIMAL
from eth_consensus_specs.test.helpers.fork_choice import (
    get_genesis_forkchoice_store_and_block,
)
from eth_consensus_specs.test.helpers.gossip import get_filename, get_seen, wrap_genesis_block
from eth_consensus_specs.test.helpers.keys import privkeys
from eth_consensus_specs.test.helpers.state import next_slot


def create_signed_aggregate_and_proof(spec, state, attestation):
    committee_index = spec.get_committee_indices(attestation.committee_bits)[0]
    committee = spec.get_beacon_committee(state, attestation.data.slot, committee_index)

    aggregator_index = None
    for index in committee:
        privkey = privkeys[index]
        selection_proof = spec.get_slot_signature(state, attestation.data.slot, privkey)
        if spec.is_aggregator(state, attestation.data.slot, committee_index, selection_proof):
            aggregator_index = index
            break

    if aggregator_index is None:
        aggregator_index = committee[0]

    privkey = privkeys[aggregator_index]
    aggregate_and_proof = spec.get_aggregate_and_proof(
        state, aggregator_index, attestation, privkey
    )
    signature = spec.get_aggregate_and_proof_signature(state, aggregate_and_proof, privkey)

    return spec.SignedAggregateAndProof(message=aggregate_and_proof, signature=signature)


def run_validate_beacon_aggregate_and_proof_gossip(
    spec, seen, store, state, signed_aggregate_and_proof, current_time_ms
):
    try:
        spec.validate_beacon_aggregate_and_proof_gossip(
            seen, store, state, signed_aggregate_and_proof, current_time_ms
        )
        return "valid", None
    except spec.GossipIgnore as e:
        return "ignore", str(e)
    except spec.GossipReject as e:
        return "reject", str(e)


def prepare_signed_aggregate(spec, state):
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    anchor_root = anchor_block.hash_tree_root()
    next_slot(spec, state)
    attestation = get_valid_attestation(spec, state, signed=True, beacon_block_root=anchor_root)
    signed_agg = create_signed_aggregate_and_proof(spec, state, attestation)
    return store, signed_anchor, signed_agg


@with_phases([ELECTRA])
@spec_state_test
@with_presets([MINIMAL], "need multiple committees per slot")
def test_gossip_beacon_aggregate_and_proof__accept_same_data_for_disjoint_committees(spec, state):
    """
    [New in Electra:EIP7549] Test that two committee-local aggregates with equal
    ``AttestationData`` and disjoint ``committee_bits`` are both accepted.
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
    committees_per_slot = spec.get_committee_count_per_slot(state, spec.get_current_epoch(state))
    assert committees_per_slot >= 2, "need at least two committees in the current slot"

    attestation_1 = get_valid_attestation(
        spec,
        state,
        index=0,
        signed=True,
        beacon_block_root=anchor_root,
        filter_participant_set=lambda participants: {sorted(participants)[0]},
    )
    attestation_2 = get_valid_attestation(
        spec,
        state,
        index=1,
        signed=True,
        beacon_block_root=anchor_root,
        filter_participant_set=lambda participants: {sorted(participants)[0]},
    )

    assert attestation_1.data.hash_tree_root() == attestation_2.data.hash_tree_root()
    assert attestation_1.committee_bits != attestation_2.committee_bits

    signed_agg_1 = create_signed_aggregate_and_proof(spec, state, attestation_1)
    signed_agg_2 = create_signed_aggregate_and_proof(spec, state, attestation_2)

    yield get_filename(signed_agg_1), signed_agg_1
    yield get_filename(signed_agg_2), signed_agg_2

    block_time_ms = spec.compute_time_at_slot_ms(state, attestation_1.data.slot)
    yield "current_time_ms", "meta", int(block_time_ms)

    result, reason = run_validate_beacon_aggregate_and_proof_gossip(
        spec, seen, store, state, signed_agg_1, block_time_ms + 500
    )
    assert result == "valid"
    assert reason is None
    messages.append({"offset_ms": 500, "message": get_filename(signed_agg_1), "expected": "valid"})

    result, reason = run_validate_beacon_aggregate_and_proof_gossip(
        spec, seen, store, state, signed_agg_2, block_time_ms + 600
    )
    assert result == "valid"
    assert reason is None
    messages.append({"offset_ms": 600, "message": get_filename(signed_agg_2), "expected": "valid"})

    yield "messages", "meta", messages


@with_phases([ELECTRA])
@spec_state_test
def test_gossip_beacon_aggregate_and_proof__reject_nonzero_data_index(spec, state):
    """
    [New in Electra:EIP7549] Test that an aggregate with ``aggregate.data.index != 0``
    is rejected.
    """
    yield "topic", "meta", "beacon_aggregate_and_proof"
    yield "state", state

    seen = get_seen(spec)
    store, signed_anchor, signed_agg = prepare_signed_aggregate(spec, state)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    # Set a non-zero data index (EIP-7549 forbids this).
    signed_agg.message.aggregate.data.index = spec.CommitteeIndex(1)

    yield get_filename(signed_agg), signed_agg

    block_time_ms = spec.compute_time_at_slot_ms(state, signed_agg.message.aggregate.data.slot)
    yield "current_time_ms", "meta", int(block_time_ms)

    result, reason = run_validate_beacon_aggregate_and_proof_gossip(
        spec, seen, store, state, signed_agg, block_time_ms + 500
    )
    assert result == "reject"
    assert reason == "aggregate data index is non-zero"

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


@with_phases([ELECTRA])
@spec_state_test
def test_gossip_beacon_aggregate_and_proof__reject_zero_committees(spec, state):
    """
    [New in Electra:EIP7549] Test that an aggregate with no committee bits set
    is rejected.
    """
    yield "topic", "meta", "beacon_aggregate_and_proof"
    yield "state", state

    seen = get_seen(spec)
    store, signed_anchor, signed_agg = prepare_signed_aggregate(spec, state)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    # Clear all committee bits.
    signed_agg.message.aggregate.committee_bits = spec.Bitvector[spec.MAX_COMMITTEES_PER_SLOT]()

    yield get_filename(signed_agg), signed_agg

    block_time_ms = spec.compute_time_at_slot_ms(state, signed_agg.message.aggregate.data.slot)
    yield "current_time_ms", "meta", int(block_time_ms)

    result, reason = run_validate_beacon_aggregate_and_proof_gossip(
        spec, seen, store, state, signed_agg, block_time_ms + 500
    )
    assert result == "reject"
    assert reason == "aggregate committee bits must specify exactly one committee"

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


@with_phases([ELECTRA])
@spec_state_test
def test_gossip_beacon_aggregate_and_proof__reject_multiple_committees(spec, state):
    """
    [New in Electra:EIP7549] Test that an aggregate with more than one committee
    bit set is rejected.
    """
    yield "topic", "meta", "beacon_aggregate_and_proof"
    yield "state", state

    seen = get_seen(spec)
    store, signed_anchor, signed_agg = prepare_signed_aggregate(spec, state)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    # Set two committee bits.
    assert spec.MAX_COMMITTEES_PER_SLOT >= 2
    bits = [False] * spec.MAX_COMMITTEES_PER_SLOT
    bits[0] = True
    bits[1] = True
    signed_agg.message.aggregate.committee_bits = spec.Bitvector[spec.MAX_COMMITTEES_PER_SLOT](
        *bits
    )

    yield get_filename(signed_agg), signed_agg

    block_time_ms = spec.compute_time_at_slot_ms(state, signed_agg.message.aggregate.data.slot)
    yield "current_time_ms", "meta", int(block_time_ms)

    result, reason = run_validate_beacon_aggregate_and_proof_gossip(
        spec, seen, store, state, signed_agg, block_time_ms + 500
    )
    assert result == "reject"
    assert reason == "aggregate committee bits must specify exactly one committee"

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
