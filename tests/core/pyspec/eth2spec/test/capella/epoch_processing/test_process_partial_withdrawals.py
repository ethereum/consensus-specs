from eth2spec.test.context import (
    with_capella_and_later,
    spec_state_test,
)
from eth2spec.test.helpers.epoch_processing import run_epoch_processing_with


def set_validator_partiall_withdrawable(spec, state, index):
    validator = state.validators[index]
    validator.withdrawal_credentials = spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX + validator.withdrawal_credentials[1:]
    validator.effective_balance = spec.MAX_EFFECTIVE_BALANCE
    state.balances[index] = spec.MAX_EFFECTIVE_BALANCE + 500  # make a random increase

    assert spec.partially_withdrawable_indices(validator, state.balances[index])


def run_process_partial_withdrawals(spec, state, num_expected_withdrawals=None):
    pre_withdrawal_index = state.withdrawal_index
    pre_withdrawals_queue = state.withdrawals_queue
    partially_withdrawable_indices = [
        index for index, validator in enumerate(state.validators)
        if spec.is_partially_withdrawable_validator(validator, state.balances[index])
    ]
    num_partial_withdrawals = min(len(partially_withdrawable_indices), spec.MAX_PARTIAL_WITHDRAWALS_PER_EPOCH)

    if num_expected_withdrawals is not None:
        assert num_partial_withdrawals == num_expected_withdrawals
    else:
        num_expected_withdrawals = num_partial_withdrawals

    yield from run_epoch_processing_with(spec, state, 'process_partial_withdrawals')

    post_partially_withdrawable_indices = [
        index for index, validator in enumerate(state.validators)
        if spec.is_partially_withdrawable_validator(validator, state.balances[index])
    ]

    assert len(partially_withdrawable_indices) - num_partial_withdrawals == len(post_partially_withdrawable_indices)

    assert len(state.withdrawals_queue) == len(pre_withdrawals_queue) + num_expected_withdrawals
    assert state.withdrawal_index == pre_withdrawal_index + num_expected_withdrawals


@with_capella_and_later
@spec_state_test
def test_no_partial_withdrawals(spec, state):
    pre_validators = state.validators.copy()
    yield from run_process_partial_withdrawals(spec, state, 0)

    assert pre_validators == state.validators
