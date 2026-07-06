from eth_consensus_specs.test.context import always_bls, spec_state_test, with_gloas_and_later
from eth_consensus_specs.test.helpers.deposits import prepare_pending_deposit
from eth_consensus_specs.test.helpers.epoch_processing import run_epoch_processing_with
from eth_consensus_specs.test.helpers.keys import privkeys
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
    assert state.pending_deposits == []
