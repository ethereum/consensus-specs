from eth2spec.test.context import (
    always_bls,
    spec_state_test,
    with_gloas_and_later,
    expect_assertion_error,
)
from eth2spec.test.helpers.keys import pubkey_to_privkey
from eth2spec.test.helpers.voluntary_exits import sign_voluntary_exit
from eth2spec.test.helpers.state import next_epoch


def create_test_builder(spec, state, balance=None):
    """
    Helper to add a builder to state for testing.
    
    Returns: (builder_index, pubkey)
    """
    if balance is None:
        balance = spec.MIN_DEPOSIT_AMOUNT + spec.MIN_ACTIVATION_BALANCE
    
    # Use validator 0's pubkey (exists in pubkey_to_privkey for signing)
    if len(state.validators) > 0:
        pubkey = state.validators[0].pubkey
    else:
        pubkey = spec.BLSPubkey(b'\x42' * 48)
    
    builder = spec.Builder(
        pubkey=pubkey,
        version=3,
        execution_address=spec.ExecutionAddress(b'\x50' * 20),
        balance=balance,
        deposit_epoch=0,  # Always use epoch 0 for simplicity
        withdrawable_epoch=spec.FAR_FUTURE_EPOCH,
    )
    state.builders.append(builder)
    return len(state.builders) - 1, pubkey


@with_gloas_and_later
@spec_state_test
def test_builder_voluntary_exit_success(spec, state):
    """
    Test successful builder voluntary exit with no pending balance.
    
    Builder can exit when:
    - Builder is active (deposit_epoch < finalized epoch, withdrawable_epoch == FAR_FUTURE_EPOCH)
    - No pending payments in builder_pending_payments
    - No pending withdrawals in builder_pending_withdrawals
    """
    # Create builder with deposit_epoch=0
    builder_index, pubkey = create_test_builder(spec, state)
    privkey = pubkey_to_privkey[pubkey]
    
    # Manually set finalized checkpoint to make builder active
    # Builder is active when deposit_epoch (0) < finalized_checkpoint.epoch
    state.finalized_checkpoint.epoch = spec.Epoch(2)
    
    # Verify builder is active
    assert spec.is_active_builder(state, builder_index), \
        f"Builder not active: deposit={state.builders[builder_index].deposit_epoch}, finalized={state.finalized_checkpoint.epoch}"
    
    # Verify no pending balance
    assert spec.get_pending_balance_to_withdraw_for_builder(state, builder_index) == 0
    
    current_epoch = spec.get_current_epoch(state)
    
    # Create voluntary exit with builder index encoded as validator index
    validator_index = spec.convert_builder_index_to_validator_index(builder_index)
    voluntary_exit = spec.VoluntaryExit(
        epoch=current_epoch,
        validator_index=validator_index,
    )
    signed_voluntary_exit = sign_voluntary_exit(spec, state, voluntary_exit, privkey)
    
    # Process the exit directly (not using validator-focused helper)
    yield 'pre', state
    spec.process_voluntary_exit(state, signed_voluntary_exit)
    yield 'post', state
    
    # Verify builder is no longer active
    assert not spec.is_active_builder(state, builder_index)
    
    # Verify withdrawable_epoch is set
    expected_withdrawable = current_epoch + spec.config.MIN_BUILDER_WITHDRAWABILITY_DELAY
    assert state.builders[builder_index].withdrawable_epoch == expected_withdrawable


@with_gloas_and_later
@spec_state_test
def test_builder_voluntary_exit_with_pending_payment(spec, state):
    """
    Test that builder cannot exit while having pending payment.
    
    get_pending_balance_to_withdraw_for_builder checks both:
    - builder_pending_payments (not yet at quorum)
    - builder_pending_withdrawals (queued for withdrawal)
    
    Builder must wait for all to clear before exiting.
    """
    # Create builder
    builder_index, pubkey = create_test_builder(spec, state)
    privkey = pubkey_to_privkey[pubkey]
    
    # Make builder active
    state.finalized_checkpoint.epoch = spec.Epoch(2)
    assert spec.is_active_builder(state, builder_index)
    
    # Add pending payment for this builder
    payment_amount = spec.MIN_ACTIVATION_BALANCE
    payment = spec.BuilderPendingPayment(
        weight=spec.get_builder_payment_quorum_threshold(state) + 1,
        withdrawal=spec.BuilderPendingWithdrawal(
            fee_recipient=spec.ExecutionAddress(b'\x60' * 20),
            amount=payment_amount,
            builder_index=builder_index,
        ),
    )
    state.builder_pending_payments[0] = payment
    
    # Verify builder has pending balance
    pending_balance = spec.get_pending_balance_to_withdraw_for_builder(state, builder_index)
    assert pending_balance == payment_amount
    
    current_epoch = spec.get_current_epoch(state)
    
    # Try to exit - should FAIL
    validator_index = spec.convert_builder_index_to_validator_index(builder_index)
    voluntary_exit = spec.VoluntaryExit(
        epoch=current_epoch,
        validator_index=validator_index,
    )
    signed_voluntary_exit = sign_voluntary_exit(spec, state, voluntary_exit, privkey)
    
    # Should fail because pending balance != 0
    yield 'pre', state
    yield 'voluntary_exit', signed_voluntary_exit
    expect_assertion_error(lambda: spec.process_voluntary_exit(state, signed_voluntary_exit))
    yield 'post', None


