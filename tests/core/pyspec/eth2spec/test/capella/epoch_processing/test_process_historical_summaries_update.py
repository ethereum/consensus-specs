from eth2spec.test.context import (
    spec_state_test,
    with_capella_and_later,
)
from eth2spec.test.helpers.epoch_processing import run_epoch_processing_with


def run_process_historical_summaries_update(spec, state):
    yield from run_epoch_processing_with(spec, state, "process_historical_summaries_update")


@with_capella_and_later
@spec_state_test
def test_historical_summaries_accumulator(spec, state):
    # skip ahead to near the end of the historical batch period (excl block before epoch processing)
    state.slot = spec.SLOTS_PER_HISTORICAL_ROOT - 1
    pre_historical_summaries = state.historical_summaries.copy()

    yield from run_process_historical_summaries_update(spec, state)

    assert len(state.historical_summaries) == len(pre_historical_summaries) + 1
    summary = state.historical_summaries[len(state.historical_summaries) - 1]
    assert summary.block_summary_root == state.block_roots.hash_tree_root()
    assert summary.state_summary_root == state.state_roots.hash_tree_root()
