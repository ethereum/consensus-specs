from eth2spec.test.context import PHASE1, spec_state_test, with_phases
from eth2spec.test.phase0.epoch_processing.run_epoch_process_base import (
    run_epoch_processing_to, run_process_final_updates,
)
from eth2spec.test.helpers.attestations import get_valid_attestation
from eth2spec.test.helpers.block import build_empty_block_for_next_slot
from eth2spec.test.helpers.state import state_transition_and_sign_block, transition_to


@with_phases([PHASE1])
@spec_state_test
def test_process_online_tracking_no_participants(spec, state):
    run_epoch_processing_to(spec, state, 'process_final_updates')

    for count in state.online_countdown:
        assert count == spec.ONLINE_PERIOD

    yield from run_process_final_updates(spec, state)

    for count in state.online_countdown:
        assert count == spec.ONLINE_PERIOD - 1


@with_phases([PHASE1])
@spec_state_test
def test_process_online_tracking_has_participants(spec, state):
    # Build a block and apply it
    block = build_empty_block_for_next_slot(spec, state)
    attestation = get_valid_attestation(spec, state, index=0, signed=True)
    block.body.attestations.append(attestation)
    participants = set(spec.get_attesting_indices(state, attestation.data, attestation.aggregation_bits))
    assert len(participants) != 0
    state_transition_and_sign_block(spec, state, block)

    # Transition to before `process_final_updates`
    next_epoch = spec.get_current_epoch(state) + 1
    transition_to(spec, state, spec.compute_start_slot_at_epoch(next_epoch) - 1)
    run_epoch_processing_to(spec, state, 'process_final_updates')

    for count in state.online_countdown:
        assert count == spec.ONLINE_PERIOD

    yield from run_process_final_updates(spec, state)

    for index, count in enumerate(state.online_countdown):
        if index in participants:
            assert count == spec.ONLINE_PERIOD
        else:
            assert count == spec.ONLINE_PERIOD - 1
