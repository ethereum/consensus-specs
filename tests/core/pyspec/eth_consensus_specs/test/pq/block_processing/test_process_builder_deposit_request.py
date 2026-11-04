from eth_consensus_specs.test.context import spec_state_test, with_phases
from eth_consensus_specs.test.helpers.builder_deposit_requests import (
    prepare_process_builder_deposit_request,
    run_builder_deposit_request_processing,
)
from eth_consensus_specs.test.helpers.constants import PQ


@with_phases([PQ])
@spec_state_test
def test_new_builder_deposit_ignored(spec, state):
    request = prepare_process_builder_deposit_request(spec, state, signed=True)
    pre_state = state.copy()

    yield from run_builder_deposit_request_processing(spec, state, request)

    assert state == pre_state


@with_phases([PQ])
@spec_state_test
def test_builder_top_up_ignored(spec, state):
    request = prepare_process_builder_deposit_request(
        spec, state, builder_index=0, amount=spec.MIN_DEPOSIT_AMOUNT, signed=True
    )
    pre_state = state.copy()

    yield from run_builder_deposit_request_processing(spec, state, request)

    assert state == pre_state
