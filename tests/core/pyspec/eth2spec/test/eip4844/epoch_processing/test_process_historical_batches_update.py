from eth2spec.test.context import (
    spec_state_test,
    with_eip4844_and_later,
)
from eth2spec.test.helpers.epoch_processing import (
    run_epoch_processing_with
)


def run_process_historical_batches_update(spec, state):
    yield from run_epoch_processing_with(spec, state, 'process_historical_batches_update')


@with_eip4844_and_later
@spec_state_test
def test_no_op(spec, state):
    # skip ahead to near the end of the historical batch period (excl block before epoch processing)
    state.slot = spec.SLOTS_PER_HISTORICAL_ROOT - 1
    historical_batches_len = len(state.historical_batches)

    yield from run_process_historical_batches_update(spec, state)

    assert len(state.historical_batches) == historical_batches_len
