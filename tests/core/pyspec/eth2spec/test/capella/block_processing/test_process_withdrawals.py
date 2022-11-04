import random

from eth2spec.test.context import (
    spec_state_test,
    expect_assertion_error,
    with_capella_and_later,
    with_presets,
)
from eth2spec.test.helpers.constants import MINIMAL
from eth2spec.test.helpers.execution_payload import (
    build_empty_execution_payload,
)
from eth2spec.test.helpers.random import (
    randomize_state,
)
from eth2spec.test.helpers.state import (
    next_epoch,
    next_slot,
)
from eth2spec.test.helpers.withdrawals import (
    set_eth1_withdrawal_credential_with_balance,
    set_validator_fully_withdrawable,
    set_validator_partially_withdrawable,
)


def prepare_expected_withdrawals(spec, state,
                                 num_full_withdrawals=0, num_partial_withdrawals=0, rng=random.Random(5566)):
    assert num_full_withdrawals + num_partial_withdrawals <= len(state.validators)
    all_validator_indices = list(range(len(state.validators)))
    sampled_indices = rng.sample(all_validator_indices, num_full_withdrawals + num_partial_withdrawals)
    fully_withdrawable_indices = rng.sample(sampled_indices, num_full_withdrawals)
    partial_withdrawals_indices = list(set(sampled_indices).difference(set(fully_withdrawable_indices)))

    for index in fully_withdrawable_indices:
        set_validator_fully_withdrawable(spec, state, index)
    for index in partial_withdrawals_indices:
        set_validator_partially_withdrawable(spec, state, index)

    return fully_withdrawable_indices, partial_withdrawals_indices


def verify_post_state(state, spec, expected_withdrawals,
                      fully_withdrawable_indices, partial_withdrawals_indices):
    expected_withdrawals_validator_indices = [withdrawal.validator_index for withdrawal in expected_withdrawals]
    assert state.next_withdrawal_index == expected_withdrawals[-1].index + 1
    assert state.latest_withdrawal_validator_index == expected_withdrawals_validator_indices[-1]
    for index in fully_withdrawable_indices:
        if index in expected_withdrawals_validator_indices:
            assert state.balances[index] == 0
        else:
            assert state.balances[index] > 0
    for index in partial_withdrawals_indices:
        if index in expected_withdrawals_validator_indices:
            assert state.balances[index] == spec.MAX_EFFECTIVE_BALANCE
        else:
            assert state.balances[index] > spec.MAX_EFFECTIVE_BALANCE


def run_withdrawals_processing(spec, state, execution_payload, num_expected_withdrawals=None, valid=True):
    """
    Run ``process_execution_payload``, yielding:
      - pre-state ('pre')
      - execution payload ('execution_payload')
      - post-state ('post').
    If ``valid == False``, run expecting ``AssertionError``
    """
    expected_withdrawals = spec.get_expected_withdrawals(state)
    assert len(expected_withdrawals) <= spec.MAX_WITHDRAWALS_PER_PAYLOAD
    if num_expected_withdrawals is not None:
        assert len(expected_withdrawals) == num_expected_withdrawals

    pre_state = state.copy()
    yield 'pre', state
    yield 'execution_payload', execution_payload

    if not valid:
        expect_assertion_error(lambda: spec.process_withdrawals(state, execution_payload))
        yield 'post', None
        return

    spec.process_withdrawals(state, execution_payload)

    yield 'post', state

    if len(expected_withdrawals) == 0:
        assert state == pre_state
    elif len(expected_withdrawals) < spec.MAX_WITHDRAWALS_PER_PAYLOAD:
        assert len(spec.get_expected_withdrawals(state)) == 0
    elif len(expected_withdrawals) > spec.MAX_WITHDRAWALS_PER_PAYLOAD:
        raise ValueError('len(expected_withdrawals) should not be greater than MAX_WITHDRAWALS_PER_PAYLOAD')

    return expected_withdrawals


