import random
from eth2spec.test.helpers.constants import MINIMAL
from eth2spec.test.context import (
    with_capella_and_later,
    spec_state_test,
    with_presets,
)
from eth2spec.test.helpers.epoch_processing import run_epoch_processing_to
from eth2spec.test.helpers.state import next_epoch
from eth2spec.test.helpers.random import randomize_state


def set_validator_partially_withdrawable(spec, state, index, rng=random.Random(666)):
    validator = state.validators[index]
    validator.withdrawal_credentials = spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX + validator.withdrawal_credentials[1:]
    validator.effective_balance = spec.MAX_EFFECTIVE_BALANCE
    state.balances[index] = spec.MAX_EFFECTIVE_BALANCE + rng.randint(1, 100000000)

    assert spec.is_partially_withdrawable_validator(validator, state.balances[index])


def run_process_partial_withdrawals(spec, state, num_expected_withdrawals=None):
    # Run rest of epoch processing before predicting partial withdrawals as
    # balance changes can affect withdrawability
    run_epoch_processing_to(spec, state, 'process_partial_withdrawals')

    pre_next_withdrawal_index = state.next_withdrawal_index
    pre_withdrawal_queue = state.withdrawal_queue.copy()

    partially_withdrawable_indices = [
        index for index, validator in enumerate(state.validators)
        if spec.is_partially_withdrawable_validator(validator, state.balances[index])
    ]
    num_partial_withdrawals = min(len(partially_withdrawable_indices), spec.MAX_PARTIAL_WITHDRAWALS_PER_EPOCH)

    if num_expected_withdrawals is not None:
        assert num_partial_withdrawals == num_expected_withdrawals
    else:
        num_expected_withdrawals = num_partial_withdrawals

    yield 'pre', state
    spec.process_partial_withdrawals(state)
    yield 'post', state

    post_partially_withdrawable_indices = [
        index for index, validator in enumerate(state.validators)
        if spec.is_partially_withdrawable_validator(validator, state.balances[index])
    ]

    assert len(partially_withdrawable_indices) - num_partial_withdrawals == len(post_partially_withdrawable_indices)

    assert len(state.withdrawal_queue) == len(pre_withdrawal_queue) + num_expected_withdrawals
    assert state.next_withdrawal_index == pre_next_withdrawal_index + num_expected_withdrawals


@with_capella_and_later
@spec_state_test
def test_success_no_withdrawable(spec, state):
    pre_validators = state.validators.copy()
    yield from run_process_partial_withdrawals(spec, state, 0)

    assert pre_validators == state.validators


@with_capella_and_later
@spec_state_test
def test_success_one_partial_withdrawable(spec, state):
    validator_index = len(state.validators) // 2
    set_validator_partially_withdrawable(spec, state, validator_index)

    yield from run_process_partial_withdrawals(spec, state, 1)


@with_capella_and_later
@spec_state_test
def test_success_one_partial_withdrawable_not_yet_active(spec, state):
    validator_index = len(state.validators) // 2
    state.validators[validator_index].activation_epoch += 4
    set_validator_partially_withdrawable(spec, state, validator_index)

    assert not spec.is_active_validator(state.validators[validator_index], spec.get_current_epoch(state))

    yield from run_process_partial_withdrawals(spec, state, 1)


@with_capella_and_later
@spec_state_test
def test_success_one_partial_withdrawable_in_exit_queue(spec, state):
    validator_index = len(state.validators) // 2
    state.validators[validator_index].exit_epoch = spec.get_current_epoch(state) + 1
    set_validator_partially_withdrawable(spec, state, validator_index)

    assert spec.is_active_validator(state.validators[validator_index], spec.get_current_epoch(state))
    assert not spec.is_active_validator(state.validators[validator_index], spec.get_current_epoch(state) + 1)

    yield from run_process_partial_withdrawals(spec, state, 1)


@with_capella_and_later
@spec_state_test
def test_success_one_partial_withdrawable_exited(spec, state):
    validator_index = len(state.validators) // 2
    state.validators[validator_index].exit_epoch = spec.get_current_epoch(state)
    set_validator_partially_withdrawable(spec, state, validator_index)

    assert not spec.is_active_validator(state.validators[validator_index], spec.get_current_epoch(state))

    yield from run_process_partial_withdrawals(spec, state, 1)


