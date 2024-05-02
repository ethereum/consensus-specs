from eth2spec.test.context import (
    spec_state_test,
    with_capella_and_later,
)
from eth2spec.test.helpers.forks import is_post_electra
from eth2spec.test.helpers.state import next_epoch_via_block
from eth2spec.test.helpers.deposits import (
    prepare_state_and_deposit,
    run_deposit_processing,
)
from eth2spec.test.helpers.withdrawals import set_validator_fully_withdrawable


@with_capella_and_later
@spec_state_test
def test_success_top_up_to_withdrawn_validator(spec, state):
    validator_index = 0

    # Fully withdraw validator
    set_validator_fully_withdrawable(spec, state, validator_index)
    assert state.balances[validator_index] > 0
    next_epoch_via_block(spec, state)
    assert state.balances[validator_index] == 0
    assert state.validators[validator_index].effective_balance > 0
    next_epoch_via_block(spec, state)
    assert state.validators[validator_index].effective_balance == 0

    # Make a top-up balance to validator
    amount = spec.MAX_EFFECTIVE_BALANCE // 4
    deposit = prepare_state_and_deposit(spec, state, validator_index, amount, signed=True)

    yield from run_deposit_processing(spec, state, deposit, validator_index)

    if is_post_electra(spec):
        pending_balance_deposits_len = len(state.pending_balance_deposits)
        pending_balance_deposit = state.pending_balance_deposits[pending_balance_deposits_len - 1]
        assert pending_balance_deposit.amount == amount
        assert pending_balance_deposit.index == validator_index
    else:
        assert state.balances[validator_index] == amount
        assert state.validators[validator_index].effective_balance == 0

    validator = state.validators[validator_index]
    balance = state.balances[validator_index]
    current_epoch = spec.get_current_epoch(state)

    if is_post_electra(spec):
        has_execution_withdrawal = spec.has_execution_withdrawal_credential(validator)
        is_withdrawable = validator.withdrawable_epoch <= current_epoch
        has_non_zero_balance = pending_balance_deposit.amount > 0
        # NOTE: directly compute `is_fully_withdrawable_validator` conditions here
        # to work around how the epoch processing changed balance updates
        assert has_execution_withdrawal and is_withdrawable and has_non_zero_balance
    else:
        assert spec.is_fully_withdrawable_validator(validator, balance, current_epoch)
