from eth2spec.test.context import (
    with_eip4844_and_later,
    spec_state_test,
)
from eth2spec.test.helpers.epoch_processing import (
    run_epoch_processing_to,
)
from eth2spec.test.helpers.withdrawals import (
    set_validator_fully_withdrawable,
)


def run_process_full_withdrawals_no_op(spec, state, num_expected_withdrawals=None):
    run_epoch_processing_to(spec, state, 'process_full_withdrawals')

    state.next_withdrawal_index = 0
    to_be_withdrawn_indices = [
        index for index, validator in enumerate(state.validators)
        if spec.is_fully_withdrawable_validator(validator, state.balances[index], spec.get_current_epoch(state))
    ]

    if num_expected_withdrawals is not None:
        assert len(to_be_withdrawn_indices) == num_expected_withdrawals
    else:
        num_expected_withdrawals = len(to_be_withdrawn_indices)

    pre_state = state.copy()

    yield 'pre', state
    spec.process_full_withdrawals(state)
    yield 'post', state

    # Make sure state has NOT been changed
    assert state == pre_state


@with_eip4844_and_later
@spec_state_test
def test_no_op(spec, state):
    # Make one validator withdrawable
    set_validator_fully_withdrawable(spec, state, 0)

    yield from run_process_full_withdrawals_no_op(spec, state, 1)