@with_capella_and_later
@spec_state_test
def test_success_zero_expected_withdrawals(spec, state):
    assert len(spec.get_expected_withdrawals(state)) == 0

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)

    yield from run_withdrawals_processing(spec, state, execution_payload)


@with_capella_and_later
@spec_state_test
def test_success_one_full_withdrawal(spec, state):
    fully_withdrawable_indices, partial_withdrawals_indices = prepare_expected_withdrawals(
        spec, state, num_full_withdrawals=1)
    assert len(fully_withdrawable_indices) == 1
    assert len(partial_withdrawals_indices) == 0

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)

    expected_withdrawals = yield from run_withdrawals_processing(spec, state, execution_payload)

    verify_post_state(state, spec, expected_withdrawals, fully_withdrawable_indices, partial_withdrawals_indices)


@with_capella_and_later
@spec_state_test
def test_success_one_partial_withdrawal(spec, state):
    fully_withdrawable_indices, partial_withdrawals_indices = prepare_expected_withdrawals(
        spec, state, num_partial_withdrawals=1)
    assert len(fully_withdrawable_indices) == 0
    assert len(partial_withdrawals_indices) == 1
    for index in partial_withdrawals_indices:
        assert state.balances[index] != spec.MAX_EFFECTIVE_BALANCE

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)

    expected_withdrawals = yield from run_withdrawals_processing(spec, state, execution_payload)

    verify_post_state(state, spec, expected_withdrawals, fully_withdrawable_indices, partial_withdrawals_indices)


@with_capella_and_later
@spec_state_test
def test_success_max_per_slot(spec, state):
    num_full_withdrawals = spec.MAX_WITHDRAWALS_PER_PAYLOAD // 2
    num_partial_withdrawals = spec.MAX_WITHDRAWALS_PER_PAYLOAD - num_full_withdrawals
    fully_withdrawable_indices, partial_withdrawals_indices = prepare_expected_withdrawals(
        spec, state,
        num_full_withdrawals=num_full_withdrawals, num_partial_withdrawals=num_partial_withdrawals)

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)

    expected_withdrawals = yield from run_withdrawals_processing(spec, state, execution_payload)

    verify_post_state(state, spec, expected_withdrawals, fully_withdrawable_indices, partial_withdrawals_indices)


@with_capella_and_later
@spec_state_test
def test_success_all_fully_withdrawable(spec, state):
    fully_withdrawable_indices, partial_withdrawals_indices = prepare_expected_withdrawals(
        spec, state, num_full_withdrawals=len(state.validators))

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)

    expected_withdrawals = yield from run_withdrawals_processing(spec, state, execution_payload)

    verify_post_state(state, spec, expected_withdrawals, fully_withdrawable_indices, partial_withdrawals_indices)


@with_capella_and_later
@spec_state_test
def test_success_all_partially_withdrawable(spec, state):
    fully_withdrawable_indices, partial_withdrawals_indices = prepare_expected_withdrawals(
        spec, state, num_partial_withdrawals=len(state.validators))

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)

    expected_withdrawals = yield from run_withdrawals_processing(spec, state, execution_payload)

    verify_post_state(state, spec, expected_withdrawals, fully_withdrawable_indices, partial_withdrawals_indices)


#
# Failure cases in which the number of withdrawals in the execution_payload is incorrect
#

@with_capella_and_later
@spec_state_test
def test_fail_non_withdrawable_non_empty_withdrawals(spec, state):
    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)
    withdrawal = spec.Withdrawal(
        index=0,
        validator_index=0,
        address=b'\x30' * 20,
        amount=420,
    )
    execution_payload.withdrawals.append(withdrawal)

    yield from run_withdrawals_processing(spec, state, execution_payload, valid=False)


