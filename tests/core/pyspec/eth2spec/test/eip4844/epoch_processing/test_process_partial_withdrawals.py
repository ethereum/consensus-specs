from eth2spec.test.context import (
    spec_state_test,
    with_eip4844_and_later,
)
from eth2spec.test.helpers.epoch_processing import run_epoch_processing_to
from eth2spec.test.helpers.withdrawals import (
    set_validator_partially_withdrawable,
)


def run_process_partial_withdrawals_no_op(spec, state, num_expected_withdrawals=None):
    # Run rest of epoch processing before predicting partial withdrawals as
    # balance changes can affect withdrawability
    run_epoch_processing_to(spec, state, 'process_partial_withdrawals')

    partially_withdrawable_indices = [
        index for index, validator in enumerate(state.validators)
        if spec.is_partially_withdrawable_validator(validator, state.balances[index])
    ]
    num_partial_withdrawals = min(len(partially_withdrawable_indices), spec.MAX_PARTIAL_WITHDRAWALS_PER_EPOCH)

    if num_expected_withdrawals is not None:
        assert num_partial_withdrawals == num_expected_withdrawals
    else:
        num_expected_withdrawals = num_partial_withdrawals

    pre_state = state.copy()

    yield 'pre', state
    spec.process_partial_withdrawals(state)
    yield 'post', state

    # Make sure state has NOT been changed
    assert state == pre_state


@with_eip4844_and_later
@spec_state_test
def test_no_op(spec, state):
    validator_index = len(state.validators) // 2
    set_validator_partially_withdrawable(spec, state, validator_index)

    yield from run_process_partial_withdrawals_no_op(spec, state, 1)
