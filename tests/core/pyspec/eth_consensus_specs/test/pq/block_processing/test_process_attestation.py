from eth_consensus_specs.test.context import spec_state_test, with_phases
from eth_consensus_specs.test.helpers.attestations import (
    get_valid_attestation,
    run_attestation_processing,
    sign_attestation,
)
from eth_consensus_specs.test.helpers.block import apply_empty_block
from eth_consensus_specs.test.helpers.constants import PQ
from eth_consensus_specs.test.helpers.state import next_slots


def run_skipped_slot_attestation(spec, state, data_slot_available, block_slot_available):
    """
    Process an attestation with ``index = 1`` for skipped slot 4, whose block is
    at slot 3, with the given availability bits at those slots. Return whether
    the attester received the timely head flag.
    """
    apply_empty_block(spec, state, 1)
    apply_empty_block(spec, state, 2)
    apply_empty_block(spec, state, 3)
    next_slots(spec, state, 1 + spec.MIN_ATTESTATION_INCLUSION_DELAY_PQ)
    state.execution_payload_availability[3] = block_slot_available
    state.execution_payload_availability[4] = data_slot_available

    attestation = get_valid_attestation(
        spec, state, slot=4, beacon_block_root=spec.get_block_root_at_slot(state, 4)
    )
    attestation.data.index = 1
    sign_attestation(spec, state, attestation)
    assert not spec.is_attestation_same_slot(state, attestation.data)
    validator_index = next(iter(spec.get_attesting_indices(state, attestation)))

    yield from run_attestation_processing(spec, state, attestation)

    participation = state.current_epoch_participation[validator_index]
    return spec.has_flag(participation, spec.TIMELY_HEAD_FLAG_INDEX)


@with_phases([PQ])
@spec_state_test
def test_skipped_slot_matching_payload_gets_head_flag(spec, state):
    """
    Test that an attestation for a skipped slot gets the head flag when
    ``data.index`` matches the availability bit at ``data.slot``, even if the
    bit at the attested block's slot does not match.
    """
    has_head_flag = yield from run_skipped_slot_attestation(spec, state, 1, 0)
    assert has_head_flag


@with_phases([PQ])
@spec_state_test
def test_skipped_slot_mismatched_payload_no_head_flag(spec, state):
    """
    Test that an attestation for a skipped slot does not get the head flag when
    ``data.index`` does not match the availability bit at ``data.slot``, even if
    the bit at the attested block's slot matches.
    """
    has_head_flag = yield from run_skipped_slot_attestation(spec, state, 0, 1)
    assert not has_head_flag
