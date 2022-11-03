import random
from eth2spec.test.helpers.execution_payload import (
    build_empty_execution_payload,
)

from eth2spec.test.context import spec_state_test, expect_assertion_error, with_capella_and_later
from eth2spec.test.helpers.state import next_slot
from eth2spec.test.helpers.withdrawals import (
    set_validator_fully_withdrawable,
    set_validator_partially_withdrawable,
)


def prepare_withdrawal_queue(spec, state, num_withdrawals):
    pre_queue_len = len(state.withdrawal_queue)
    validator_len = len(state.validators)
    for i in range(num_withdrawals):
        withdrawal = spec.Withdrawal(
            index=i + 5,
            validator_index=(i + 1000) % validator_len,
            address=b'\x42' * 20,
            amount=200000 + i,
        )
        state.withdrawal_queue.append(withdrawal)

    assert len(state.withdrawal_queue) == num_withdrawals + pre_queue_len


def prepare_expected_withdrawals(spec, state,
                                 num_full_withdrawals=0, num_partial_withdrawals=0, rng=random.Random(5566)):
    assert num_full_withdrawals + num_partial_withdrawals <= len(state.validators)
    all_valdiator_indices = list(range(len(state.validators)))
    sampled_indices = rng.sample(all_valdiator_indices, num_full_withdrawals + num_partial_withdrawals)
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


def run_withdrawals_processing(spec, state, execution_payload, valid=True):
    """
    Run ``process_execution_payload``, yielding:
      - pre-state ('pre')
      - execution payload ('execution_payload')
      - post-state ('post').
    If ``valid == False``, run expecting ``AssertionError``
    """
    expected_withdrawals = spec.get_expected_withdrawals(state)
    assert len(expected_withdrawals) <= spec.MAX_WITHDRAWALS_PER_PAYLOAD

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
    elif len(expected_withdrawals) == spec.MAX_WITHDRAWALS_PER_PAYLOAD:
        assert len(spec.get_expected_withdrawals(state)) >= 0
    else:
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
def test_success_max_per_slot_in_queue(spec, state):
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
def test_success_a_lot_full_withdrawal_in_queue(spec, state):
    fully_withdrawable_indices, partial_withdrawals_indices = prepare_expected_withdrawals(
        spec, state, num_full_withdrawals=spec.MAX_WITHDRAWALS_PER_PAYLOAD * 4)

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)

    expected_withdrawals = yield from run_withdrawals_processing(spec, state, execution_payload)

    verify_post_state(state, spec, expected_withdrawals, fully_withdrawable_indices, partial_withdrawals_indices)


@with_capella_and_later
@spec_state_test
def test_success_a_lot_partial_withdrawal_in_queue(spec, state):
    fully_withdrawable_indices, partial_withdrawals_indices = prepare_expected_withdrawals(
        spec, state, num_partial_withdrawals=spec.MAX_WITHDRAWALS_PER_PAYLOAD * 4)

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)

    expected_withdrawals = yield from run_withdrawals_processing(spec, state, execution_payload)

    verify_post_state(state, spec, expected_withdrawals, fully_withdrawable_indices, partial_withdrawals_indices)


#
# Failure cases in which the number of withdrawals in the execution_payload is incorrect
#

@with_capella_and_later
@spec_state_test
def test_fail_empty_queue_non_empty_withdrawals(spec, state):
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
def test_fail_one_expected_partial_withdrawal_and_duplicate_in_withdrawals(spec, state):
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
def test_fail_a_lot_full_withdrawals_in_queue_too_few_in_withdrawals(spec, state):
    prepare_expected_withdrawals(spec, state, num_full_withdrawals=spec.MAX_WITHDRAWALS_PER_PAYLOAD * 4)

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.withdrawals = execution_payload.withdrawals[:-1]

    yield from run_withdrawals_processing(spec, state, execution_payload, valid=False)


@with_capella_and_later
@spec_state_test
def test_fail_a_lot_partial_withdrawals_in_queue_too_few_in_withdrawals(spec, state):
    prepare_expected_withdrawals(spec, state, num_partial_withdrawals=spec.MAX_WITHDRAWALS_PER_PAYLOAD * 4)

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.withdrawals = execution_payload.withdrawals[:-1]

    yield from run_withdrawals_processing(spec, state, execution_payload, valid=False)


#
# Failure cases in which the withdrawals in the execution_payload are incorrect
#

@with_capella_and_later
@spec_state_test
def test_fail_incorrect_dequeue_index(spec, state):
    prepare_expected_withdrawals(spec, state, num_full_withdrawals=1)

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.withdrawals[0].index += 1

    yield from run_withdrawals_processing(spec, state, execution_payload, valid=False)


@with_capella_and_later
@spec_state_test
def test_fail_incorrect_dequeue_address_full(spec, state):
    prepare_expected_withdrawals(spec, state, num_full_withdrawals=1)

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.withdrawals[0].address = b'\xff' * 20

    yield from run_withdrawals_processing(spec, state, execution_payload, valid=False)


@with_capella_and_later
@spec_state_test
def test_fail_incorrect_dequeue_address_partial(spec, state):
    prepare_expected_withdrawals(spec, state, num_partial_withdrawals=1)

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.withdrawals[0].address = b'\xff' * 20

    yield from run_withdrawals_processing(spec, state, execution_payload, valid=False)


@with_capella_and_later
@spec_state_test
def test_fail_incorrect_dequeue_amount_full(spec, state):
    prepare_expected_withdrawals(spec, state, num_full_withdrawals=1)

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.withdrawals[0].amount += 1

    yield from run_withdrawals_processing(spec, state, execution_payload, valid=False)


@with_capella_and_later
@spec_state_test
def test_fail_incorrect_dequeue_amount_partial(spec, state):
    prepare_expected_withdrawals(spec, state, num_full_withdrawals=1)

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.withdrawals[0].amount += 1

    yield from run_withdrawals_processing(spec, state, execution_payload, valid=False)


@with_capella_and_later
@spec_state_test
def test_fail_one_of_many_dequeued_incorrectly_full(spec, state):
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
def test_fail_one_of_many_dequeued_incorrectly_partial(spec, state):
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
def test_fail_many_dequeued_incorrectly_full(spec, state):
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
def test_fail_many_dequeued_incorrectly_partial(spec, state):
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
