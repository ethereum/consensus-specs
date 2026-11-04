from eth_consensus_specs.test.context import spec_state_test, with_phases
from eth_consensus_specs.test.helpers.builder_deposit_requests import (
    prepare_process_builder_deposit_request,
    run_builder_deposit_request_processing,
)
from eth_consensus_specs.test.helpers.constants import PQ


@with_phases([PQ])
@spec_state_test
def test_new_builder_deposit_kept_pending(spec, state):
    pre_builder_count = len(state.builders)
    request = prepare_process_builder_deposit_request(spec, state, signed=True)

    yield from run_builder_deposit_request_processing(spec, state, request)

    assert len(state.builders) == pre_builder_count
    assert len(state.pq_builders) == pre_builder_count
    assert len(state.pending_builder_deposits) == 1
    pending_deposit = state.pending_builder_deposits[0]
    assert pending_deposit.pubkey == request.pubkey
    assert pending_deposit.withdrawal_credentials == request.withdrawal_credentials
    assert pending_deposit.amount == request.amount
    assert pending_deposit.signature == request.signature
    assert pending_deposit.slot == state.slot


@with_phases([PQ])
@spec_state_test
def test_builder_top_up_kept_pending(spec, state):
    amount = spec.MIN_DEPOSIT_AMOUNT
    pre_balance = state.pq_builders[0].balance
    request = prepare_process_builder_deposit_request(
        spec, state, builder_index=0, amount=amount, signed=True
    )

    yield from run_builder_deposit_request_processing(spec, state, request)

    assert state.pq_builders[0].balance == pre_balance
    assert state.builders[0].balance == pre_balance
    assert len(state.pending_builder_deposits) == 1
    assert state.pending_builder_deposits[0].pubkey == request.pubkey
    assert state.pending_builder_deposits[0].amount == amount