@with_capella_and_later
@spec_state_test
def test_fail_one_expected_full_withdrawal_and_none_in_withdrawals(spec, state):
    prepare_expected_withdrawals(spec, state, num_full_withdrawals=1)

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.withdrawals = []

    yield from run_withdrawals_processing(spec, state, execution_payload, valid=False)


@with_capella_and_later
@spec_state_test
def test_fail_one_expected_partial_withdrawal_and_none_in_withdrawals(spec, state):
    prepare_expected_withdrawals(spec, state, num_partial_withdrawals=1)

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.withdrawals = []

    yield from run_withdrawals_processing(spec, state, execution_payload, valid=False)


@with_capella_and_later
@spec_state_test
def test_fail_one_expected_full_withdrawal_and_duplicate_in_withdrawals(spec, state):
    prepare_expected_withdrawals(spec, state, num_full_withdrawals=2)

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.withdrawals.append(execution_payload.withdrawals[0].copy())

    yield from run_withdrawals_processing(spec, state, execution_payload, valid=False)


@with_capella_and_later
@spec_state_test
def test_fail_two_expected_partial_withdrawal_and_duplicate_in_withdrawals(spec, state):
    prepare_expected_withdrawals(spec, state, num_partial_withdrawals=2)

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.withdrawals.append(execution_payload.withdrawals[0].copy())

    yield from run_withdrawals_processing(spec, state, execution_payload, valid=False)


@with_capella_and_later
@spec_state_test
def test_fail_max_per_slot_full_withdrawals_and_one_less_in_withdrawals(spec, state):
    prepare_expected_withdrawals(spec, state, num_full_withdrawals=spec.MAX_WITHDRAWALS_PER_PAYLOAD)

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.withdrawals = execution_payload.withdrawals[:-1]

    yield from run_withdrawals_processing(spec, state, execution_payload, valid=False)


@with_capella_and_later
@spec_state_test
def test_fail_max_per_slot_partial_withdrawals_and_one_less_in_withdrawals(spec, state):
    prepare_expected_withdrawals(spec, state, num_partial_withdrawals=spec.MAX_WITHDRAWALS_PER_PAYLOAD)

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.withdrawals = execution_payload.withdrawals[:-1]

    yield from run_withdrawals_processing(spec, state, execution_payload, valid=False)


@with_capella_and_later
@spec_state_test
def test_fail_a_lot_fully_withdrawable_too_few_in_withdrawals(spec, state):
    prepare_expected_withdrawals(spec, state, num_full_withdrawals=spec.MAX_WITHDRAWALS_PER_PAYLOAD * 4)

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.withdrawals = execution_payload.withdrawals[:-1]

    yield from run_withdrawals_processing(spec, state, execution_payload, valid=False)


@with_capella_and_later
@spec_state_test
def test_fail_a_lot_partially_withdrawable_too_few_in_withdrawals(spec, state):
    prepare_expected_withdrawals(spec, state, num_partial_withdrawals=spec.MAX_WITHDRAWALS_PER_PAYLOAD * 4)

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.withdrawals = execution_payload.withdrawals[:-1]

    yield from run_withdrawals_processing(spec, state, execution_payload, valid=False)


@with_capella_and_later
@spec_state_test
def test_fail_a_lot_mixed_withdrawable_in_queue_too_few_in_withdrawals(spec, state):
    prepare_expected_withdrawals(spec, state, num_full_withdrawals=spec.MAX_WITHDRAWALS_PER_PAYLOAD * 4,
                                 num_partial_withdrawals=spec.MAX_WITHDRAWALS_PER_PAYLOAD * 4)

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.withdrawals = execution_payload.withdrawals[:-1]

    yield from run_withdrawals_processing(spec, state, execution_payload, valid=False)


#
# Failure cases in which the withdrawals in the execution_payload are incorrect
#

