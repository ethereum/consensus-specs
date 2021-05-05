from eth2spec.test.helpers.execution_payload import build_empty_execution_payload
from eth2spec.test.context import spec_state_test, expect_assertion_error, with_merge_and_later
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

    pre_exec_header = state.latest_execution_payload_header.copy()

    yield 'pre', state
    yield 'execution', {'execution_valid': execution_valid}
    yield 'execution_payload', execution_payload

    if not valid:
        expect_assertion_error(lambda: spec.process_execution_payload(state, execution_payload))
        yield 'post', None
        return

    spec.process_execution_payload(state, execution_payload)

    yield 'post', state

    assert pre_exec_header != state.latest_execution_payload_header
    # TODO: any more assertions to make?


@with_merge_and_later
@spec_state_test
def test_success_first_payload(spec, state):
    next_slot(spec, state)
    assert not spec.is_transition_completed(state)

    execution_payload = build_empty_execution_payload(spec, state)

    yield from run_execution_payload_processing(spec, state, execution_payload)


@with_merge_and_later
@spec_state_test
def test_success_regular_payload(spec, state):
    # TODO: setup state
    assert spec.is_transition_completed(state)

    # TODO: execution payload
    execution_payload = spec.ExecutionPayload()

    yield from run_execution_payload_processing(spec, state, execution_payload)


@with_merge_and_later
@spec_state_test
def test_success_first_payload_with_gap_slot(spec, state):
    # TODO: transition gap slot

    assert not spec.is_transition_completed(state)

    # TODO: execution payload
    execution_payload = spec.ExecutionPayload()

    yield from run_execution_payload_processing(spec, state, execution_payload)


@with_merge_and_later
@spec_state_test
def test_success_regular_payload_with_gap_slot(spec, state):
    # TODO: setup state
    assert spec.is_transition_completed(state)
    # TODO: transition gap slot

    # TODO: execution payload
    execution_payload = spec.ExecutionPayload()

    yield from run_execution_payload_processing(spec, state, execution_payload)


@with_merge_and_later
@spec_state_test
def test_bad_execution_first_payload(spec, state):
    # completely valid payload, but execution itself fails (e.g. block exceeds gas limit)

    # TODO: execution payload.
    execution_payload = spec.ExecutionPayload()

    yield from run_execution_payload_processing(spec, state, execution_payload, valid=False, execution_valid=False)


@with_merge_and_later
@spec_state_test
def test_bad_execution_regular_payload(spec, state):
    # completely valid payload, but execution itself fails (e.g. block exceeds gas limit)

    # TODO: execution payload
    execution_payload = spec.ExecutionPayload()

    yield from run_execution_payload_processing(spec, state, execution_payload, valid=False, execution_valid=False)


@with_merge_and_later
@spec_state_test
def test_bad_parent_hash_first_payload(spec, state):
    # TODO: execution payload
    execution_payload = spec.ExecutionPayload()

    yield from run_execution_payload_processing(spec, state, execution_payload, valid=False)


@with_merge_and_later
@spec_state_test
def test_bad_number_first_payload(spec, state):
    # TODO: execution payload
    execution_payload = spec.ExecutionPayload()

    yield from run_execution_payload_processing(spec, state, execution_payload, valid=False)


@with_merge_and_later
@spec_state_test
def test_bad_everything_first_payload(spec, state):
    # TODO: execution payload
    execution_payload = spec.ExecutionPayload()

    yield from run_execution_payload_processing(spec, state, execution_payload, valid=False)


@with_merge_and_later
@spec_state_test
def test_bad_timestamp_first_payload(spec, state):
    # TODO: execution payload
    execution_payload = spec.ExecutionPayload()

    yield from run_execution_payload_processing(spec, state, execution_payload, valid=False)


@with_merge_and_later
@spec_state_test
def test_bad_timestamp_regular_payload(spec, state):
    # TODO: execution payload
    execution_payload = spec.ExecutionPayload()

    yield from run_execution_payload_processing(spec, state, execution_payload, valid=False)
