from eth_consensus_specs.test.context import spec_state_test, with_heze_and_later
from eth_consensus_specs.test.helpers.bls_to_execution_changes import get_signed_address_change


def run_bls_to_execution_change_processing(spec, state, signed_address_change):
    yield "pre", state
    yield "address_change", signed_address_change
    spec.process_bls_to_execution_change(state, signed_address_change)
    yield "post", state


def park_validator(spec, state, index):
    validator = state.validators[index]
    validator.activation_eligibility_epoch = spec.GENESIS_EPOCH
    validator.activation_epoch = spec.FAR_FUTURE_EPOCH
    validator.exit_epoch = spec.FAR_FUTURE_EPOCH
    validator.withdrawable_epoch = spec.FAR_FUTURE_EPOCH


@with_heze_and_later
@spec_state_test
def test_never_activated_validator_requeued(spec, state):
    index = 0
    park_validator(spec, state, index)
    balance = state.balances[index]
    pre_pending_deposits = len(state.pending_deposits)
    signed_address_change = get_signed_address_change(spec, state, validator_index=index)

    yield from run_bls_to_execution_change_processing(spec, state, signed_address_change)

    validator = state.validators[index]
    assert validator.withdrawal_credentials[:1] == spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX
    assert state.balances[index] == 0
    assert validator.effective_balance == 0
    assert validator.activation_eligibility_epoch == spec.FAR_FUTURE_EPOCH
    assert validator.activation_epoch == spec.FAR_FUTURE_EPOCH
    assert not spec.is_eligible_for_activation(state, validator)
    assert len(state.pending_deposits) == pre_pending_deposits + 1
    assert state.pending_deposits[-1] == spec.PendingDeposit(
        pubkey=validator.pubkey,
        withdrawal_credentials=validator.withdrawal_credentials,
        amount=balance,
        signature=spec.bls.G2_POINT_AT_INFINITY,
        slot=spec.GENESIS_SLOT,
    )


@with_heze_and_later
@spec_state_test
def test_active_validator_not_requeued(spec, state):
    index = 0
    assert spec.is_active_validator(state.validators[index], spec.get_current_epoch(state))
    balance = state.balances[index]
    effective_balance = state.validators[index].effective_balance
    pre_pending_deposits = len(state.pending_deposits)
    signed_address_change = get_signed_address_change(spec, state, validator_index=index)

    yield from run_bls_to_execution_change_processing(spec, state, signed_address_change)

    validator = state.validators[index]
    assert validator.withdrawal_credentials[:1] == spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX
    assert state.balances[index] == balance
    assert validator.effective_balance == effective_balance
    assert len(state.pending_deposits) == pre_pending_deposits
