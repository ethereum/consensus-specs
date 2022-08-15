from random import Random

from eth2spec.test.helpers.execution_payload import (
    build_empty_execution_payload,
    build_randomized_execution_payload,
    get_execution_payload_header,
    build_state_with_incomplete_transition,
    build_state_with_complete_transition,
)
from eth2spec.test.context import spec_state_test, expect_assertion_error, with_bellatrix_and_later
from eth2spec.test.helpers.state import next_slot


def run_execution_payload_processing(spec, state, execution_payload, valid=True, execution_valid=True):
    """
    Run ``process_execution_payload``, yielding:
      - pre-state ('pre')
      - execution payload ('execution_payload')
      - execution details, to mock EVM execution ('execution.yml', a dict with 'execution_valid' key and boolean value)
      - post-state ('post').
    If ``valid == False``, run expecting ``AssertionError``
    """

    yield 'pre', state
    yield 'execution', {'execution_valid': execution_valid}
    yield 'execution_payload', execution_payload

    called_new_block = False

    class TestEngine(spec.NoopExecutionEngine):
        def notify_new_payload(self, payload) -> bool:
            nonlocal called_new_block, execution_valid
            called_new_block = True
            assert payload == execution_payload
            return execution_valid

    if not valid:
        expect_assertion_error(lambda: spec.process_execution_payload(state, execution_payload, TestEngine()))
        yield 'post', None
        return

    spec.process_execution_payload(state, execution_payload, TestEngine())

    # Make sure we called the engine
    assert called_new_block

    yield 'post', state

    assert state.latest_execution_payload_header == get_execution_payload_header(spec, execution_payload)


def run_success_test(spec, state):
    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)

    yield from run_execution_payload_processing(spec, state, execution_payload)


@with_bellatrix_and_later
@spec_state_test
def test_success_first_payload(spec, state):
    state = build_state_with_incomplete_transition(spec, state)

    yield from run_success_test(spec, state)


@with_bellatrix_and_later
@spec_state_test
def test_success_regular_payload(spec, state):
    state = build_state_with_complete_transition(spec, state)

    yield from run_success_test(spec, state)


def run_gap_slot_test(spec, state):
    next_slot(spec, state)
    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)

    yield from run_execution_payload_processing(spec, state, execution_payload)


@with_bellatrix_and_later
@spec_state_test
def test_success_first_payload_with_gap_slot(spec, state):
    state = build_state_with_incomplete_transition(spec, state)
    yield from run_gap_slot_test(spec, state)


@with_bellatrix_and_later
@spec_state_test
def test_success_regular_payload_with_gap_slot(spec, state):
    state = build_state_with_complete_transition(spec, state)
    yield from run_gap_slot_test(spec, state)


def run_bad_execution_test(spec, state):
    # completely valid payload, but execution itself fails (e.g. block exceeds gas limit)
    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)

    yield from run_execution_payload_processing(spec, state, execution_payload, valid=False, execution_valid=False)


@with_bellatrix_and_later
@spec_state_test
def test_bad_execution_first_payload(spec, state):
    state = build_state_with_incomplete_transition(spec, state)
    yield from run_bad_execution_test(spec, state)


@with_bellatrix_and_later
@spec_state_test
def test_bad_execution_regular_payload(spec, state):
    state = build_state_with_complete_transition(spec, state)
    yield from run_bad_execution_test(spec, state)


@with_bellatrix_and_later
@spec_state_test
def test_bad_parent_hash_first_payload(spec, state):
    state = build_state_with_incomplete_transition(spec, state)
    next_slot(spec, state)

    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.parent_hash = b'\x55' * 32

    yield from run_execution_payload_processing(spec, state, execution_payload, valid=True)


@with_bellatrix_and_later
@spec_state_test
def test_bad_parent_hash_regular_payload(spec, state):
    state = build_state_with_complete_transition(spec, state)
    next_slot(spec, state)

    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.parent_hash = spec.Hash32()

    yield from run_execution_payload_processing(spec, state, execution_payload, valid=False)


def run_bad_prev_randao_test(spec, state):
    next_slot(spec, state)

    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.prev_randao = b'\x42' * 32

    yield from run_execution_payload_processing(spec, state, execution_payload, valid=False)


@with_bellatrix_and_later
@spec_state_test
def test_bad_prev_randao_first_payload(spec, state):
    state = build_state_with_incomplete_transition(spec, state)
    yield from run_bad_prev_randao_test(spec, state)


@with_bellatrix_and_later
@spec_state_test
def test_bad_pre_randao_regular_payload(spec, state):
    state = build_state_with_complete_transition(spec, state)
    yield from run_bad_prev_randao_test(spec, state)


def run_bad_everything_test(spec, state):
    next_slot(spec, state)

    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.parent_hash = spec.Hash32()
    execution_payload.prev_randao = spec.Bytes32()
    execution_payload.timestamp = 0

    yield from run_execution_payload_processing(spec, state, execution_payload, valid=False)


@with_bellatrix_and_later
@spec_state_test
def test_bad_everything_first_payload(spec, state):
    state = build_state_with_incomplete_transition(spec, state)
    yield from run_bad_everything_test(spec, state)


@with_bellatrix_and_later
@spec_state_test
def test_bad_everything_regular_payload(spec, state):
    state = build_state_with_complete_transition(spec, state)
    yield from run_bad_everything_test(spec, state)


