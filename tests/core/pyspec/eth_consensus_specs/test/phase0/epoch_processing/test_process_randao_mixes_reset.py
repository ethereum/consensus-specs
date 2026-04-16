from eth_consensus_specs.test.context import spec_state_test, with_all_phases
from eth_consensus_specs.test.helpers.epoch_processing import run_epoch_processing_with


def run_process_randao_mixes_reset(spec, state):
    yield from run_epoch_processing_with(spec, state, "process_randao_mixes_reset")


@with_all_phases
@spec_state_test
def test_updated_randao_mixes(spec, state):
    next_epoch = spec.get_current_epoch(state) + 1
    state.randao_mixes[next_epoch % spec.EPOCHS_PER_HISTORICAL_VECTOR] = b"\x56" * 32

    yield from run_process_randao_mixes_reset(spec, state)

    assert state.randao_mixes[
        next_epoch % spec.EPOCHS_PER_HISTORICAL_VECTOR
    ] == spec.get_randao_mix(state, spec.get_current_epoch(state))