@with_capella_and_later
@spec_state_test
def test_fail_incorrect_withdrawal_index(spec, state):
    prepare_expected_withdrawals(spec, state, num_full_withdrawals=1)

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.withdrawals[0].index += 1

    yield from run_withdrawals_processing(spec, state, execution_payload, valid=False)


@with_capella_and_later
@spec_state_test
def test_fail_incorrect_address_full(spec, state):
    prepare_expected_withdrawals(spec, state, num_full_withdrawals=1)

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.withdrawals[0].address = b'\xff' * 20

    yield from run_withdrawals_processing(spec, state, execution_payload, valid=False)


@with_capella_and_later
@spec_state_test
def test_fail_incorrect_address_partial(spec, state):
    prepare_expected_withdrawals(spec, state, num_partial_withdrawals=1)

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.withdrawals[0].address = b'\xff' * 20

    yield from run_withdrawals_processing(spec, state, execution_payload, valid=False)


@with_capella_and_later
@spec_state_test
def test_fail_incorrect_amount_full(spec, state):
    prepare_expected_withdrawals(spec, state, num_full_withdrawals=1)

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.withdrawals[0].amount += 1

    yield from run_withdrawals_processing(spec, state, execution_payload, valid=False)


@with_capella_and_later
@spec_state_test
def test_fail_incorrect_amount_partial(spec, state):
    prepare_expected_withdrawals(spec, state, num_full_withdrawals=1)

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.withdrawals[0].amount += 1

    yield from run_withdrawals_processing(spec, state, execution_payload, valid=False)


@with_capella_and_later
@spec_state_test
def test_fail_one_of_many_incorrectly_full(spec, state):
    prepare_expected_withdrawals(spec, state, num_full_withdrawals=spec.MAX_WITHDRAWALS_PER_PAYLOAD * 4)

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)
    num_withdrawals = len(execution_payload.withdrawals)

    # Pick withdrawal in middle of list and mutate
    withdrawal = execution_payload.withdrawals[num_withdrawals // 2]
    withdrawal.index += 1
    withdrawal.address = b'\x99' * 20
    withdrawal.amount += 4000000

    yield from run_withdrawals_processing(spec, state, execution_payload, valid=False)


@with_capella_and_later
@spec_state_test
def test_fail_one_of_many_incorrectly_partial(spec, state):
    prepare_expected_withdrawals(spec, state, num_partial_withdrawals=spec.MAX_WITHDRAWALS_PER_PAYLOAD * 4)

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)
    num_withdrawals = len(execution_payload.withdrawals)

    # Pick withdrawal in middle of list and mutate
    withdrawal = execution_payload.withdrawals[num_withdrawals // 2]
    withdrawal.index += 1
    withdrawal.address = b'\x99' * 20
    withdrawal.amount += 4000000

    yield from run_withdrawals_processing(spec, state, execution_payload, valid=False)


@with_capella_and_later
@spec_state_test
def test_fail_many_incorrectly_full(spec, state):
    prepare_expected_withdrawals(spec, state, num_full_withdrawals=spec.MAX_WITHDRAWALS_PER_PAYLOAD * 4)

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)
    for i, withdrawal in enumerate(execution_payload.withdrawals):
        if i % 3 == 0:
            withdrawal.index += 1
        elif i % 3 == 1:
            withdrawal.address = i.to_bytes(20, 'big')
        else:
            withdrawal.amount += 1

    yield from run_withdrawals_processing(spec, state, execution_payload, valid=False)


@with_capella_and_later
@spec_state_test
def test_fail_many_incorrectly_partial(spec, state):
    prepare_expected_withdrawals(spec, state, num_partial_withdrawals=spec.MAX_WITHDRAWALS_PER_PAYLOAD * 4)

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)
    for i, withdrawal in enumerate(execution_payload.withdrawals):
        if i % 3 == 0:
            withdrawal.index += 1
        elif i % 3 == 1:
            withdrawal.address = i.to_bytes(20, 'big')
        else:
            withdrawal.amount += 1

    yield from run_withdrawals_processing(spec, state, execution_payload, valid=False)


