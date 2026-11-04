from eth_consensus_specs.test.context import spec_state_test, with_phases
from eth_consensus_specs.test.helpers.constants import PQ
from eth_consensus_specs.test.helpers.deposits import prepare_pending_deposit
from eth_consensus_specs.test.helpers.epoch_processing import run_epoch_processing_with


@with_phases([PQ])
@spec_state_test
def test_new_validator_deposit_postponed(spec, state):
    new_index = len(state.validators)
    deposit = prepare_pending_deposit(spec, new_index, spec.MIN_ACTIVATION_BALANCE, signed=True)
    state.pending_deposits.append(deposit)

    yield from run_epoch_processing_with(spec, state, "process_pending_deposits")

    assert len(state.validators) == new_index
    assert len(state.pq_validators) == new_index
    assert state.pending_deposits == spec.PendingDeposits(data=[deposit])
    assert state.deposit_balance_to_consume == 0


@with_phases([PQ])
@spec_state_test
def test_top_up_behind_new_validator_deposit(spec, state):
    new_index = len(state.validators)
    amount = spec.EFFECTIVE_BALANCE_INCREMENT
    new_deposit = prepare_pending_deposit(spec, new_index, spec.MIN_ACTIVATION_BALANCE, signed=True)
    top_up = prepare_pending_deposit(spec, 0, amount)
    state.pending_deposits.append(new_deposit)
    state.pending_deposits.append(top_up)
    pre_balance = state.balances[0]

    yield from run_epoch_processing_with(spec, state, "process_pending_deposits")

    assert state.balances[0] == pre_balance + amount
    assert state.pending_deposits == spec.PendingDeposits(data=[new_deposit])
