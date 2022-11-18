from eth2spec.test.helpers.bls_to_execution_changes import get_signed_address_change
from eth2spec.test.context import spec_state_test, expect_assertion_error, with_eip4844_and_later


def run_bls_to_execution_change_processing_no_op(spec, state, signed_address_change, valid=True):
    """
    Run ``process_bls_to_execution_change``, yielding:
      - pre-state ('pre')
      - address-change ('address_change')
      - post-state ('post').
    If ``valid == False``, run expecting ``AssertionError``
    """
    pre_state = state.copy()

    # yield pre-state
    yield 'pre', state

    yield 'address_change', signed_address_change

    # If the address_change is invalid, processing is aborted, and there is no post-state.
    if not valid:
        expect_assertion_error(lambda: spec.process_bls_to_execution_change(state, signed_address_change))
        yield 'post', None
        return

    # process address change
    spec.process_bls_to_execution_change(state, signed_address_change)

    # yield post-state
    yield 'post', state

    # Make sure state has NOT been changed
    assert state == pre_state


@with_eip4844_and_later
@spec_state_test
def test_no_op(spec, state):
    signed_address_change = get_signed_address_change(spec, state)
    yield from run_bls_to_execution_change_processing_no_op(spec, state, signed_address_change)
