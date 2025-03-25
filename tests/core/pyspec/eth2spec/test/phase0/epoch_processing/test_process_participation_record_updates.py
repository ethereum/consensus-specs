from eth2spec.test.context import spec_state_test, with_phases
from eth2spec.test.helpers.constants import PHASE0
from eth2spec.test.helpers.epoch_processing import run_epoch_processing_with


def run_process_participation_record_updates(spec, state):
    yield from run_epoch_processing_with(
        spec, state, "process_participation_record_updates"
    )


@with_phases([PHASE0])
@spec_state_test
def test_updated_participation_record(spec, state):
    state.previous_epoch_attestations = [spec.PendingAttestation(proposer_index=100)]
    current_epoch_attestations = [spec.PendingAttestation(proposer_index=200)]
    state.current_epoch_attestations = current_epoch_attestations

    yield from run_process_participation_record_updates(spec, state)

    assert state.previous_epoch_attestations == current_epoch_attestations
    assert state.current_epoch_attestations == []