#
# More full withdrawal cases
#

@with_capella_and_later
@spec_state_test
def test_withdrawable_epoch_but_0_balance(spec, state):
    current_epoch = spec.get_current_epoch(state)
    set_validator_fully_withdrawable(spec, state, 0, current_epoch)

    state.validators[0].effective_balance = 10000000000
    state.balances[0] = 0

    execution_payload = build_empty_execution_payload(spec, state)

    yield from run_withdrawals_processing(spec, state, execution_payload, num_expected_withdrawals=0)


@with_capella_and_later
@spec_state_test
def test_withdrawable_epoch_but_0_effective_balance_0_balance(spec, state):
    current_epoch = spec.get_current_epoch(state)
    set_validator_fully_withdrawable(spec, state, 0, current_epoch)

    state.validators[0].effective_balance = 0
    state.balances[0] = 0

    execution_payload = build_empty_execution_payload(spec, state)

    yield from run_withdrawals_processing(spec, state, execution_payload, num_expected_withdrawals=0)


@with_capella_and_later
@spec_state_test
def test_withdrawable_epoch_but_0_effective_balance_nonzero_balance(spec, state):
    current_epoch = spec.get_current_epoch(state)
    set_validator_fully_withdrawable(spec, state, 0, current_epoch)

    state.validators[0].effective_balance = 0
    state.balances[0] = 100000000

    execution_payload = build_empty_execution_payload(spec, state)

    yield from run_withdrawals_processing(spec, state, execution_payload, num_expected_withdrawals=1)


@with_capella_and_later
@spec_state_test
def test_no_withdrawals_but_some_next_epoch(spec, state):
    current_epoch = spec.get_current_epoch(state)

    # Make a few validators withdrawable at the *next* epoch
    for index in range(3):
        set_validator_fully_withdrawable(spec, state, index, current_epoch + 1)

    execution_payload = build_empty_execution_payload(spec, state)

    yield from run_withdrawals_processing(spec, state, execution_payload, num_expected_withdrawals=0)


@with_capella_and_later
@spec_state_test
def test_all_withdrawal(spec, state):
    # Make all validators withdrawable
    for index in range(len(state.validators)):
        set_validator_fully_withdrawable(spec, state, index)

    execution_payload = build_empty_execution_payload(spec, state)

    yield from run_withdrawals_processing(
        spec, state, execution_payload,
        num_expected_withdrawals=spec.MAX_WITHDRAWALS_PER_PAYLOAD)


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

    execution_payload = build_empty_execution_payload(spec, state)

    yield from run_withdrawals_processing(spec, state, execution_payload)


@with_capella_and_later
@spec_state_test
def test_random_full_withdrawals_0(spec, state):
    yield from run_random_full_withdrawals_test(spec, state, random.Random(444))


@with_capella_and_later
@spec_state_test
def test_random_full_withdrawals_1(spec, state):
    yield from run_random_full_withdrawals_test(spec, state, random.Random(420))


@with_capella_and_later
@spec_state_test
def test_random_full_withdrawals_2(spec, state):
    yield from run_random_full_withdrawals_test(spec, state, random.Random(200))


@with_capella_and_later
@spec_state_test
def test_random_full_withdrawals_3(spec, state):
    yield from run_random_full_withdrawals_test(spec, state, random.Random(2000000))


#
# More partial withdrawal cases
#

@with_capella_and_later
@spec_state_test
def test_success_no_max_effective_balance(spec, state):
    validator_index = len(state.validators) // 2
    # To be partially withdrawable, the validator's effective balance must be maxed out
    set_eth1_withdrawal_credential_with_balance(spec, state, validator_index, spec.MAX_EFFECTIVE_BALANCE - 1)
    validator = state.validators[validator_index]

    assert validator.effective_balance < spec.MAX_EFFECTIVE_BALANCE
    assert not spec.is_partially_withdrawable_validator(validator, state.balances[validator_index])

    execution_payload = build_empty_execution_payload(spec, state)

    yield from run_withdrawals_processing(spec, state, execution_payload, num_expected_withdrawals=0)


