from eth2spec.test.helpers.epoch_processing import run_epoch_processing_with
from eth2spec.test.context import (
    spec_state_test,
    with_eip7251_and_later,
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
    # No leftover deposit balance to consume when there are no deposits left to process
    assert state.deposit_balance_to_consume == 0
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
    amount = 10 ** 9 + 1
    state.deposit_balance_to_consume = 2 * amount
    state.pending_balance_deposits.append(spec.PendingBalanceDeposit(index=index, amount=amount))
    pre_balance = state.balances[index]
    yield from run_epoch_processing_with(spec, state, 'process_pending_balance_deposits')
    # balance was deposited correctly
    assert state.balances[index] == pre_balance + amount
    # No leftover deposit balance to consume when there are no deposits left to process
    assert state.deposit_balance_to_consume == 0
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
    for i in [0, 1]:
        assert state.balances[i] == pre_balances[i] + amount
    # No leftover deposit balance to consume when there are no deposits left to process
    assert state.deposit_balance_to_consume == 0
    assert state.pending_balance_deposits == []


@with_eip7251_and_later
@spec_state_test
def test_multiple_pending_deposits_above_churn(spec, state):
    # set third deposit to be over the churn
    amount = (spec.get_activation_exit_churn_limit(state) // 3) + 1
    for i in [0, 1, 2]:
        state.pending_balance_deposits.append(spec.PendingBalanceDeposit(index=i, amount=amount))
    pre_balances = state.balances
    yield from run_epoch_processing_with(spec, state, 'process_pending_balance_deposits')
    # First two deposits are processed, third is not because above churn
    for i in [0, 1]:
        assert state.balances[i] == pre_balances[i] + amount
    assert state.balances[2] == pre_balances[2]
    # Only first two subtract from the deposit balance to consume
    assert state.deposit_balance_to_consume == spec.get_activation_exit_churn_limit(state) - 2 * amount
    # third deposit is still in the queue
    assert state.pending_balance_deposits == [spec.PendingBalanceDeposit(index=2, amount=amount)]


@with_eip7251_and_later
@spec_state_test
def test_skipped_deposit_exiting_validator(spec, state):
    index = 0
    amount = spec.MIN_ACTIVATION_BALANCE
    state.pending_balance_deposits.append(spec.PendingBalanceDeposit(index=index, amount=amount))
    pre_pending_balance_deposits = state.pending_balance_deposits
    pre_balance = state.balances[index]
    # Initiate the validator's exit
    spec.initiate_validator_exit(state, index)
    yield from run_epoch_processing_with(spec, state, 'process_pending_balance_deposits')
    # Deposit is skipped because validator is exiting
    assert state.balances[index] == pre_balance
    # All deposits either processed or postponed, no leftover deposit balance to consume 
    assert state.deposit_balance_to_consume == 0
    # The deposit is still in the queue
    assert state.pending_balance_deposits == pre_pending_balance_deposits

@with_eip7251_and_later
@spec_state_test
def test_multiple_skipped_deposits_exiting_validators(spec, state):
    amount = spec.EFFECTIVE_BALANCE_INCREMENT
    for i in [0, 1, 2]:
        # Append pending deposit for validator i
        state.pending_balance_deposits.append(spec.PendingBalanceDeposit(index=i, amount=amount))

        # Initiate the exit of validator i
        spec.initiate_validator_exit(state, i)
    pre_pending_balance_deposits = state.pending_balance_deposits
    pre_balances = state.balances
    yield from run_epoch_processing_with(spec, state, 'process_pending_balance_deposits')
    # All deposits are postponed, no balance changes
    assert state.balances == pre_balances
    # All deposits are postponed, no leftover deposit balance to consume 
    assert state.deposit_balance_to_consume == 0
    # All deposits still in the queue, in the same order
    assert state.pending_balance_deposits == pre_pending_balance_deposits


@with_eip7251_and_later
@spec_state_test
def test_multiple_pending_one_skipped(spec, state):
    amount = spec.EFFECTIVE_BALANCE_INCREMENT
    for i in [0, 1, 2]:
        state.pending_balance_deposits.append(spec.PendingBalanceDeposit(index=i, amount=amount))
    pre_balances = state.balances
    # Initiate the second validator's exit
    spec.initiate_validator_exit(state, 1)
    yield from run_epoch_processing_with(spec, state, 'process_pending_balance_deposits')
    # First and last deposit are processed, second is not because of exiting
    for i in [0, 2]:
        assert state.balances[i] == pre_balances[i] + amount
    assert state.balances[1] == pre_balances[1]
    # All deposits either processed or postponed, no leftover deposit balance to consume 
    assert state.deposit_balance_to_consume == 0
    # second deposit is still in the queue
    assert state.pending_balance_deposits == [spec.PendingBalanceDeposit(index=1, amount=amount)]


@with_eip7251_and_later
@spec_state_test
def test_mixture_of_skipped_and_above_churn(spec, state):
    amount01 = spec.EFFECTIVE_BALANCE_INCREMENT
    amount2 = spec.MAX_EFFECTIVE_BALANCE_EIP7251
    # First two validators have small deposit, third validators a large one
    for i in [0,1]:
        state.pending_balance_deposits.append(spec.PendingBalanceDeposit(index=i, amount=amount01))
    state.pending_balance_deposits.append(spec.PendingBalanceDeposit(index=2, amount=amount2))
    pre_balances = state.balances
    # Initiate the second validator's exit
    spec.initiate_validator_exit(state, 1)
    yield from run_epoch_processing_with(spec, state, 'process_pending_balance_deposits')
    # First deposit is processed
    assert state.balances[0] == pre_balances[0] + amount01
    # Second deposit is postponed, third is above churn
    for i in [1, 2]:
        assert state.balances[i] == pre_balances[i]
    # First deposit consumes some deposit balance, deposit balance to consume is not reset because third deposit is not processed 
    assert state.deposit_balance_to_consume == spec.get_activation_exit_churn_limit(state) - amount01
    # second and third deposit still in the queue, but second is appended at the end
    assert state.pending_balance_deposits == [spec.PendingBalanceDeposit(index=2, amount=amount2), spec.PendingBalanceDeposit(index=1, amount=amount01)]


@with_eip7251_and_later
@spec_state_test
def test_processing_deposit_of_withdrawable_validator(spec, state):
    index = 0
    amount = spec.MIN_ACTIVATION_BALANCE
    state.pending_balance_deposits.append(spec.PendingBalanceDeposit(index=index, amount=amount))
    pre_pending_balance_deposits = state.pending_balance_deposits
    pre_balance = state.balances[index]
    # Initiate the validator's exit
    spec.initiate_validator_exit(state, index)
    # Set epoch to withdrawable epoch + 1 to allow processing of the deposit
    state.slot = spec.SLOTS_PER_EPOCH * (state.validators[index].withdrawable_epoch + 1)
    yield from run_epoch_processing_with(spec, state, 'process_pending_balance_deposits')
    # Deposit is correctly processed
    assert state.balances[index] == pre_balance + amount
    # No leftover deposit balance to consume when there are no deposits left to process
    assert state.deposit_balance_to_consume == 0
    assert state.pending_balance_deposits == []


@with_eip7251_and_later
@spec_state_test
def test_processing_deposit_of_withdrawable_validator_does_not_get_churned(spec, state):
    amount = spec.MAX_EFFECTIVE_BALANCE_EIP7251
    for i in [0,1]:
        state.pending_balance_deposits.append(spec.PendingBalanceDeposit(index=i, amount=amount))
    pre_balances = state.balances
    # Initiate the first validator's exit
    spec.initiate_validator_exit(state, 0)
    # Set epoch to withdrawable epoch + 1 to allow processing of the deposit
    state.slot = spec.SLOTS_PER_EPOCH * (state.validators[0].withdrawable_epoch + 1)
    # Don't use run_epoch_processing_with to avoid penalties being applied
    yield 'pre', state
    spec.process_pending_balance_deposits(state)
    yield 'post', state
    # First deposit is processed though above churn limit, because validator is withdrawable
    assert state.balances[0] == pre_balances[0] + amount
    # Second deposit is not processed because above churn
    print(state.pending_balance_deposits)
    assert state.balances[1] == pre_balances[1]
    # Second deposit is not processed, so there's leftover deposit balance to consume. First deposit does not consume any.
    assert state.deposit_balance_to_consume == spec.get_activation_exit_churn_limit(state)
    assert state.pending_balance_deposits == [spec.PendingBalanceDeposit(index=1, amount=amount)]