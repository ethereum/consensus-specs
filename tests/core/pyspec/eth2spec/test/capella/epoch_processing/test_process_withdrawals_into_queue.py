from random import Random

from eth2spec.test.helpers.constants import MINIMAL
from eth2spec.test.context import (
    with_capella_and_later,
    spec_state_test,
    with_presets,
)
from eth2spec.test.helpers.epoch_processing import (
    run_epoch_processing_to,
)
from eth2spec.test.helpers.random import randomize_state
from eth2spec.test.helpers.state import next_epoch
from eth2spec.test.helpers.withdrawals import (
    set_validator_fully_withdrawable,
    set_validator_partially_withdrawable,
    set_eth1_withdrawal_credential_with_balance,
)


def run_process_withdrawals_into_queue(spec, state, num_expected_withdrawals=None):
    run_epoch_processing_to(spec, state, 'process_withdrawals_into_queue')

    pre_next_withdrawal_index = state.next_withdrawal_index
    pre_withdrawal_queue = state.withdrawal_queue.copy()

    fully_withdrawable_indices = []
    partially_withdrawable_indices = []
    for index, validator in enumerate(state.validators):
        if spec.is_fully_withdrawable_validator(validator, state.balances[index], spec.get_current_epoch(state)):
            fully_withdrawable_indices.append(index)
        elif spec.is_partially_withdrawable_validator(validator, state.balances[index]):
            partially_withdrawable_indices.append(index)

    to_be_withdrawn_indices = list(
        set(fully_withdrawable_indices + partially_withdrawable_indices)
    )[:spec.MAX_WITHDRAWALS_PER_EPOCH]
    if num_expected_withdrawals is not None:
        assert min(len(to_be_withdrawn_indices), spec.MAX_WITHDRAWALS_PER_EPOCH) == num_expected_withdrawals
    else:
        num_expected_withdrawals = len(to_be_withdrawn_indices)

    to_be_partially_withdrawn_indices = [
        index for index in partially_withdrawable_indices
        if index in to_be_withdrawn_indices
    ]
    num_partial_withdrawals = len(to_be_partially_withdrawn_indices)

    yield 'pre', state
    spec.process_withdrawals_into_queue(state)
    yield 'post', state

    # check fully withdrawable indices
    for index in fully_withdrawable_indices:
        if index in to_be_withdrawn_indices:
            assert state.balances[index] == 0

    # check partially withdrawable indices
    post_partially_withdrawable_indices = [
        index for index, validator in enumerate(state.validators)
        if (
            not spec.is_fully_withdrawable_validator(validator, state.balances[index], spec.get_current_epoch(state))
            and spec.is_partially_withdrawable_validator(validator, state.balances[index])
        )
    ]
    assert len(partially_withdrawable_indices) - num_partial_withdrawals == len(post_partially_withdrawable_indices)

    assert len(state.withdrawal_queue) == len(pre_withdrawal_queue) + num_expected_withdrawals
    assert state.next_withdrawal_index == pre_next_withdrawal_index + num_expected_withdrawals


#
# Fully
#

@with_capella_and_later
@spec_state_test
def test_no_withdrawable_validators(spec, state):
    pre_validators = state.validators.copy()
    yield from run_process_withdrawals_into_queue(spec, state, 0)

    assert pre_validators == state.validators


@with_capella_and_later
@spec_state_test
def test_withdrawable_epoch_but_0_balance(spec, state):
    current_epoch = spec.get_current_epoch(state)
    set_validator_fully_withdrawable(spec, state, 0, current_epoch)

    state.validators[0].effective_balance = 10000000000
    state.balances[0] = 0

    yield from run_process_withdrawals_into_queue(spec, state, 0)


@with_capella_and_later
@spec_state_test
def test_withdrawable_epoch_but_0_effective_balance_0_balance(spec, state):
    current_epoch = spec.get_current_epoch(state)
    set_validator_fully_withdrawable(spec, state, 0, current_epoch)

    state.validators[0].effective_balance = 0
    state.balances[0] = 0

    yield from run_process_withdrawals_into_queue(spec, state, 0)


@with_capella_and_later
@spec_state_test
def test_withdrawable_epoch_but_0_effective_balance_nonzero_balance(spec, state):
    current_epoch = spec.get_current_epoch(state)
    set_validator_fully_withdrawable(spec, state, 0, current_epoch)

    state.validators[0].effective_balance = 0
    state.balances[0] = 100000000

    yield from run_process_withdrawals_into_queue(spec, state, 1)


@with_capella_and_later
@spec_state_test
def test_no_withdrawals_but_some_next_epoch(spec, state):
    current_epoch = spec.get_current_epoch(state)

    # Make a few validators withdrawable at the *next* epoch
    for index in range(3):
        set_validator_fully_withdrawable(spec, state, index, current_epoch + 1)

    yield from run_process_withdrawals_into_queue(spec, state, 0)