@with_gloas_and_later
@spec_state_test
def test_builder_voluntary_exit_with_pending_withdrawal(spec, state):
    """
    Test that builder cannot exit while having pending withdrawal.
    
    Even after payment reaches quorum and moves to builder_pending_withdrawals,
    builder must wait for withdrawal to be processed.
    """
    # Create builder
    builder_index, pubkey = create_test_builder(spec, state)
    privkey = pubkey_to_privkey[pubkey]
    
    # Make builder active
    state.finalized_checkpoint.epoch = spec.Epoch(2)
    assert spec.is_active_builder(state, builder_index)
    
    # Add withdrawal directly to pending withdrawals queue
    withdrawal_amount = spec.MIN_ACTIVATION_BALANCE
    withdrawal = spec.BuilderPendingWithdrawal(
        fee_recipient=spec.ExecutionAddress(b'\x70' * 20),
        amount=withdrawal_amount,
        builder_index=builder_index,
    )
    state.builder_pending_withdrawals.append(withdrawal)
    
    # Verify builder has pending withdrawal
    pending_balance = spec.get_pending_balance_to_withdraw_for_builder(state, builder_index)
    assert pending_balance == withdrawal_amount
    
    current_epoch = spec.get_current_epoch(state)
    
    # Try to exit - should FAIL
    validator_index = spec.convert_builder_index_to_validator_index(builder_index)
    voluntary_exit = spec.VoluntaryExit(
        epoch=current_epoch,
        validator_index=validator_index,
    )
    signed_voluntary_exit = sign_voluntary_exit(spec, state, voluntary_exit, privkey)
    
    # Should fail because pending balance != 0
    yield 'pre', state
    yield 'voluntary_exit', signed_voluntary_exit
    expect_assertion_error(lambda: spec.process_voluntary_exit(state, signed_voluntary_exit))
    yield 'post', None


@with_gloas_and_later
@spec_state_test
@always_bls
def test_builder_voluntary_exit_invalid_signature(spec, state):
    """Test builder voluntary exit with invalid signature."""
    # Create builder
    builder_index, _ = create_test_builder(spec, state)
    
    # Make builder active
    state.finalized_checkpoint.epoch = spec.Epoch(2)
    assert spec.is_active_builder(state, builder_index)
    
    current_epoch = spec.get_current_epoch(state)
    
    # Create exit with WRONG private key
    validator_index = spec.convert_builder_index_to_validator_index(builder_index)
    voluntary_exit = spec.VoluntaryExit(
        epoch=current_epoch,
        validator_index=validator_index,
    )
    # Sign with wrong key
    signed_voluntary_exit = sign_voluntary_exit(spec, state, voluntary_exit, 12345)
    
    # Should fail due to invalid signature
    yield 'pre', state
    yield 'voluntary_exit', signed_voluntary_exit
    expect_assertion_error(lambda: spec.process_voluntary_exit(state, signed_voluntary_exit))
    yield 'post', None


@with_gloas_and_later
@spec_state_test
def test_builder_voluntary_exit_inactive_builder(spec, state):
    """
    Test that inactive builders cannot exit.
    
    Builder is inactive if deposit_epoch >= finalized checkpoint epoch.
    """
    # Create builder
    builder_index, pubkey = create_test_builder(spec, state)
    privkey = pubkey_to_privkey[pubkey]
    
    # Set deposit epoch to current epoch (NOT finalized)
    current_epoch = spec.get_current_epoch(state)
    state.builders[builder_index].deposit_epoch = current_epoch
    
    # Keep finalized_checkpoint.epoch <= deposit_epoch so builder is NOT active
    state.finalized_checkpoint.epoch = current_epoch
    
    # Verify builder is NOT active
    assert not spec.is_active_builder(state, builder_index)
    
    # Try to exit - should FAIL
    validator_index = spec.convert_builder_index_to_validator_index(builder_index)
    voluntary_exit = spec.VoluntaryExit(
        epoch=current_epoch,
        validator_index=validator_index,
    )
    signed_voluntary_exit = sign_voluntary_exit(spec, state, voluntary_exit, privkey)
    
    # Should fail because builder is not active
    yield 'pre', state
    yield 'voluntary_exit', signed_voluntary_exit
    expect_assertion_error(lambda: spec.process_voluntary_exit(state, signed_voluntary_exit))
    yield 'post', None


@with_gloas_and_later
@spec_state_test
def test_builder_voluntary_exit_already_exited(spec, state):
    """Test that already-exited builders cannot exit again."""
    # Create builder
    builder_index, pubkey = create_test_builder(spec, state)
    privkey = pubkey_to_privkey[pubkey]
    
    # Make builder deposited and finalized, but already exited
    state.finalized_checkpoint.epoch = spec.Epoch(2)
    current_epoch = spec.get_current_epoch(state)
    
    # Mark builder as already exited (withdrawable_epoch != FAR_FUTURE_EPOCH)
    state.builders[builder_index].withdrawable_epoch = current_epoch + 10
    
    # Verify builder is NOT active (already exited)
    assert not spec.is_active_builder(state, builder_index)
    
    # Try to exit again - should FAIL
    validator_index = spec.convert_builder_index_to_validator_index(builder_index)
    voluntary_exit = spec.VoluntaryExit(
        epoch=current_epoch,
        validator_index=validator_index,
    )
    signed_voluntary_exit = sign_voluntary_exit(spec, state, voluntary_exit, privkey)
    
    # Should fail because builder already exited
    yield 'pre', state
    yield 'voluntary_exit', signed_voluntary_exit
    expect_assertion_error(lambda: spec.process_voluntary_exit(state, signed_voluntary_exit))
    yield 'post', None