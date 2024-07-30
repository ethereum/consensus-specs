from eth2spec.test.helpers.epoch_processing import run_epoch_processing_with
from eth2spec.test.context import (
    spec_state_test,
    with_electra_and_later,
)
from eth2spec.test.helpers.keys import privkeys, pubkeys
from tests.core.pyspec.eth2spec.test.helpers.deposits import build_deposit_data
from eth2spec.test.helpers.state import next_epoch_via_block


def run_process_pending_deposits(spec, state):
    yield from run_epoch_processing_with(
        spec, state, 'process_pending_deposits')


@with_electra_and_later
@spec_state_test
def test_apply_pending_deposit_add_validator_to_registry(spec, state):
    amount = spec.MIN_ACTIVATION_BALANCE

    # select validator set outside of the mainnet preset of 256
    index = len(state.validators)
    withdrawal_credentials = (
        spec.BLS_WITHDRAWAL_PREFIX + spec.hash(pubkeys[index])[1:]
    )
    deposit_data = build_deposit_data(spec,
                                      pubkeys[index],
                                      privkeys[index],
                                      amount,
                                      withdrawal_credentials,
                                      signed=True)
    deposit = spec.PendingDeposit(
        pubkey=pubkeys[index],
        withdrawal_credentials=withdrawal_credentials,
        amount=amount,
        slot=spec.GENESIS_SLOT,
        signature=deposit_data.signature,
    )
    old_validator_count = len(state.validators)
    state.pending_deposits.append(deposit)
    yield from run_process_pending_deposits(spec, state)
    # validator count should increase by 1
    assert len(state.validators) == old_validator_count + 1


@with_electra_and_later
@spec_state_test
def test_apply_pending_deposit_increases_balance(spec, state):
    amount = 100
    # signature doesn't matter here as it's interpreted as a top-up
    deposit = spec.PendingDeposit(
        pubkey=state.validators[0].pubkey,
        withdrawal_credentials=state.validators[0].withdrawal_credentials,
        amount=amount,
        slot=spec.GENESIS_SLOT
    )
    # run test
    spec.apply_pending_deposit(state, deposit)
    assert state.balances[0] == amount


@with_electra_and_later
@spec_state_test
def test_apply_pending_deposit_switch_to_compounding(spec, state):
    amount = 100

    # choose a value public key that's in the validator set
    index = 0
    withdrawal_credentials = (
        spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX +
        spec.hash(pubkeys[index])[1:]
    )
    compounding_credentials = (
        spec.COMPOUNDING_WITHDRAWAL_PREFIX +
        spec.hash(pubkeys[index])[1:]
    )
    # advance the state
    next_epoch_via_block(spec, state)
    state.validators[index].withdrawal_credentials = withdrawal_credentials
    # set validator to be exited by current epoch
    state.validators[index].exit_epoch = spec.get_current_epoch(state) - 1
    deposit_data = build_deposit_data(spec,
                                      pubkeys[index],
                                      privkeys[index],
                                      amount,
                                      compounding_credentials,
                                      signed=True)
    deposit = spec.PendingDeposit(
        pubkey=pubkeys[index],
        withdrawal_credentials=compounding_credentials,
        amount=amount,
        slot=spec.GENESIS_SLOT,
        signature=deposit_data.signature,
    )
    state.balances[index] = 0
    # run test
    spec.apply_pending_deposit(state, deposit)
    # validator balance should increase
    assert state.balances[index] == amount
    current_credentials = state.validators[0].withdrawal_credentials
    assert current_credentials == compounding_credentials


@with_electra_and_later
@spec_state_test
def test_apply_pending_deposit_switch_to_compounding_not_exited(spec, state):
    amount = 100

    # choose a value public key that's in the validator set
    index = 0
    withdrawal_credentials = (
        spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX + spec.hash(pubkeys[index])[1:]
    )
    compounding_credentials = (
        spec.COMPOUNDING_WITHDRAWAL_PREFIX + spec.hash(pubkeys[index])[1:]
    )
    state.validators[index].withdrawal_credentials = withdrawal_credentials
    deposit_data = build_deposit_data(spec,
                                      pubkeys[index],
                                      privkeys[index],
                                      amount,
                                      compounding_credentials,
                                      signed=True)
    deposit = spec.PendingDeposit(
        pubkey=pubkeys[index],
        withdrawal_credentials=compounding_credentials,
        amount=amount,
        slot=spec.GENESIS_SLOT,
        signature=deposit_data.signature,
    )
    state.balances[index] = 0
    # run test
    spec.apply_pending_deposit(state, deposit)
    # validator balance should increase
    assert state.balances[index] == amount
    # make sure validator did not switch to compounding if not exited
    current_credentials = state.validators[0].withdrawal_credentials
    assert current_credentials == withdrawal_credentials
    # postpone pending_deposit
    assert len(state.pending_deposits) == 0
