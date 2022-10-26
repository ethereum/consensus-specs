from eth2spec.test.helpers.constants import CAPELLA
from eth2spec.test.helpers.execution_payload import (
    build_empty_execution_payload,
)

from eth2spec.test.context import spec_state_test, expect_assertion_error, with_phases

from eth2spec.test.helpers.state import next_slot


def prepare_withdrawal_queue(spec, state, num_withdrawals):
    pre_queue_len = len(state.withdrawal_queue)

    for i in range(num_withdrawals):
        withdrawal = spec.Withdrawal(
            index=i + 5,
            address=b'\x42' * 20,
            amount=200000 + i,
        )
        state.withdrawal_queue.append(withdrawal)

    assert len(state.withdrawal_queue) == num_withdrawals + pre_queue_len


def run_withdrawals_processing(spec, state, execution_payload, valid=True):
    """
    Run ``process_execution_payload``, yielding:
      - pre-state ('pre')
      - execution payload ('execution_payload')
      - post-state ('post').
    If ``valid == False``, run expecting ``AssertionError``
    """

    pre_withdrawal_queue = state.withdrawal_queue.copy()
    num_withdrawals = min(spec.MAX_WITHDRAWALS_PER_PAYLOAD, len(pre_withdrawal_queue))

    yield 'pre', state
    yield 'execution_payload', execution_payload

    if not valid:
        expect_assertion_error(lambda: spec.process_withdrawals(state, execution_payload))
        yield 'post', None
        return

    spec.process_withdrawals(state, execution_payload)

    yield 'post', state

    if len(pre_withdrawal_queue) == 0:
        assert len(state.withdrawal_queue) == 0
    elif len(pre_withdrawal_queue) <= num_withdrawals:
        assert len(state.withdrawal_queue) == 0
    else:
        assert state.withdrawal_queue == pre_withdrawal_queue[num_withdrawals:]


@with_phases([CAPELLA])
@spec_state_test
def test_success_empty_queue(spec, state):
    assert len(state.withdrawal_queue) == 0

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)

    yield from run_withdrawals_processing(spec, state, execution_payload)


@with_phases([CAPELLA])
@spec_state_test
def test_success_one_in_queue(spec, state):
    prepare_withdrawal_queue(spec, state, 1)

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)

    yield from run_withdrawals_processing(spec, state, execution_payload)


@with_phases([CAPELLA])
@spec_state_test
def test_success_max_per_slot_in_queue(spec, state):
    prepare_withdrawal_queue(spec, state, spec.MAX_WITHDRAWALS_PER_PAYLOAD)

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)

    yield from run_withdrawals_processing(spec, state, execution_payload)


@with_phases([CAPELLA])
@spec_state_test
def test_success_a_lot_in_queue(spec, state):
    prepare_withdrawal_queue(spec, state, spec.MAX_WITHDRAWALS_PER_PAYLOAD * 4)

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)

    yield from run_withdrawals_processing(spec, state, execution_payload)


#
# Failure cases in which the number of withdrawals in the execution_payload is incorrect
#

@with_phases([CAPELLA])
@spec_state_test
def test_fail_empty_queue_non_empty_withdrawals(spec, state):
    assert len(state.withdrawal_queue) == 0

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)
    withdrawal = spec.Withdrawal(
        index=0,
        address=b'\x30' * 20,
        amount=420,
    )
    execution_payload.withdrawals.append(withdrawal)

    yield from run_withdrawals_processing(spec, state, execution_payload, valid=False)


@with_phases([CAPELLA])
@spec_state_test
def test_fail_one_in_queue_none_in_withdrawals(spec, state):
    prepare_withdrawal_queue(spec, state, 1)

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.withdrawals = []

    yield from run_withdrawals_processing(spec, state, execution_payload, valid=False)


@with_phases([CAPELLA])
@spec_state_test
def test_fail_one_in_queue_two_in_withdrawals(spec, state):
    prepare_withdrawal_queue(spec, state, 1)

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.withdrawals.append(execution_payload.withdrawals[0].copy())

    yield from run_withdrawals_processing(spec, state, execution_payload, valid=False)


@with_phases([CAPELLA])
@spec_state_test
def test_fail_max_per_slot_in_queue_one_less_in_withdrawals(spec, state):
    prepare_withdrawal_queue(spec, state, spec.MAX_WITHDRAWALS_PER_PAYLOAD)

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.withdrawals = execution_payload.withdrawals[:-1]

    yield from run_withdrawals_processing(spec, state, execution_payload, valid=False)


@with_phases([CAPELLA])
@spec_state_test
def test_fail_a_lot_in_queue_too_few_in_withdrawals(spec, state):
    prepare_withdrawal_queue(spec, state, spec.MAX_WITHDRAWALS_PER_PAYLOAD * 4)

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.withdrawals = execution_payload.withdrawals[:-1]

    yield from run_withdrawals_processing(spec, state, execution_payload, valid=False)


#
# Failure cases in which the withdrawals in the execution_payload are incorrect
#

@with_phases([CAPELLA])
@spec_state_test
def test_fail_incorrect_dequeue_index(spec, state):
    prepare_withdrawal_queue(spec, state, 1)

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.withdrawals[0].index += 1

    yield from run_withdrawals_processing(spec, state, execution_payload, valid=False)


@with_phases([CAPELLA])
@spec_state_test
def test_fail_incorrect_dequeue_address(spec, state):
    prepare_withdrawal_queue(spec, state, 1)

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.withdrawals[0].address = b'\xff' * 20

    yield from run_withdrawals_processing(spec, state, execution_payload, valid=False)


@with_phases([CAPELLA])
@spec_state_test
def test_fail_incorrect_dequeue_amount(spec, state):
    prepare_withdrawal_queue(spec, state, 1)

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.withdrawals[0].amount += 1

    yield from run_withdrawals_processing(spec, state, execution_payload, valid=False)


@with_phases([CAPELLA])
@spec_state_test
def test_fail_one_of_many_dequeued_incorrectly(spec, state):
    prepare_withdrawal_queue(spec, state, spec.MAX_WITHDRAWALS_PER_PAYLOAD * 4)

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)
    num_withdrawals = len(execution_payload.withdrawals)

    # Pick withdrawal in middle of list and mutate
    withdrawal = execution_payload.withdrawals[num_withdrawals // 2]
    withdrawal.index += 1
    withdrawal.address = b'\x99' * 20
    withdrawal.amount += 4000000

    yield from run_withdrawals_processing(spec, state, execution_payload, valid=False)


@with_phases([CAPELLA])
@spec_state_test
def test_fail_many_dequeued_incorrectly(spec, state):
    prepare_withdrawal_queue(spec, state, spec.MAX_WITHDRAWALS_PER_PAYLOAD * 4)

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