def run_bad_timestamp_test(spec, state, is_future):
    next_slot(spec, state)

    # execution payload
    execution_payload = build_empty_execution_payload(spec, state)
    if is_future:
        timestamp = execution_payload.timestamp + 1
    else:
        timestamp = execution_payload.timestamp - 1
    execution_payload.timestamp = timestamp

    yield from run_execution_payload_processing(spec, state, execution_payload, valid=False)


@with_bellatrix_and_later
@spec_state_test
def test_future_timestamp_first_payload(spec, state):
    state = build_state_with_incomplete_transition(spec, state)
    yield from run_bad_timestamp_test(spec, state, is_future=True)


@with_bellatrix_and_later
@spec_state_test
def test_future_timestamp_regular_payload(spec, state):
    state = build_state_with_complete_transition(spec, state)
    yield from run_bad_timestamp_test(spec, state, is_future=True)


@with_bellatrix_and_later
@spec_state_test
def test_past_timestamp_first_payload(spec, state):
    state = build_state_with_incomplete_transition(spec, state)
    yield from run_bad_timestamp_test(spec, state, is_future=False)


@with_bellatrix_and_later
@spec_state_test
def test_past_timestamp_regular_payload(spec, state):
    state = build_state_with_complete_transition(spec, state)
    yield from run_bad_timestamp_test(spec, state, is_future=False)


def run_non_empty_extra_data_test(spec, state):
    next_slot(spec, state)

    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.extra_data = b'\x45' * 12

    yield from run_execution_payload_processing(spec, state, execution_payload)
    assert state.latest_execution_payload_header.extra_data == execution_payload.extra_data


@with_bellatrix_and_later
@spec_state_test
def test_non_empty_extra_data_first_payload(spec, state):
    state = build_state_with_incomplete_transition(spec, state)
    yield from run_non_empty_extra_data_test(spec, state)


@with_bellatrix_and_later
@spec_state_test
def test_non_empty_extra_data_regular_payload(spec, state):
    state = build_state_with_complete_transition(spec, state)
    yield from run_non_empty_extra_data_test(spec, state)


def run_non_empty_transactions_test(spec, state):
    next_slot(spec, state)

    execution_payload = build_empty_execution_payload(spec, state)
    num_transactions = 2
    execution_payload.transactions = [
        spec.Transaction(b'\x99' * 128)
        for _ in range(num_transactions)
    ]

    yield from run_execution_payload_processing(spec, state, execution_payload)
    assert state.latest_execution_payload_header.transactions_root == execution_payload.transactions.hash_tree_root()


@with_bellatrix_and_later
@spec_state_test
def test_non_empty_transactions_first_payload(spec, state):
    state = build_state_with_incomplete_transition(spec, state)
    yield from run_non_empty_extra_data_test(spec, state)


@with_bellatrix_and_later
@spec_state_test
def test_non_empty_transactions_regular_payload(spec, state):
    state = build_state_with_complete_transition(spec, state)
    yield from run_non_empty_extra_data_test(spec, state)


def run_zero_length_transaction_test(spec, state):
    next_slot(spec, state)

    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.transactions = [spec.Transaction(b'')]
    assert len(execution_payload.transactions[0]) == 0

    yield from run_execution_payload_processing(spec, state, execution_payload)
    assert state.latest_execution_payload_header.transactions_root == execution_payload.transactions.hash_tree_root()


@with_bellatrix_and_later
@spec_state_test
def test_zero_length_transaction_first_payload(spec, state):
    state = build_state_with_incomplete_transition(spec, state)
    yield from run_zero_length_transaction_test(spec, state)


@with_bellatrix_and_later
@spec_state_test
def test_zero_length_transaction_regular_payload(spec, state):
    state = build_state_with_complete_transition(spec, state)
    yield from run_zero_length_transaction_test(spec, state)


def run_randomized_non_validated_execution_fields_test(spec, state, execution_valid=True, rng=Random(5555)):
    next_slot(spec, state)
    execution_payload = build_randomized_execution_payload(spec, state, rng)

    yield from run_execution_payload_processing(
        spec, state,
        execution_payload,
        valid=execution_valid, execution_valid=execution_valid
    )


@with_bellatrix_and_later
@spec_state_test
def test_randomized_non_validated_execution_fields_first_payload__valid(spec, state):
    state = build_state_with_incomplete_transition(spec, state)
    yield from run_randomized_non_validated_execution_fields_test(spec, state)


@with_bellatrix_and_later
@spec_state_test
def test_randomized_non_validated_execution_fields_regular_payload__valid(spec, state):
    state = build_state_with_complete_transition(spec, state)
    yield from run_randomized_non_validated_execution_fields_test(spec, state)


@with_bellatrix_and_later
@spec_state_test
def test_randomized_non_validated_execution_fields_first_payload__invalid(spec, state):
    state = build_state_with_incomplete_transition(spec, state)
    yield from run_randomized_non_validated_execution_fields_test(spec, state, execution_valid=False)


@with_bellatrix_and_later
@spec_state_test
def test_randomized_non_validated_execution_fields_regular_payload__invalid(spec, state):
    state = build_state_with_complete_transition(spec, state)
    yield from run_randomized_non_validated_execution_fields_test(spec, state, execution_valid=False)
