from eth_consensus_specs.test.context import always_bls, spec_state_test, with_gloas_and_later
from eth_consensus_specs.test.helpers.deposits import prepare_pending_deposit
from eth_consensus_specs.test.helpers.epoch_processing import run_epoch_processing_with
from eth_consensus_specs.test.helpers.keys import (
    builder_pubkey_to_privkey,
    privkeys,
)
from eth_consensus_specs.utils import bls


@with_gloas_and_later
@spec_state_test
@always_bls
def test_process_pending_deposits__builder_deposit_domain(spec, state):
    """
    Test that a pending deposit signed under DOMAIN_BUILDER_DEPOSIT is dropped.

    A signature over the same DepositMessage under DOMAIN_BUILDER_DEPOSIT is a
    valid builder deposit signature. It must not be accepted here, otherwise a
    builder deposit could be replayed to the validator deposit contract to
    register its pubkey as a validator.
    """
    # A new validator, pubkey doesn't exist in the state
    validator_index = len(state.validators)
    amount = spec.MIN_ACTIVATION_BALANCE
    pre_validator_count = len(state.validators)

    deposit = prepare_pending_deposit(spec, validator_index, amount, signed=False)

    # Sign over the builder deposit domain instead of DOMAIN_DEPOSIT
    deposit_message = spec.DepositMessage(
        pubkey=deposit.pubkey,
        withdrawal_credentials=deposit.withdrawal_credentials,
        amount=deposit.amount,
    )
    domain = spec.compute_domain(spec.DOMAIN_BUILDER_DEPOSIT)
    signing_root = spec.compute_signing_root(deposit_message, domain)
    deposit.signature = bls.Sign(privkeys[validator_index], signing_root)

    state.pending_deposits.append(deposit)

    yield from run_epoch_processing_with(spec, state, "process_pending_deposits")

    # The deposit was dropped: no validator created and no balance applied
    assert len(state.validators) == pre_validator_count
    assert state.pending_deposits == spec.PendingDeposits()


@with_gloas_and_later
@spec_state_test
def test_process_pending_deposits__existing_validator_valid_non_builder_topup(spec, state):
    """A valid non-B0 top-up funds the existing validator, not its same-key builder."""
    amount = spec.MIN_DEPOSIT_AMOUNT
    pubkey = state.validators[0].pubkey
    address = spec.ExecutionAddress(spec.sha256(pubkey)[12:])
    spec.add_builder_to_registry(
        state, pubkey, spec.PAYLOAD_BUILDER_VERSION, address, amount * 2, spec.GENESIS_SLOT
    )
    validator_topup = prepare_pending_deposit(
        spec,
        0,
        amount * 3,
        withdrawal_credentials=spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX + b"\x00" * 11 + b"\xab" * 20,
        signed=True,
    )
    state.pending_deposits = spec.PendingDeposits.of(validator_topup)
    pre_builders = [builder.copy() for builder in state.builders]
    pre_validator_count = len(state.validators)
    pre_balance = state.balances[0]
    pre_credentials = state.validators[0].withdrawal_credentials

    yield from run_epoch_processing_with(spec, state, "process_pending_deposits")

    assert list(state.pending_deposits) == []
    assert list(state.builders) == pre_builders
    assert len(state.validators) == pre_validator_count
    assert state.validators[0].withdrawal_credentials == pre_credentials
    assert state.balances[0] == pre_balance + validator_topup.amount


@with_gloas_and_later
@spec_state_test
@always_bls
def test_process_pending_deposits__pending_validator_invalid_non_builder_topup(spec, state):
    """A valid deposit creates the validator; its later invalid non-B0 top-up still funds it."""
    amount = spec.MIN_DEPOSIT_AMOUNT
    pubkey = state.builders[0].pubkey
    privkey = builder_pubkey_to_privkey[pubkey]
    validator_credentials = spec.COMPOUNDING_WITHDRAWAL_PREFIX + b"\x00" * 11 + b"\xab" * 20
    validator_deposit = prepare_pending_deposit(
        spec,
        0,
        amount,
        pubkey=pubkey,
        privkey=privkey,
        withdrawal_credentials=validator_credentials,
        signed=True,
    )
    invalid_topup = prepare_pending_deposit(
        spec,
        0,
        amount * 3,
        pubkey=pubkey,
        privkey=privkey,
        withdrawal_credentials=spec.COMPOUNDING_WITHDRAWAL_PREFIX + b"\x00" * 11 + b"\xcd" * 20,
        signed=False,
    )
    state.pending_deposits = spec.PendingDeposits.of(validator_deposit, invalid_topup)
    pre_builders = [builder.copy() for builder in state.builders]
    pre_validator_count = len(state.validators)

    yield from run_epoch_processing_with(spec, state, "process_pending_deposits")

    assert list(state.pending_deposits) == []
    assert list(state.builders) == pre_builders
    assert len(state.validators) == pre_validator_count + 1
    assert state.validators[-1].pubkey == pubkey
    assert state.validators[-1].withdrawal_credentials == validator_credentials
    assert state.balances[-1] == validator_deposit.amount + invalid_topup.amount


@with_gloas_and_later
@spec_state_test
@always_bls
def test_process_pending_deposits__invalid_builder_topup_with_existing_validator(spec, state):
    """An invalid B0 deposit retained before builder registration tops up the validator."""
    amount = spec.MIN_DEPOSIT_AMOUNT
    pubkey = state.validators[0].pubkey
    builder_credentials = spec.BUILDER_WITHDRAWAL_PREFIX + b"\x00" * 11 + spec.sha256(pubkey)[12:]
    spec.add_builder_to_registry(
        state,
        pubkey,
        spec.PAYLOAD_BUILDER_VERSION,
        spec.ExecutionAddress(builder_credentials[12:]),
        amount * 2,
        spec.GENESIS_SLOT,
    )
    invalid_topup = prepare_pending_deposit(
        spec,
        0,
        amount * 3,
        withdrawal_credentials=builder_credentials,
        signed=False,
    )
    state.pending_deposits = spec.PendingDeposits.of(invalid_topup)
    pre_builders = [builder.copy() for builder in state.builders]
    pre_validator_count = len(state.validators)
    pre_balance = state.balances[0]
    pre_credentials = state.validators[0].withdrawal_credentials

    yield from run_epoch_processing_with(spec, state, "process_pending_deposits")

    assert list(state.pending_deposits) == []
    assert list(state.builders) == pre_builders
    assert len(state.validators) == pre_validator_count
    assert state.validators[0].withdrawal_credentials == pre_credentials
    assert state.balances[0] == pre_balance + invalid_topup.amount