@with_capella_and_later
@spec_state_test
def test_success_no_excess_balance(spec, state):
    validator_index = len(state.validators) // 2
    # To be partially withdrawable, the validator needs an excess balance
    set_eth1_withdrawal_credential_with_balance(spec, state, validator_index, spec.MAX_EFFECTIVE_BALANCE)
    validator = state.validators[validator_index]

    assert validator.effective_balance == spec.MAX_EFFECTIVE_BALANCE
    assert not spec.is_partially_withdrawable_validator(validator, state.balances[validator_index])

    execution_payload = build_empty_execution_payload(spec, state)

    yield from run_withdrawals_processing(spec, state, execution_payload, num_expected_withdrawals=0)


@with_capella_and_later
@spec_state_test
def test_success_excess_balance_but_no_max_effective_balance(spec, state):
    validator_index = len(state.validators) // 2
    set_validator_partially_withdrawable(spec, state, validator_index)
    validator = state.validators[validator_index]

    # To be partially withdrawable, the validator needs both a maxed out effective balance and an excess balance
    validator.effective_balance = spec.MAX_EFFECTIVE_BALANCE - 1

    assert not spec.is_partially_withdrawable_validator(validator, state.balances[validator_index])

    execution_payload = build_empty_execution_payload(spec, state)

    yield from run_withdrawals_processing(spec, state, execution_payload, num_expected_withdrawals=0)


@with_capella_and_later
@spec_state_test
def test_success_one_partial_withdrawable_not_yet_active(spec, state):
    validator_index = len(state.validators) // 2
    state.validators[validator_index].activation_epoch += 4
    set_validator_partially_withdrawable(spec, state, validator_index)

    assert not spec.is_active_validator(state.validators[validator_index], spec.get_current_epoch(state))

    execution_payload = build_empty_execution_payload(spec, state)

    yield from run_withdrawals_processing(spec, state, execution_payload, num_expected_withdrawals=1)


@with_capella_and_later
@spec_state_test
def test_success_one_partial_withdrawable_in_exit_queue(spec, state):
    validator_index = len(state.validators) // 2
    state.validators[validator_index].exit_epoch = spec.get_current_epoch(state) + 1
    set_validator_partially_withdrawable(spec, state, validator_index)

    assert spec.is_active_validator(state.validators[validator_index], spec.get_current_epoch(state))
    assert not spec.is_active_validator(state.validators[validator_index], spec.get_current_epoch(state) + 1)

    execution_payload = build_empty_execution_payload(spec, state)

    yield from run_withdrawals_processing(spec, state, execution_payload, num_expected_withdrawals=1)


@with_capella_and_later
@spec_state_test
def test_success_one_partial_withdrawable_exited(spec, state):
    validator_index = len(state.validators) // 2
    state.validators[validator_index].exit_epoch = spec.get_current_epoch(state)
    set_validator_partially_withdrawable(spec, state, validator_index)

    assert not spec.is_active_validator(state.validators[validator_index], spec.get_current_epoch(state))

    execution_payload = build_empty_execution_payload(spec, state)

    yield from run_withdrawals_processing(spec, state, execution_payload, num_expected_withdrawals=1)


@with_capella_and_later
@spec_state_test
def test_success_one_partial_withdrawable_active_and_slashed(spec, state):
    validator_index = len(state.validators) // 2
    state.validators[validator_index].slashed = True
    set_validator_partially_withdrawable(spec, state, validator_index)

    assert spec.is_active_validator(state.validators[validator_index], spec.get_current_epoch(state))

    execution_payload = build_empty_execution_payload(spec, state)

    yield from run_withdrawals_processing(spec, state, execution_payload, num_expected_withdrawals=1)


