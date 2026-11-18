from eth_consensus_specs.test.context import spec_state_test, with_phases
from eth_consensus_specs.test.helpers.attestations import get_valid_attestation
from eth_consensus_specs.test.helpers.block import (
    build_empty_block,
    build_empty_block_for_next_slot,
)
from eth_consensus_specs.test.helpers.constants import PQ
from eth_consensus_specs.test.helpers.state import (
    next_slots,
    state_transition_and_sign_block,
)
from eth_consensus_specs.test.helpers.withdrawals import set_parent_block_full


@with_phases([PQ])
@spec_state_test
def test_timely_attestation_for_grandparent_uses_its_payload_availability(spec, state):
    """
    Test that a timely attestation for a skipped slot, whose block is the
    grandparent of the including block, is checked against the payload
    availability of that block rather than that of the parent.
    """
    set_parent_block_full(spec, state)

    # Block 1 commits to a payload
    block_1 = build_empty_block_for_next_slot(spec, state)
    block_1_hash = spec.Hash32(b"\x42" * 32)
    block_1.body.signed_execution_payload_bid.message.block_hash = block_1_hash

    yield "pre", state

    signed_block_1 = state_transition_and_sign_block(spec, state, block_1)

    # The next slot is missed. Attest to block 1 there, with and without its payload.
    attestation_slot = block_1.slot + 1
    attestation_state = state.copy()
    next_slots(spec, attestation_state, 1)
    committee = spec.get_beacon_committee(attestation_state, attestation_slot, 0)
    matching_attesters = set(committee[::2])
    mismatching_attesters = set(committee[1::2])
    matching_attestation = get_valid_attestation(
        spec,
        attestation_state,
        slot=attestation_slot,
        payload_index=1,
        filter_participant_set=lambda participants: participants & matching_attesters,
        signed=True,
    )
    mismatching_attestation = get_valid_attestation(
        spec,
        attestation_state,
        slot=attestation_slot,
        payload_index=0,
        filter_participant_set=lambda participants: participants & mismatching_attesters,
        signed=True,
    )

    # Block 3 builds on the payload of block 1, and block 4 builds on block 3
    # without its payload
    block_3 = build_empty_block(spec, state, slot=attestation_slot + 1)
    block_3.body.signed_execution_payload_bid.message.parent_block_hash = block_1_hash
    signed_block_3 = state_transition_and_sign_block(spec, state, block_3)

    block_4 = build_empty_block_for_next_slot(spec, state)
    block_4.body.attestations = spec.Attestations.of(matching_attestation, mismatching_attestation)
    signed_block_4 = state_transition_and_sign_block(spec, state, block_4)

    yield "blocks", [signed_block_1, signed_block_3, signed_block_4]
    yield "post", state

    assert block_4.slot - attestation_slot == spec.MIN_ATTESTATION_INCLUSION_DELAY_PQ
    assert state.execution_payload_availability[attestation_slot % spec.SLOTS_PER_HISTORICAL_ROOT]
    assert not state.execution_payload_availability[block_3.slot % spec.SLOTS_PER_HISTORICAL_ROOT]

    matching_indices = spec.get_attesting_indices(state, matching_attestation)
    mismatching_indices = spec.get_attesting_indices(state, mismatching_attestation)
    assert len(matching_indices) > 0
    assert len(mismatching_indices) > 0
    for validator_index in matching_indices:
        assert spec.has_flag(
            state.current_epoch_participation[validator_index], spec.TIMELY_HEAD_FLAG_INDEX
        )
    for validator_index in mismatching_indices:
        assert not spec.has_flag(
            state.current_epoch_participation[validator_index], spec.TIMELY_HEAD_FLAG_INDEX
        )
