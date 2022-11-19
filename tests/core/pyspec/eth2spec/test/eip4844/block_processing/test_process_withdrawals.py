
from eth2spec.test.context import spec_state_test, expect_assertion_error, with_eip4844_and_later
from eth2spec.test.helpers.execution_payload import (
    build_empty_execution_payload,
)
from eth2spec.test.helpers.state import next_slot


def run_withdrawals_processing(spec, state, execution_payload, valid=True):
    """
    Run ``process_execution_payload``, yielding:
      - pre-state ('pre')
      - execution payload ('execution_payload')
      - post-state ('post').
    If ``valid == False``, run expecting ``AssertionError``
    """
    pre_state = state.copy()

    yield 'pre', state
    yield 'execution_payload', execution_payload

    if not valid:
        expect_assertion_error(lambda: spec.process_withdrawals(state, execution_payload))
        yield 'post', None
        return

    spec.process_withdrawals(state, execution_payload)

    yield 'post', state

    # Make sure state has NOT been changed
    assert state == pre_state


@with_eip4844_and_later
@spec_state_test
def test_no_op(spec, state):
    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)

    yield from run_withdrawals_processing(spec, state, execution_payload)