@with_capella_and_later
@spec_state_test
def test_single_withdrawal(spec, state):
    # Make one validator withdrawable
    set_validator_fully_withdrawable(spec, state, 0)

    assert state.next_withdrawal_index == 0
    yield from run_process_withdrawals_into_queue(spec, state, 1)

    assert state.next_withdrawal_index == 1


@with_capella_and_later
@spec_state_test
def test_multi_withdrawal(spec, state):
    # Make a few validators withdrawable
    for index in range(3):
        set_validator_fully_withdrawable(spec, state, index)

    yield from run_process_withdrawals_into_queue(spec, state, 3)


@with_capella_and_later
@spec_state_test
def test_all_withdrawal(spec, state):
    # Make all validators withdrawable
    for index in range(len(state.validators)):
        set_validator_fully_withdrawable(spec, state, index)

    num_expected_withdrawals = min(spec.MAX_WITHDRAWALS_PER_EPOCH, len(state.validators))
    yield from run_process_withdrawals_into_queue(spec, state, num_expected_withdrawals)


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

    yield from run_process_withdrawals_into_queue(spec, state, None)


@with_capella_and_later
@spec_state_test
def test_random_withdrawals_0(spec, state):
    yield from run_random_full_withdrawals_test(spec, state, Random(444))


@with_capella_and_later
@spec_state_test
def test_random_withdrawals_1(spec, state):
    yield from run_random_full_withdrawals_test(spec, state, Random(420))


@with_capella_and_later
@spec_state_test
def test_random_withdrawals_2(spec, state):
    yield from run_random_full_withdrawals_test(spec, state, Random(200))


@with_capella_and_later
@spec_state_test
def test_random_withdrawals_3(spec, state):
    yield from run_random_full_withdrawals_test(spec, state, Random(2000000))

#
# Partial
#


@with_capella_and_later
@spec_state_test
def test_success_no_withdrawable(spec, state):
    pre_validators = state.validators.copy()
    yield from run_process_withdrawals_into_queue(spec, state, 0)

    assert pre_validators == state.validators


@with_capella_and_later
@spec_state_test
def test_success_no_max_effective_balance(spec, state):
    validator_index = len(state.validators) // 2
    # To be partially withdrawable, the validator's effective balance must be maxed out
    set_eth1_withdrawal_credential_with_balance(spec, state, validator_index, spec.MAX_EFFECTIVE_BALANCE - 1)
    validator = state.validators[validator_index]

    assert validator.effective_balance < spec.MAX_EFFECTIVE_BALANCE
    assert not spec.is_partially_withdrawable_validator(validator, state.balances[validator_index])

    yield from run_process_withdrawals_into_queue(spec, state, 0)


@with_capella_and_later
@spec_state_test
def test_success_no_excess_balance(spec, state):
    validator_index = len(state.validators) // 2
    # To be partially withdrawable, the validator needs an excess balance
    set_eth1_withdrawal_credential_with_balance(spec, state, validator_index, spec.MAX_EFFECTIVE_BALANCE)
    validator = state.validators[validator_index]

    assert validator.effective_balance == spec.MAX_EFFECTIVE_BALANCE
    assert not spec.is_partially_withdrawable_validator(validator, state.balances[validator_index])

    yield from run_process_withdrawals_into_queue(spec, state, 0)


@with_capella_and_later
@spec_state_test
def test_success_excess_balance_but_no_max_effective_balance(spec, state):
    validator_index = len(state.validators) // 2
    set_validator_partially_withdrawable(spec, state, validator_index)
    validator = state.validators[validator_index]

    # To be partially withdrawable, the validator needs both a maxed out effective balance and an excess balance
    validator.effective_balance = spec.MAX_EFFECTIVE_BALANCE - 1

    assert not spec.is_partially_withdrawable_validator(validator, state.balances[validator_index])

    yield from run_process_withdrawals_into_queue(spec, state, 0)


@with_capella_and_later
@spec_state_test
def test_success_one_partial_withdrawable(spec, state):
    validator_index = len(state.validators) // 2
    set_validator_partially_withdrawable(spec, state, validator_index)

    yield from run_process_withdrawals_into_queue(spec, state, 1)


@with_capella_and_later
@spec_state_test
def test_success_one_partial_withdrawable_not_yet_active(spec, state):
    validator_index = len(state.validators) // 2
    state.validators[validator_index].activation_epoch += 4
    set_validator_partially_withdrawable(spec, state, validator_index)

    assert not spec.is_active_validator(state.validators[validator_index], spec.get_current_epoch(state))

    yield from run_process_withdrawals_into_queue(spec, state, 1)


@with_capella_and_later
@spec_state_test
def test_success_one_partial_withdrawable_in_exit_queue(spec, state):
    validator_index = len(state.validators) // 2
    state.validators[validator_index].exit_epoch = spec.get_current_epoch(state) + 1
    set_validator_partially_withdrawable(spec, state, validator_index)

    assert spec.is_active_validator(state.validators[validator_index], spec.get_current_epoch(state))
    assert not spec.is_active_validator(state.validators[validator_index], spec.get_current_epoch(state) + 1)

    yield from run_process_withdrawals_into_queue(spec, state, 1)


