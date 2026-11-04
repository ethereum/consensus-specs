from eth_consensus_specs.test.context import spec_state_test, with_phases
from eth_consensus_specs.test.gloas.block_processing.test_process_builder_exit_request import (
    advance_past_finalization,
    prepare_builder_exit_request,
    run_builder_exit_request_processing,
)
from eth_consensus_specs.test.helpers.constants import PQ


@with_phases([PQ])
@spec_state_test
def test_builder_exit_request_ignored(spec, state):
    builder_index = 0
    advance_past_finalization(spec, state)
    assert spec.is_active_builder(state, builder_index)
    builder_exit_request = prepare_builder_exit_request(spec, state, builder_index)

    yield from run_builder_exit_request_processing(spec, state, builder_exit_request, valid=False)

    assert spec.is_active_builder(state, builder_index)
