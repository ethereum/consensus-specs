from eth_consensus_specs.test.context import spec_state_test, with_phases
from eth_consensus_specs.test.eip8483.block_processing.test_process_builder_pq_registration_request import (
    prepare_builder_pq_registration_request,
)
from eth_consensus_specs.test.gloas.block_processing.test_process_builder_exit_request import (
    advance_past_finalization,
    prepare_builder_exit_request,
    run_builder_exit_request_processing,
)
from eth_consensus_specs.test.helpers.constants import EIP8483


@with_phases([EIP8483])
@spec_state_test
def test_process_builder_exit_request__removes_pq_registration(spec, state):
    advance_past_finalization(spec, state)
    spec.process_builder_pq_registration_request(
        state, prepare_builder_pq_registration_request(spec, state, 0, b"\x22" * 32)
    )
    spec.process_builder_pq_registration_request(
        state, prepare_builder_pq_registration_request(spec, state, 1, b"\x33" * 32)
    )
    request = prepare_builder_exit_request(spec, state, 0)

    yield from run_builder_exit_request_processing(spec, state, request)

    assert len(state.builder_pq_registrations) == 1
    assert state.builder_pq_registrations[0].builder_pubkey == state.builders[1].pubkey


@with_phases([EIP8483])
@spec_state_test
def test_process_builder_exit_request__no_pq_registration(spec, state):
    advance_past_finalization(spec, state)
    spec.process_builder_pq_registration_request(
        state, prepare_builder_pq_registration_request(spec, state, 1, b"\x33" * 32)
    )
    request = prepare_builder_exit_request(spec, state, 0)

    yield from run_builder_exit_request_processing(spec, state, request)

    assert len(state.builder_pq_registrations) == 1
    assert state.builder_pq_registrations[0].builder_pubkey == state.builders[1].pubkey
