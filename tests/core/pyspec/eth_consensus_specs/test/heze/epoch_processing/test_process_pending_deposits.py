from eth_consensus_specs.test.context import (
    always_bls,
    spec_state_test,
    spec_test,
    with_heze_and_later,
    with_phases,
    with_state,
)
from eth_consensus_specs.test.helpers.constants import GLOAS, HEZE
from eth_consensus_specs.test.helpers.deposits import (
    prepare_pending_deposit,
    run_pending_deposit_applying,
)
from eth_consensus_specs.test.helpers.epoch_processing import run_epoch_processing_with
from eth_consensus_specs.test.helpers.genesis import create_genesis_state
from eth_consensus_specs.test.helpers.keys import pubkeys


@with_heze_and_later
@spec_state_test
@always_bls
def test_new_bls_withdrawal_credentials_valid_signature(spec, state):
    validator_index = len(state.validators)
    withdrawal_credentials = spec.BLS_WITHDRAWAL_PREFIX + spec.sha256(pubkeys[validator_index])[1:]
    deposit = prepare_pending_deposit(
        spec,
        validator_index,
        spec.MIN_ACTIVATION_BALANCE,
        withdrawal_credentials=withdrawal_credentials,
        signed=True,
    )

    yield from run_pending_deposit_applying(spec, state, deposit, validator_index, effective=False)


@with_heze_and_later
@spec_state_test
@always_bls
def test_new_bls_withdrawal_credentials_invalid_signature(spec, state):
    validator_index = len(state.validators)
    withdrawal_credentials = spec.BLS_WITHDRAWAL_PREFIX + spec.sha256(pubkeys[validator_index])[1:]
    deposit = prepare_pending_deposit(
        spec,
        validator_index,
        spec.MIN_ACTIVATION_BALANCE,
        withdrawal_credentials=withdrawal_credentials,
        signed=False,
    )

    yield from run_pending_deposit_applying(spec, state, deposit, validator_index, effective=False)


@with_heze_and_later
@spec_state_test
@always_bls
def test_bls_withdrawal_credentials_top_up_valid_signature(spec, state):
    validator_index = 0
    withdrawal_credentials = spec.BLS_WITHDRAWAL_PREFIX + spec.sha256(pubkeys[validator_index])[1:]
    state.validators[validator_index].withdrawal_credentials = withdrawal_credentials
    deposit = prepare_pending_deposit(
        spec,
        validator_index,
        spec.MIN_ACTIVATION_BALANCE,
        withdrawal_credentials=withdrawal_credentials,
        signed=True,
    )
    assert spec.is_valid_deposit_signature(
        deposit.pubkey, deposit.withdrawal_credentials, deposit.amount, deposit.signature
    )

    yield from run_pending_deposit_applying(spec, state, deposit, validator_index)


@with_heze_and_later
@spec_state_test
@always_bls
def test_bls_withdrawal_credentials_top_up_invalid_signature(spec, state):
    validator_index = 0
    withdrawal_credentials = spec.BLS_WITHDRAWAL_PREFIX + spec.sha256(pubkeys[validator_index])[1:]
    state.validators[validator_index].withdrawal_credentials = withdrawal_credentials
    deposit = prepare_pending_deposit(
        spec,
        validator_index,
        spec.MIN_ACTIVATION_BALANCE,
        withdrawal_credentials=withdrawal_credentials,
        signed=False,
    )

    yield from run_pending_deposit_applying(spec, state, deposit, validator_index)


@with_heze_and_later
@spec_state_test
@always_bls
def test_bls_withdrawal_credentials_followed_by_eth1_deposit(spec, state):
    validator_index = len(state.validators)
    bls_credentials = spec.BLS_WITHDRAWAL_PREFIX + spec.sha256(pubkeys[validator_index])[1:]
    eth1_credentials = spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX + b"\x00" * 11 + b"\x42" * 20
    amount = spec.MIN_ACTIVATION_BALANCE
    bls_deposit = prepare_pending_deposit(
        spec, validator_index, amount, withdrawal_credentials=bls_credentials, signed=True
    )
    eth1_deposit = prepare_pending_deposit(
        spec, validator_index, amount, withdrawal_credentials=eth1_credentials, signed=True
    )
    state.pending_deposits = spec.PendingDeposits.of(bls_deposit, eth1_deposit)
    state.deposit_balance_to_consume = 2 * amount

    yield from run_epoch_processing_with(spec, state, "process_pending_deposits")

    assert len(state.validators) == validator_index + 1
    assert state.validators[validator_index].withdrawal_credentials == eth1_credentials
    assert state.balances[validator_index] == amount
    assert state.pending_deposits == spec.PendingDeposits()


@with_phases(phases=[HEZE], other_phases=[GLOAS])
@spec_test
@with_state
@always_bls
def test_bls_withdrawal_credentials_queued_before_heze(spec, phases, state):
    pre_spec = phases[GLOAS]
    pre_state = create_genesis_state(
        pre_spec, list(state.balances), pre_spec.MIN_ACTIVATION_BALANCE
    )
    validator_index = len(pre_state.validators)
    withdrawal_credentials = (
        pre_spec.BLS_WITHDRAWAL_PREFIX + pre_spec.sha256(pubkeys[validator_index])[1:]
    )
    deposit = prepare_pending_deposit(
        pre_spec,
        validator_index,
        pre_spec.MIN_ACTIVATION_BALANCE,
        withdrawal_credentials=withdrawal_credentials,
        signed=True,
    )
    pre_state.pending_deposits.append(deposit)
    state = spec.upgrade_to_heze(pre_state)

    yield from run_epoch_processing_with(spec, state, "process_pending_deposits")

    assert len(state.validators) == validator_index
    assert len(state.balances) == validator_index
    assert state.pending_deposits == spec.PendingDeposits()