@with_capella_and_later
@spec_state_test
def test_success_one_partial_withdrawable_exited_and_slashed(spec, state):
    validator_index = len(state.validators) // 2
    state.validators[validator_index].slashed = True
    state.validators[validator_index].exit_epoch = spec.get_current_epoch(state)
    set_validator_partially_withdrawable(spec, state, validator_index)

    assert not spec.is_active_validator(state.validators[validator_index], spec.get_current_epoch(state))

    execution_payload = build_empty_execution_payload(spec, state)

    yield from run_withdrawals_processing(spec, state, execution_payload, num_expected_withdrawals=1)


@with_capella_and_later
@spec_state_test
def test_success_two_partial_withdrawable(spec, state):
    set_validator_partially_withdrawable(spec, state, 0)
    set_validator_partially_withdrawable(spec, state, 1)

    execution_payload = build_empty_execution_payload(spec, state)

    yield from run_withdrawals_processing(spec, state, execution_payload, num_expected_withdrawals=2)


@with_capella_and_later
@spec_state_test
def test_success_max_partial_withdrawable(spec, state):
    # Sanity check that this test works for this state
    assert len(state.validators) >= spec.MAX_WITHDRAWALS_PER_PAYLOAD

    for i in range(spec.MAX_WITHDRAWALS_PER_PAYLOAD):
        set_validator_partially_withdrawable(spec, state, i)

    execution_payload = build_empty_execution_payload(spec, state)

    yield from run_withdrawals_processing(
        spec, state, execution_payload, num_expected_withdrawals=spec.MAX_WITHDRAWALS_PER_PAYLOAD)


@with_capella_and_later
@with_presets([MINIMAL], reason="not enough validators with mainnet config")
@spec_state_test
def test_success_max_plus_one_withdrawable(spec, state):
    # Sanity check that this test works for this state
    assert len(state.validators) >= spec.MAX_WITHDRAWALS_PER_PAYLOAD + 1

    # More than MAX_WITHDRAWALS_PER_PAYLOAD partially withdrawable
    for i in range(spec.MAX_WITHDRAWALS_PER_PAYLOAD + 1):
        set_validator_partially_withdrawable(spec, state, i)

    execution_payload = build_empty_execution_payload(spec, state)

    # Should only have MAX_WITHDRAWALS_PER_PAYLOAD withdrawals created
    yield from run_withdrawals_processing(
        spec, state, execution_payload, num_expected_withdrawals=spec.MAX_WITHDRAWALS_PER_PAYLOAD)


def run_random_partial_withdrawals_test(spec, state, rng):
    for _ in range(rng.randint(0, 2)):
        next_epoch(spec, state)
    randomize_state(spec, state, rng)

    num_validators = len(state.validators)
    state.latest_withdrawal_validator_index = rng.randint(0, num_validators - 1)

    num_partially_withdrawable = rng.randint(0, num_validators - 1)
    partially_withdrawable_indices = rng.sample(range(num_validators), num_partially_withdrawable)
    for index in partially_withdrawable_indices:
        set_validator_partially_withdrawable(spec, state, index, excess_balance=rng.randint(1, 1000000000))

    execution_payload = build_empty_execution_payload(spec, state)

    # Note: due to the randomness and other epoch processing, some of these set as "partially withdrawable"
    # may not be partially withdrawable once we get to ``process_partial_withdrawals``,
    # thus *not* using the optional third param in this call
    yield from run_withdrawals_processing(spec, state, execution_payload)


@with_capella_and_later
@spec_state_test
def test_random_0(spec, state):
    yield from run_random_partial_withdrawals_test(spec, state, random.Random(0))


@with_capella_and_later
@spec_state_test
def test_random_partial_withdrawals_1(spec, state):
    yield from run_random_partial_withdrawals_test(spec, state, random.Random(1))


