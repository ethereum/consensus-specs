from eth2spec.test.context import (
    with_capella_and_later,
    spec_state_test,
)
from eth2spec.test.helpers.epoch_processing import run_epoch_processing_with


def set_validator_withdrawable(spec, state, index, withdrawable_epoch=None):
    if withdrawable_epoch is None:
        withdrawable_epoch = spec.get_current_epoch(state)

    validator = state.validators[index]
    validator.withdrawable_epoch = withdrawable_epoch
    validator.withdrawal_credentials = spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX + validator.withdrawal_credentials[1:]

    assert spec.is_fully_withdrawable_validator(validator, withdrawable_epoch)


def run_process_full_withdrawals(spec, state, num_expected_withdrawals=None):
    pre_next_withdrawal_index = state.next_withdrawal_index
    pre_withdrawal_queue = state.withdrawal_queue.copy()
    to_be_withdrawn_indices = [
        index for index, validator in enumerate(state.validators)
        if spec.is_fully_withdrawable_validator(validator, spec.get_current_epoch(state))
    ]

    if num_expected_withdrawals is not None:
        assert len(to_be_withdrawn_indices) == num_expected_withdrawals
    else:
        num_expected_withdrawals = len(to_be_withdrawn_indices)

    yield from run_epoch_processing_with(spec, state, 'process_full_withdrawals')

    for index in to_be_withdrawn_indices:
        validator = state.validators[index]
        assert validator.fully_withdrawn_epoch == spec.get_current_epoch(state)
        assert state.balances[index] == 0

    assert len(state.withdrawal_queue) == len(pre_withdrawal_queue) + num_expected_withdrawals
    assert state.next_withdrawal_index == pre_next_withdrawal_index + num_expected_withdrawals


@with_capella_and_later
@spec_state_test
def test_no_withdrawals(spec, state):
    pre_validators = state.validators.copy()
    yield from run_process_full_withdrawals(spec, state, 0)

    assert pre_validators == state.validators


@with_capella_and_later
@spec_state_test
def test_no_withdrawals_but_some_next_epoch(spec, state):
    current_epoch = spec.get_current_epoch(state)

    # Make a few validators withdrawable at the *next* epoch
    for index in range(3):
        set_validator_withdrawable(spec, state, index, current_epoch + 1)

    yield from run_process_full_withdrawals(spec, state, 0)


@with_capella_and_later
@spec_state_test
def test_single_withdrawal(spec, state):
    # Make one validator withdrawable
    set_validator_withdrawable(spec, state, 0)

    assert state.next_withdrawal_index == 0
    yield from run_process_full_withdrawals(spec, state, 1)

    assert state.next_withdrawal_index == 1


@with_capella_and_later
@spec_state_test
def test_multi_withdrawal(spec, state):
    # Make a few validators withdrawable
    for index in range(3):
        set_validator_withdrawable(spec, state, index)

    yield from run_process_full_withdrawals(spec, state, 3)


@with_capella_and_later
@spec_state_test
def test_all_withdrawal(spec, state):
    # Make all validators withdrawable
    for index in range(len(state.validators)):
        set_validator_withdrawable(spec, state, index)

    yield from run_process_full_withdrawals(spec, state, len(state.validators))
