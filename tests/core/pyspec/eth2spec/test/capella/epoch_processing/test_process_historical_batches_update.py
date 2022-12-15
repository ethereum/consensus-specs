from eth2spec.test.context import (
    CAPELLA,
    spec_state_test,
    with_phases,
)
from eth2spec.test.helpers.epoch_processing import (
    run_epoch_processing_with
)


def run_process_historical_batches_update(spec, state):
    yield from run_epoch_processing_with(spec, state, 'process_historical_batches_update')


@with_phases([CAPELLA])
@spec_state_test
def test_historical_batches_accumulator(spec, state):
    # skip ahead to near the end of the historical batch period (excl block before epoch processing)
    state.slot = spec.SLOTS_PER_HISTORICAL_ROOT - 1
    pre_historical_batches = state.historical_batches.copy()

    yield from run_process_historical_batches_update(spec, state)

    assert len(state.historical_batches) == len(pre_historical_batches) + 1
    summary = state.historical_batches[len(state.historical_batches) - 1]
    assert summary.block_batch_root == state.block_roots.hash_tree_root()
    assert summary.state_batch_root == state.state_roots.hash_tree_root()
