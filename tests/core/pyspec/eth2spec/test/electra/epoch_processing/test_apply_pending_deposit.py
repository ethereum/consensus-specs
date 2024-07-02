from eth2spec.test.context import (
    spec_state_test,
    with_electra_and_later,
)
from eth2spec.test.helpers.keys import privkeys, pubkeys
from tests.core.pyspec.eth2spec.test.helpers.deposits import build_deposit_data

@with_electra_and_later
@spec_state_test
def test_apply_pending_deposit_add_validator_to_registry(spec, state):
    amount = 100 

    # choose a value public key that's not in the validator set outside of the mainnet preset of 256
    index = 2000
    withdrawal_credentials = spec.BLS_WITHDRAWAL_PREFIX + spec.hash(pubkeys[index])[1:]
    deposit_data = build_deposit_data(spec,
                                          pubkeys[index],
                                          privkeys[index],
                                          amount,
                                          withdrawal_credentials,
                                          signed=True)
    deposit = spec.PendingDeposit(
        pubkey=pubkeys[index],
        withdrawal_credentials= withdrawal_credentials,
        amount=amount,
        slot=spec.GENESIS_SLOT,
        signature=deposit_data.signature,
        )
    old_validator_count = len(state.validators)
    assert spec.apply_pending_deposit(state,deposit) == True
    # validator count should increase by 1
    assert len(state.validators) == old_validator_count+1

@with_electra_and_later
@spec_state_test
def test_apply_pending_deposit_not_withdrawable_epoch_while_exiting(spec, state):
    amount = 100 
    # validator exit epoch must be less than far future
    state.validators[0].exit_epoch = spec.FAR_FUTURE_EPOCH - 1
    state.validators[0].withdrawable_epoch = spec.FAR_FUTURE_EPOCH 
  
    deposit = spec.PendingDeposit(
        pubkey=state.validators[0].pubkey,
        withdrawal_credentials= state.validators[0].withdrawal_credentials,
        amount=amount,
        slot=spec.GENESIS_SLOT,
        )
    assert spec.apply_pending_deposit(state,deposit) == False

@with_electra_and_later
@spec_state_test
def test_apply_pending_deposit_withdrawable_epoch_while_exiting(spec, state):
    amount = 100 
    state.slot = spec.SLOTS_PER_EPOCH * 2
    # validator exit epoch must be less than far future
    state.validators[0].exit_epoch = spec.FAR_FUTURE_EPOCH - 1
    state.validators[0].withdrawable_epoch = 0
  
    deposit = spec.PendingDeposit(
        pubkey=state.validators[0].pubkey,
        withdrawal_credentials= state.validators[0].withdrawal_credentials,
        amount=amount,
        slot=spec.GENESIS_SLOT,
        )
    # reset the balance 
    state.balances[0] = 0
    assert spec.apply_pending_deposit(state,deposit) == True
    assert state.balances[0] == amount

@with_electra_and_later
@spec_state_test
def test_apply_pending_deposit_withdrawable_epoch_while_exited(spec, state):
    amount = 100 
    state.validators[0].exit_epoch = spec.FAR_FUTURE_EPOCH
    # signature doesn't matter here as it's interpreted as a top-up
    deposit = spec.PendingDeposit(
        pubkey=state.validators[0].pubkey,
        withdrawal_credentials= state.validators[0].withdrawal_credentials,
        amount=amount,
        slot=spec.GENESIS_SLOT,
        )
    # reset the balance 
    state.balances[0] = 0
    assert spec.apply_pending_deposit(state,deposit) == True
    assert state.balances[0] == amount


@with_electra_and_later
@spec_state_test
def test_apply_pending_deposit_switch_to_compounding(spec, state):
    amount = 100 

    # choose a value public key that's not in the validator set
    index = 0
    withdrawal_credentials = spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX + spec.hash(pubkeys[index])[1:]
    compounding_credentials = spec.COMPOUNDING_WITHDRAWAL_PREFIX + spec.hash(pubkeys[index])[1:]
    state.validators[index].withdrawal_credentials = withdrawal_credentials
    state.validators[index].exit_epoch = spec.FAR_FUTURE_EPOCH
    deposit_data = build_deposit_data(spec,
                                          pubkeys[index],
                                          privkeys[index],
                                          amount,
                                          compounding_credentials,
                                          signed=True)
    deposit = spec.PendingDeposit(
        pubkey=pubkeys[index],
        withdrawal_credentials= compounding_credentials,
        amount=amount,
        slot=spec.GENESIS_SLOT,
        signature=deposit_data.signature,
        )
    state.balances[0] = 0
    assert spec.apply_pending_deposit(state,deposit) == True
    # validator count should increase by 1
    assert state.balances[0] == amount
    assert state.validators[0].withdrawal_credentials == compounding_credentials