@with_capella_and_later
@spec_state_test
def test_success_one_partial_withdrawable_exited(spec, state):
    validator_index = len(state.validators) // 2
    state.validators[validator_index].exit_epoch = spec.get_current_epoch(state)
    set_validator_partially_withdrawable(spec, state, validator_index)

    assert not spec.is_active_validator(state.validators[validator_index], spec.get_current_epoch(state))

    yield from run_process_withdrawals_into_queue(spec, state, 1)


@with_capella_and_later
@spec_state_test
def test_success_one_partial_withdrawable_active_and_slashed(spec, state):
    validator_index = len(state.validators) // 2
    state.validators[validator_index].slashed = True
    set_validator_partially_withdrawable(spec, state, validator_index)

    assert spec.is_active_validator(state.validators[validator_index], spec.get_current_epoch(state))

    yield from run_process_withdrawals_into_queue(spec, state, 1)


@with_capella_and_later
@spec_state_test
def test_success_one_partial_withdrawable_exited_and_slashed(spec, state):
    validator_index = len(state.validators) // 2
    state.validators[validator_index].slashed = True
    state.validators[validator_index].exit_epoch = spec.get_current_epoch(state)
    set_validator_partially_withdrawable(spec, state, validator_index)

    assert not spec.is_active_validator(state.validators[validator_index], spec.get_current_epoch(state))

    yield from run_process_withdrawals_into_queue(spec, state, 1)


@with_capella_and_later
@spec_state_test
def test_success_two_partial_withdrawable(spec, state):
    set_validator_partially_withdrawable(spec, state, 0)
    set_validator_partially_withdrawable(spec, state, 1)

    yield from run_process_withdrawals_into_queue(spec, state, 2)


@with_capella_and_later
@spec_state_test
def test_success_max_partial_withdrawable(spec, state):
    # Sanity check that this test works for this state
    assert len(state.validators) >= spec.MAX_WITHDRAWALS_PER_EPOCH

    for i in range(spec.MAX_WITHDRAWALS_PER_EPOCH):
        set_validator_partially_withdrawable(spec, state, i)

    yield from run_process_withdrawals_into_queue(spec, state, spec.MAX_WITHDRAWALS_PER_EPOCH)


@with_capella_and_later
@with_presets([MINIMAL], reason="not enough validators with mainnet config")
@spec_state_test
def test_success_max_plus_one_withdrawable(spec, state):
    # Sanity check that this test works for this state
    assert len(state.validators) >= spec.MAX_WITHDRAWALS_PER_EPOCH + 1

    # More than MAX_WITHDRAWALS_PER_EPOCH partially withdrawable
    for i in range(spec.MAX_WITHDRAWALS_PER_EPOCH + 1):
        set_validator_partially_withdrawable(spec, state, i)

    # Should only have MAX_WITHDRAWALS_PER_EPOCH withdrawals created
    yield from run_process_withdrawals_into_queue(spec, state, spec.MAX_WITHDRAWALS_PER_EPOCH)


def run_random_partial_withdrawals_test(spec, state, rng):
    for _ in range(rng.randint(0, 2)):
        next_epoch(spec, state)
    # NOTE: couldn't run `randomize_state` here because we want to only test partial withdrawal

    num_validators = len(state.validators)
    state.next_withdrawal_validator_index = rng.randint(0, num_validators - 1)

    num_partially_withdrawable = rng.randint(0, num_validators - 1)
    partially_withdrawable_indices = rng.sample(range(num_validators), num_partially_withdrawable)
    for index in partially_withdrawable_indices:
        set_validator_partially_withdrawable(spec, state, index, excess_balance=rng.randint(1, 1000000000))

    # Note: due to the randomness and other epoch processing, some of these set as "partially withdrawable"
    # may not be partially withdrawable once we get to ``process_partial_withdrawals``,
    # thus *not* using the optional third param in this call
    yield from run_process_withdrawals_into_queue(spec, state)


@with_capella_and_later
@spec_state_test
def test_random_0(spec, state):
    yield from run_random_partial_withdrawals_test(spec, state, Random(0))


@with_capella_and_later
@spec_state_test
def test_random_1(spec, state):
    yield from run_random_partial_withdrawals_test(spec, state, Random(1))


@with_capella_and_later
@spec_state_test
def test_random_2(spec, state):
    yield from run_random_partial_withdrawals_test(spec, state, Random(2))


@with_capella_and_later
@spec_state_test
def test_random_3(spec, state):
    yield from run_random_partial_withdrawals_test(spec, state, Random(3))


@with_capella_and_later
@spec_state_test
def test_random_4(spec, state):
    yield from run_random_partial_withdrawals_test(spec, state, Random(4))


@with_capella_and_later
@spec_state_test
def test_random_5(spec, state):
    yield from run_random_partial_withdrawals_test(spec, state, Random(5))
