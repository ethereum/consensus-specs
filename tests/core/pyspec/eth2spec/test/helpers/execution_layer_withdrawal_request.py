from eth2spec.test.context import expect_assertion_error
from eth2spec.test.helpers.state import get_validator_index_by_pubkey


#
# Run processing
#


def run_withdrawal_request_processing(spec, state, withdrawal_request, valid=True, success=True):
    """
    Run ``process_withdrawal_request``, yielding:
      - pre-state ('pre')
      - withdrawal_request ('withdrawal_request')
      - post-state ('post').
    If ``valid == False``, run expecting ``AssertionError``
    If ``success == False``, it doesn't initiate exit successfully
    """
    validator_index = get_validator_index_by_pubkey(state, withdrawal_request.validator_pubkey)

    yield 'pre', state
    yield 'withdrawal_request', withdrawal_request

    if not valid:
        expect_assertion_error(lambda: spec.process_withdrawal_request(state, withdrawal_request))
        yield 'post', None
        return

    pre_exit_epoch = state.validators[validator_index].exit_epoch

    spec.process_withdrawal_request(state, withdrawal_request)

    yield 'post', state

    if success:
        assert pre_exit_epoch == spec.FAR_FUTURE_EPOCH
        assert state.validators[validator_index].exit_epoch < spec.FAR_FUTURE_EPOCH
    else:
        assert state.validators[validator_index].exit_epoch == pre_exit_epoch
