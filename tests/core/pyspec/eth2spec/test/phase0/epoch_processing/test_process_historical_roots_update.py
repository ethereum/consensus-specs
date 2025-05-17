from eth2spec.test.context import (
    ALTAIR,
    BELLATRIX,
    PHASE0,
    spec_state_test,
    with_phases,
)
from eth2spec.test.helpers.epoch_processing import run_epoch_processing_with


def run_process_historical_roots_update(spec, state):
    yield from run_epoch_processing_with(spec, state, "process_historical_roots_update")


@with_phases([PHASE0, ALTAIR, BELLATRIX])
@spec_state_test
def test_historical_root_accumulator(spec, state):
    # skip ahead to near the end of the historical roots period (excl block before epoch processing)
    state.slot = spec.SLOTS_PER_HISTORICAL_ROOT - 1
    history_len = len(state.historical_roots)

    yield from run_process_historical_roots_update(spec, state)

    assert len(state.historical_roots) == history_len + 1
