from eth2spec.test.context import expect_assertion_error
from eth2spec.test.helpers.state import get_validator_index_by_pubkey


#
# Run processing
#


def run_execution_layer_exit_processing(spec, state, execution_layer_exit, valid=True, success=True):
    """
    Run ``process_execution_layer_exit``, yielding:
      - pre-state ('pre')
      - execution_layer_exit ('execution_layer_exit')
      - post-state ('post').
    If ``valid == False``, run expecting ``AssertionError``
    If ``success == False``, it doesn't initiate exit successfully
    """
    validator_index = get_validator_index_by_pubkey(state, execution_layer_exit.validator_pubkey)

    yield 'pre', state
    yield 'execution_layer_exit', execution_layer_exit

    if not valid:
        expect_assertion_error(lambda: spec.process_execution_layer_exit(state, execution_layer_exit))
        yield 'post', None
        return

    pre_exit_epoch = state.validators[validator_index].exit_epoch

    spec.process_execution_layer_exit(state, execution_layer_exit)

    yield 'post', state

    if success:
        assert pre_exit_epoch == spec.FAR_FUTURE_EPOCH
        assert state.validators[validator_index].exit_epoch < spec.FAR_FUTURE_EPOCH
    else:
        assert state.validators[validator_index].exit_epoch == pre_exit_epoch
