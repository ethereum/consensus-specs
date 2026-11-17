from eth_consensus_specs.test.context import spec_state_test, with_phases
from eth_consensus_specs.test.helpers.attestations import (
    get_aggregate_and_proof,
    get_valid_attestation,
)
from eth_consensus_specs.test.helpers.constants import PQ
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
from eth_consensus_specs.test.helpers.state import next_slot


def create_signed_aggregate_and_proof(spec, state, attestation, aggregator_index):
    privkey = privkeys[aggregator_index]
    aggregate_and_proof = get_aggregate_and_proof(
        spec, state, aggregator_index, attestation, privkey
    )
    signature = spec.get_aggregate_and_proof_signature(state, aggregate_and_proof, privkey)
    return spec.SignedAggregateAndProof(message=aggregate_and_proof, signature=signature)


def run_two_aggregates(spec, state, participants_1, participants_2, expected_2):
    """
    Validate an aggregate of ``participants_1`` and then one of ``participants_2``
    for the same data and committee from another aggregator, expecting the second
    to be ``expected_2``.
    """
    anchor_state = state.copy()
    yield "topic", "meta", "beacon_aggregate_and_proof"
    yield "state", anchor_state

    messages = []
    seen = get_seen(spec)
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    anchor_root = anchor_block.hash_tree_root()

    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    next_slot(spec, state)

    attestation_1 = get_valid_attestation(
        spec,
        state,
        signed=True,
        beacon_block_root=anchor_root,
        filter_participant_set=lambda participants: participants_1,
    )
    attestation_2 = get_valid_attestation(
        spec,
        state,
        signed=True,
        beacon_block_root=anchor_root,
        filter_participant_set=lambda participants: participants_2,
    )
    committee_index = spec.get_committee_indices(attestation_1.committee_bits)[0]
    aggregators = spec.get_aggregation_committee(state, attestation_1.data.slot, committee_index)
    assert len(aggregators) >= 2, "Need at least two aggregators in the committee"

    signed_agg_1 = create_signed_aggregate_and_proof(spec, state, attestation_1, aggregators[0])
    signed_agg_2 = create_signed_aggregate_and_proof(spec, state, attestation_2, aggregators[1])

    yield get_filename(signed_agg_1), signed_agg_1
    yield get_filename(signed_agg_2), signed_agg_2

    current_time_ms = spec.compute_time_at_slot_ms(store.genesis_time_ms, attestation_1.data.slot)
    for signed_agg, expected in ((signed_agg_1, "valid"), (signed_agg_2, expected_2)):
        current_time_ms += 500
        result, reason = run_validate_gossip(
            spec,
            seen=seen,
            store=store,
            signed_aggregate_and_proof=signed_agg,
            current_time_ms=current_time_ms,
            block_payload_statuses={},
        )
        assert result == expected
        message = {
            "current_time_ms": int(current_time_ms),
            "message": get_filename(signed_agg),
            "expected": expected,
        }
        if expected == "ignore":
            assert reason == "aggregate does not have more attesting balance"
            message["reason"] = reason
        messages.append(message)

    yield "messages", "meta", messages


def get_slot_one_committee(spec, state):
    return sorted(spec.get_beacon_committee(state, spec.Slot(state.slot + 1), 0))


@with_phases([PQ])
@spec_state_test
def test_gossip_beacon_aggregate_and_proof__ignore_without_more_attesting_balance(spec, state):
    """
    Test that an aggregate without more attesting balance than one already seen
    for the same data and committee is ignored, even if neither covers the other.
    """
    committee = get_slot_one_committee(spec, state)
    yield from run_two_aggregates(spec, state, {committee[0]}, {committee[1]}, "ignore")


@with_phases([PQ])
@spec_state_test
def test_gossip_beacon_aggregate_and_proof__accept_fewer_attesters_with_more_balance(spec, state):
    """
    Test that an aggregate with fewer attesters but more attesting balance than
    one already seen for the same data and committee is accepted.
    """
    committee = get_slot_one_committee(spec, state)
    state.validators[committee[2]].effective_balance = spec.MAX_EFFECTIVE_BALANCE_ELECTRA
    state.balances[committee[2]] = spec.MAX_EFFECTIVE_BALANCE_ELECTRA
    yield from run_two_aggregates(
        spec, state, {committee[0], committee[1]}, {committee[2]}, "valid"
    )
