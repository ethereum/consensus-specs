from eth2spec.test.context import spec_state_test, with_fulu_and_later
from eth2spec.test.helpers.deposits import prepare_state_and_deposit, run_deposit_processing


@with_fulu_and_later
@spec_state_test
def test_invalid_old_style_deposit_rejected(spec, state):
    validator_index = len(state.validators)
    amount = spec.MAX_EFFECTIVE_BALANCE
    deposit = prepare_state_and_deposit(spec, state, validator_index, amount, signed=True)

    yield from run_deposit_processing(spec, state, deposit, validator_index, valid=False)