@with_capella_and_later
@spec_state_test
def test_random_partial_withdrawals_2(spec, state):
    yield from run_random_partial_withdrawals_test(spec, state, random.Random(2))


@with_capella_and_later
@spec_state_test
def test_random_partial_withdrawals_3(spec, state):
    yield from run_random_partial_withdrawals_test(spec, state, random.Random(3))


@with_capella_and_later
@spec_state_test
def test_random_partial_withdrawals_4(spec, state):
    yield from run_random_partial_withdrawals_test(spec, state, random.Random(4))


@with_capella_and_later
@spec_state_test
def test_random_partial_withdrawals_5(spec, state):
    yield from run_random_partial_withdrawals_test(spec, state, random.Random(5))


# Tests with multiple blocks
@with_capella_and_later
@spec_state_test
def test_success_two_payloads(spec, state):
    fully_withdrawable_indices, partial_withdrawals_indices = prepare_expected_withdrawals(
        spec, state, num_partial_withdrawals=spec.MAX_WITHDRAWALS_PER_PAYLOAD * 4,
        num_full_withdrawals=spec.MAX_WITHDRAWALS_PER_PAYLOAD * 4)

    next_slot(spec, state)
    next_withdrawal_index = state.next_withdrawal_index
    execution_payload = build_empty_execution_payload(spec, state)
    expected_withdrawals = yield from run_withdrawals_processing(spec, state, execution_payload)
    verify_post_state(state, spec, expected_withdrawals, fully_withdrawable_indices, partial_withdrawals_indices)
    withdrawn_indices = [withdrawal.validator_index for withdrawal in expected_withdrawals]
    fully_withdrawable_indices = list(set(fully_withdrawable_indices).difference(set(withdrawn_indices)))
    partial_withdrawals_indices = list(set(partial_withdrawals_indices).difference(set(withdrawn_indices)))
    assert state.next_withdrawal_index == next_withdrawal_index + spec.MAX_WITHDRAWALS_PER_PAYLOAD

    execution_payload = build_empty_execution_payload(spec, state)
    expected_withdrawals = yield from run_withdrawals_processing(spec, state, execution_payload)
    verify_post_state(state, spec, expected_withdrawals, fully_withdrawable_indices, partial_withdrawals_indices)
    assert state.next_withdrawal_index == next_withdrawal_index + spec.MAX_WITHDRAWALS_PER_PAYLOAD * 2


@with_capella_and_later
@spec_state_test
def test_fail_second_payload_isnt_compatible(spec, state):
    fully_withdrawable_indices, partial_withdrawals_indices = prepare_expected_withdrawals(
        spec, state, num_partial_withdrawals=spec.MAX_WITHDRAWALS_PER_PAYLOAD * 4,
        num_full_withdrawals=spec.MAX_WITHDRAWALS_PER_PAYLOAD * 4)

    next_slot(spec, state)
    next_withdrawal_index = state.next_withdrawal_index
    execution_payload = build_empty_execution_payload(spec, state)
    expected_withdrawals = yield from run_withdrawals_processing(spec, state, execution_payload)
    verify_post_state(state, spec, expected_withdrawals, fully_withdrawable_indices, partial_withdrawals_indices)
    withdrawn_indices = [withdrawal.validator_index for withdrawal in expected_withdrawals]
    fully_withdrawable_indices = list(set(fully_withdrawable_indices).difference(set(withdrawn_indices)))
    partial_withdrawals_indices = list(set(partial_withdrawals_indices).difference(set(withdrawn_indices)))
    assert state.next_withdrawal_index == next_withdrawal_index + spec.MAX_WITHDRAWALS_PER_PAYLOAD

    execution_payload = build_empty_execution_payload(spec, state)
    state.next_withdrawal_index += 1
    yield from run_withdrawals_processing(spec, state, execution_payload, valid=False)
