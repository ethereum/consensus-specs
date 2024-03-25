from eth2spec.test.helpers.epoch_processing import run_epoch_processing_with
from eth2spec.test.context import (
    spec_state_test,
    with_eip7251_and_later,
    with_presets,
)

@with_eip7251_and_later
@spec_state_test
def test_pending_deposit_min_activation_balance(spec, state):
    index = 0
    amount = spec.MIN_ACTIVATION_BALANCE
    state.pending_balance_deposits.append(spec.PendingBalanceDeposit(index=index, amount=amount))
    pre_balance = state.balances[index]
    yield from run_epoch_processing_with(spec, state, 'process_pending_balance_deposits')
    assert state.balances[index] == pre_balance + amount
    assert state.deposit_balance_to_consume == spec.get_activation_exit_churn_limit(state) - amount
    assert state.pending_balance_deposits == []

@with_eip7251_and_later
@spec_state_test
def test_pending_deposit_balance_equal_churn(spec, state):
    index = 0
    amount = spec.get_activation_exit_churn_limit(state)
    state.pending_balance_deposits.append(spec.PendingBalanceDeposit(index=index, amount=amount))
    pre_balance = state.balances[index]
    yield from run_epoch_processing_with(spec, state, 'process_pending_balance_deposits')
    assert state.balances[index] == pre_balance + amount
    assert state.deposit_balance_to_consume == 0
    assert state.pending_balance_deposits == []

@with_eip7251_and_later
@spec_state_test
def test_pending_deposit_balance_above_churn(spec, state):
    index = 0
    amount = spec.get_activation_exit_churn_limit(state) + 1
    state.pending_balance_deposits.append(spec.PendingBalanceDeposit(index=index, amount=amount))
    pre_balance = state.balances[index]
    yield from run_epoch_processing_with(spec, state, 'process_pending_balance_deposits')
    # deposit was above churn, balance hasn't changed
    assert state.balances[index] == pre_balance
    # deposit balance to consume is the full churn limit
    assert state.deposit_balance_to_consume == spec.get_activation_exit_churn_limit(state)
    # deposit is still in the queue
    assert state.pending_balance_deposits == [spec.PendingBalanceDeposit(index=index, amount=amount)]

@with_eip7251_and_later
@spec_state_test
def test_pending_deposit_preexisting_churn(spec, state):
    index = 0
    amount = 10**9 + 1
    state.deposit_balance_to_consume = 2*amount
    state.pending_balance_deposits.append(spec.PendingBalanceDeposit(index=index, amount=amount))
    pre_balance = state.balances[index]
    yield from run_epoch_processing_with(spec, state, 'process_pending_balance_deposits')
    # balance was deposited correctly
    assert state.balances[index] == pre_balance + amount
    # the churn limit was added to deposit balance to consume, and the deposited balance was taken from it
    assert state.deposit_balance_to_consume == amount + spec.get_activation_exit_churn_limit(state)
    # queue emptied
    assert state.pending_balance_deposits == []

@with_eip7251_and_later
@spec_state_test
def test_multiple_pending_deposits_below_churn(spec, state):
    amount = 10**9
    state.pending_balance_deposits.append(spec.PendingBalanceDeposit(index=0, amount=amount))
    state.pending_balance_deposits.append(spec.PendingBalanceDeposit(index=1, amount=amount))
    pre_balances = state.balances
    yield from run_epoch_processing_with(spec, state, 'process_pending_balance_deposits')
    for i in [0,1]:
        assert  state.balances[i] == pre_balances[i] + amount
    assert state.deposit_balance_to_consume == spec.get_activation_exit_churn_limit(state) - 2*amount
    assert state.pending_balance_deposits == []

@with_eip7251_and_later
@spec_state_test
def test_multiple_pending_deposits_above_churn(spec, state):
    # set third deposit to be over the churn
    amount = (spec.get_activation_exit_churn_limit(state) // 3) + 1
    for i in [0,1,2]:
        state.pending_balance_deposits.append(spec.PendingBalanceDeposit(index=i, amount=amount))
    pre_balances = state.balances
    yield from run_epoch_processing_with(spec, state, 'process_pending_balance_deposits')
    # First two deposits are processed, third is not because above churn
    for i in [0,1]:
        assert  state.balances[i] == pre_balances[i] + amount
    assert state.balances[2] == pre_balances[2]
    # Only first two subtract from the deposit balance to consume
    assert state.deposit_balance_to_consume == spec.get_activation_exit_churn_limit(state) - 2*amount
    # third deposit is still in the queue
    assert state.pending_balance_deposits == [spec.PendingBalanceDeposit(index=2, amount=amount)]



