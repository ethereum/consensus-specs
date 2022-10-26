from random import Random

from eth2spec.test.context import (
    with_phases,
    spec_state_test,
)
from eth2spec.test.helpers.constants import CAPELLA
from eth2spec.test.helpers.epoch_processing import (
    run_epoch_processing_to,
)
from eth2spec.test.helpers.random import (
    randomize_state,
)
from eth2spec.test.helpers.withdrawals import (
    set_validator_fully_withdrawable,
)


def run_process_full_withdrawals(spec, state, num_expected_withdrawals=None):
    run_epoch_processing_to(spec, state, 'process_full_withdrawals')

    pre_next_withdrawal_index = state.next_withdrawal_index
    pre_withdrawal_queue = state.withdrawal_queue.copy()
    to_be_withdrawn_indices = [
        index for index, validator in enumerate(state.validators)
        if spec.is_fully_withdrawable_validator(validator, state.balances[index], spec.get_current_epoch(state))
    ]

    if num_expected_withdrawals is not None:
        assert len(to_be_withdrawn_indices) == num_expected_withdrawals
    else:
        num_expected_withdrawals = len(to_be_withdrawn_indices)

    yield 'pre', state
    spec.process_full_withdrawals(state)
    yield 'post', state

    for index in to_be_withdrawn_indices:
        assert state.balances[index] == 0

    assert len(state.withdrawal_queue) == len(pre_withdrawal_queue) + num_expected_withdrawals
    assert state.next_withdrawal_index == pre_next_withdrawal_index + num_expected_withdrawals


@with_phases([CAPELLA])
@spec_state_test
def test_no_withdrawable_validators(spec, state):
    pre_validators = state.validators.copy()
    yield from run_process_full_withdrawals(spec, state, 0)

    assert pre_validators == state.validators


@with_phases([CAPELLA])
@spec_state_test
def test_withdrawable_epoch_but_0_balance(spec, state):
    current_epoch = spec.get_current_epoch(state)
    set_validator_fully_withdrawable(spec, state, 0, current_epoch)

    state.validators[0].effective_balance = 10000000000
    state.balances[0] = 0

    yield from run_process_full_withdrawals(spec, state, 0)


@with_phases([CAPELLA])
@spec_state_test
def test_withdrawable_epoch_but_0_effective_balance_0_balance(spec, state):
    current_epoch = spec.get_current_epoch(state)
    set_validator_fully_withdrawable(spec, state, 0, current_epoch)

    state.validators[0].effective_balance = 0
    state.balances[0] = 0

    yield from run_process_full_withdrawals(spec, state, 0)


@with_phases([CAPELLA])
@spec_state_test
def test_withdrawable_epoch_but_0_effective_balance_nonzero_balance(spec, state):
    current_epoch = spec.get_current_epoch(state)
    set_validator_fully_withdrawable(spec, state, 0, current_epoch)

    state.validators[0].effective_balance = 0
    state.balances[0] = 100000000

    yield from run_process_full_withdrawals(spec, state, 1)


@with_phases([CAPELLA])
@spec_state_test
def test_no_withdrawals_but_some_next_epoch(spec, state):
    current_epoch = spec.get_current_epoch(state)

    # Make a few validators withdrawable at the *next* epoch
    for index in range(3):
        set_validator_fully_withdrawable(spec, state, index, current_epoch + 1)

    yield from run_process_full_withdrawals(spec, state, 0)


@with_phases([CAPELLA])
@spec_state_test
def test_single_withdrawal(spec, state):
    # Make one validator withdrawable
    set_validator_fully_withdrawable(spec, state, 0)

    assert state.next_withdrawal_index == 0
    yield from run_process_full_withdrawals(spec, state, 1)

    assert state.next_withdrawal_index == 1


@with_phases([CAPELLA])
@spec_state_test
def test_multi_withdrawal(spec, state):
    # Make a few validators withdrawable
    for index in range(3):
        set_validator_fully_withdrawable(spec, state, index)

    yield from run_process_full_withdrawals(spec, state, 3)


@with_phases([CAPELLA])
@spec_state_test
def test_all_withdrawal(spec, state):
    # Make all validators withdrawable
    for index in range(len(state.validators)):
        set_validator_fully_withdrawable(spec, state, index)

    yield from run_process_full_withdrawals(spec, state, len(state.validators))


def run_random_full_withdrawals_test(spec, state, rng):
    randomize_state(spec, state, rng)
    for index in range(len(state.validators)):
        # 50% withdrawable
        if rng.choice([True, False]):
            set_validator_fully_withdrawable(spec, state, index)
            validator = state.validators[index]
            # 12.5% unset credentials
            if rng.randint(0, 7) == 0:
                validator.withdrawal_credentials = spec.BLS_WITHDRAWAL_PREFIX + validator.withdrawal_credentials[1:]
            # 12.5% not enough balance
            if rng.randint(0, 7) == 0:
                state.balances[index] = 0
            # 12.5% not close enough epoch
            if rng.randint(0, 7) == 0:
                validator.withdrawable_epoch += 1

    yield from run_process_full_withdrawals(spec, state, None)


@with_phases([CAPELLA])
@spec_state_test
def test_random_withdrawals_0(spec, state):
    yield from run_random_full_withdrawals_test(spec, state, Random(444))


@with_phases([CAPELLA])
@spec_state_test
def test_random_withdrawals_1(spec, state):
    yield from run_random_full_withdrawals_test(spec, state, Random(420))


@with_phases([CAPELLA])
@spec_state_test
def test_random_withdrawals_2(spec, state):
    yield from run_random_full_withdrawals_test(spec, state, Random(200))


@with_phases([CAPELLA])
@spec_state_test
def test_random_withdrawals_3(spec, state):
    yield from run_random_full_withdrawals_test(spec, state, Random(2000000))
