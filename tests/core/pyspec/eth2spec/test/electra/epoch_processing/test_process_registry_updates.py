from eth2spec.test.helpers.deposits import mock_deposit
from eth2spec.test.helpers.state import next_epoch
from eth2spec.test.context import spec_state_test, with_electra_and_later
from eth2spec.test.helpers.epoch_processing import run_epoch_processing_with
from eth2spec.test.helpers.withdrawals import (
    set_eth1_withdrawal_credential_with_balance,
    set_compounding_withdrawal_credential_with_balance
)


def run_test_activation_queue_eligibility(spec, state, validator_index, balance):
    # move past first two irregular epochs wrt finality
    next_epoch(spec, state)
    next_epoch(spec, state)

    state.balances[validator_index] = balance
    state.validators[validator_index].effective_balance = balance - balance % spec.EFFECTIVE_BALANCE_INCREMENT

    # ready for entrance into activation queue
    mock_deposit(spec, state, validator_index)

    yield from run_epoch_processing_with(spec, state, 'process_registry_updates')

    # validator moved into activation queue if eligible
    validator = state.validators[validator_index]
    if validator.effective_balance <= (spec.MIN_ACTIVATION_BALANCE - spec.EFFECTIVE_BALANCE_INCREMENT):
        assert validator.activation_eligibility_epoch == spec.FAR_FUTURE_EPOCH
    else:
        assert validator.activation_eligibility_epoch < spec.FAR_FUTURE_EPOCH


@with_electra_and_later
@spec_state_test
def test_activation_queue_eligibility__less_than_min_activation_balance(spec, state):
    index = 3
    balance = spec.MIN_ACTIVATION_BALANCE - spec.EFFECTIVE_BALANCE_INCREMENT
    yield from run_test_activation_queue_eligibility(spec, state, index, balance)


@with_electra_and_later
@spec_state_test
def test_activation_queue_eligibility__min_activation_balance(spec, state):
    index = 5
    balance = spec.MIN_ACTIVATION_BALANCE
    yield from run_test_activation_queue_eligibility(spec, state, index, balance)


@with_electra_and_later
@spec_state_test
def test_activation_queue_eligibility__min_activation_balance_eth1_creds(spec, state):
    index = 7
    balance = spec.MIN_ACTIVATION_BALANCE
    set_eth1_withdrawal_credential_with_balance(spec, state, index)
    yield from run_test_activation_queue_eligibility(spec, state, index, balance)


@with_electra_and_later
@spec_state_test
def test_activation_queue_eligibility__min_activation_balance_compounding_creds(spec, state):
    index = 11
    balance = spec.MIN_ACTIVATION_BALANCE
    set_compounding_withdrawal_credential_with_balance(spec, state, index)
    yield from run_test_activation_queue_eligibility(spec, state, index, balance)


@with_electra_and_later
@spec_state_test
def test_activation_queue_eligibility__greater_than_min_activation_balance(spec, state):
    index = 13
    balance = spec.MIN_ACTIVATION_BALANCE + spec.EFFECTIVE_BALANCE_INCREMENT
    set_compounding_withdrawal_credential_with_balance(spec, state, index)
    yield from run_test_activation_queue_eligibility(spec, state, index, balance)

@with_electra_and_later
@spec_state_test
def test_activation_queue_eligibility__fractional_greater_than_min_activation_balance(spec, state):
    index = 15
    balance = spec.MIN_ACTIVATION_BALANCE + (spec.EFFECTIVE_BALANCE_INCREMENT * 0.6)
    set_compounding_withdrawal_credential_with_balance(spec, state, index)
    yield from run_test_activation_queue_eligibility(spec, state, index, balance)