@with_capella_and_later
@spec_state_test
def test_success_one_partial_withdrawable_active_and_slashed(spec, state):
    validator_index = len(state.validators) // 2
    state.validators[validator_index].slashed = True
    set_validator_partially_withdrawable(spec, state, validator_index)

    assert spec.is_active_validator(state.validators[validator_index], spec.get_current_epoch(state))

    yield from run_process_partial_withdrawals(spec, state, 1)


@with_capella_and_later
@spec_state_test
def test_success_one_partial_withdrawable_exited_and_slashed(spec, state):
    validator_index = len(state.validators) // 2
    state.validators[validator_index].slashed = True
    state.validators[validator_index].exit_epoch = spec.get_current_epoch(state)
    set_validator_partially_withdrawable(spec, state, validator_index)

    assert not spec.is_active_validator(state.validators[validator_index], spec.get_current_epoch(state))

    yield from run_process_partial_withdrawals(spec, state, 1)


@with_capella_and_later
@spec_state_test
def test_success_two_partial_withdrawable(spec, state):
    set_validator_partially_withdrawable(spec, state, 0)
    set_validator_partially_withdrawable(spec, state, 1)

    yield from run_process_partial_withdrawals(spec, state, 2)


@with_capella_and_later
@spec_state_test
def test_success_max_partial_withdrawable(spec, state):
    # Sanity check that this test works for this state
    assert len(state.validators) >= spec.MAX_PARTIAL_WITHDRAWALS_PER_EPOCH

    for i in range(spec.MAX_PARTIAL_WITHDRAWALS_PER_EPOCH):
        set_validator_partially_withdrawable(spec, state, i)

    yield from run_process_partial_withdrawals(spec, state, spec.MAX_PARTIAL_WITHDRAWALS_PER_EPOCH)


@with_capella_and_later
@with_presets([MINIMAL], reason="not no enough validators with mainnet config")
@spec_state_test
def test_success_max_plus_one_withdrawable(spec, state):
    # Sanity check that this test works for this state
    assert len(state.validators) >= spec.MAX_PARTIAL_WITHDRAWALS_PER_EPOCH + 1

    # More than MAX_PARTIAL_WITHDRAWALS_PER_EPOCH partially withdrawable
    for i in range(spec.MAX_PARTIAL_WITHDRAWALS_PER_EPOCH + 1):
        set_validator_partially_withdrawable(spec, state, i)

    # Should only have MAX_PARTIAL_WITHDRAWALS_PER_EPOCH withdrawals created
    yield from run_process_partial_withdrawals(spec, state, spec.MAX_PARTIAL_WITHDRAWALS_PER_EPOCH)


def run_random_partial_withdrawals_test(spec, state, rng):
    for _ in range(rng.randint(0, 2)):
        next_epoch(spec, state)
    randomize_state(spec, state, rng)

    num_validators = len(state.validators)
    state.next_partial_withdrawal_validator_index = rng.randint(0, num_validators - 1)

    num_partially_withdrawable = rng.randint(0, num_validators - 1)
    partially_withdrawable_indices = rng.sample(range(num_validators), num_partially_withdrawable)
    for index in partially_withdrawable_indices:
        set_validator_partially_withdrawable(spec, state, index)

    # Note: due to the randomness and other epoch processing, some of these set as "partially withdrawable"
    # may not be partially withdrawable once we get to ``process_partial_withdrawals``,
    # thus *not* using the optional third param in this call
    yield from run_process_partial_withdrawals(spec, state)


@with_capella_and_later
@spec_state_test
def test_random_0(spec, state):
    yield from run_random_partial_withdrawals_test(spec, state, random.Random(0))


@with_capella_and_later
@spec_state_test
def test_random_1(spec, state):
    yield from run_random_partial_withdrawals_test(spec, state, random.Random(1))


@with_capella_and_later
@spec_state_test
def test_random_2(spec, state):
    yield from run_random_partial_withdrawals_test(spec, state, random.Random(2))


@with_capella_and_later
@spec_state_test
def test_random_3(spec, state):
    yield from run_random_partial_withdrawals_test(spec, state, random.Random(3))


@with_capella_and_later
@spec_state_test
def test_random_4(spec, state):
    yield from run_random_partial_withdrawals_test(spec, state, random.Random(4))


@with_capella_and_later
@spec_state_test
def test_random_5(spec, state):
    yield from run_random_partial_withdrawals_test(spec, state, random.Random(5))
