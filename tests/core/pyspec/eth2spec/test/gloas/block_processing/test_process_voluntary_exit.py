from eth2spec.test.context import (
    always_bls,
    expect_assertion_error,
    spec_state_test,
    with_gloas_and_later,
)
from eth2spec.test.helpers.keys import pubkey_to_privkey
from eth2spec.test.helpers.voluntary_exits import sign_voluntary_exit


def create_test_builder(spec, state, balance=None):
    """Helper to add a builder to state for testing."""
    if balance is None:
        balance = spec.MIN_DEPOSIT_AMOUNT + spec.MIN_ACTIVATION_BALANCE

    # Use validator 0's pubkey (exists in pubkey_to_privkey for signing)
    if len(state.validators) > 0:
        pubkey = state.validators[0].pubkey
    else:
        pubkey = spec.BLSPubkey(b"\x42" * 48)

    builder = spec.Builder(
        pubkey=pubkey,
        version=3,
        execution_address=spec.ExecutionAddress(b"\x50" * 20),
        balance=balance,
        deposit_epoch=0,
        withdrawable_epoch=spec.FAR_FUTURE_EPOCH,
    )
    state.builders.append(builder)
    return len(state.builders) - 1, pubkey


@with_gloas_and_later
@spec_state_test
def test_builder_voluntary_exit_success(spec, state):
    """Test successful builder voluntary exit with no pending balance."""
    # Create builder
    builder_index, pubkey = create_test_builder(spec, state)
    privkey = pubkey_to_privkey[pubkey]

    # Manually set finalized checkpoint to make builder active
    state.finalized_checkpoint.epoch = spec.Epoch(2)

    assert spec.is_active_builder(state, builder_index), (
        f"Builder not active: deposit={state.builders[builder_index].deposit_epoch}, finalized={state.finalized_checkpoint.epoch}"
    )

    assert spec.get_pending_balance_to_withdraw_for_builder(state, builder_index) == 0

    current_epoch = spec.get_current_epoch(state)

    validator_index = spec.convert_builder_index_to_validator_index(builder_index)
    voluntary_exit = spec.VoluntaryExit(
        epoch=current_epoch,
        validator_index=validator_index,
    )
    signed_voluntary_exit = sign_voluntary_exit(spec, state, voluntary_exit, privkey)

    yield "pre", state
    spec.process_voluntary_exit(state, signed_voluntary_exit)
    yield "post", state

    assert not spec.is_active_builder(state, builder_index)

    expected_withdrawable = current_epoch + spec.config.MIN_BUILDER_WITHDRAWABILITY_DELAY
    assert state.builders[builder_index].withdrawable_epoch == expected_withdrawable


@with_gloas_and_later
@spec_state_test
def test_builder_voluntary_exit_with_pending_payment(spec, state):
    """Test that builder cannot exit while having pending payment."""
    # Create builder
    builder_index, pubkey = create_test_builder(spec, state)
    privkey = pubkey_to_privkey[pubkey]

    state.finalized_checkpoint.epoch = spec.Epoch(2)
    assert spec.is_active_builder(state, builder_index)

    # Add pending payment for this builder
    payment_amount = spec.MIN_ACTIVATION_BALANCE
    payment = spec.BuilderPendingPayment(
        weight=spec.get_builder_payment_quorum_threshold(state) + 1,
        withdrawal=spec.BuilderPendingWithdrawal(
            fee_recipient=spec.ExecutionAddress(b"\x60" * 20),
            amount=payment_amount,
            builder_index=builder_index,
        ),
    )
    state.builder_pending_payments[0] = payment

    pending_balance = spec.get_pending_balance_to_withdraw_for_builder(state, builder_index)
    assert pending_balance == payment_amount

    current_epoch = spec.get_current_epoch(state)

    validator_index = spec.convert_builder_index_to_validator_index(builder_index)
    voluntary_exit = spec.VoluntaryExit(
        epoch=current_epoch,
        validator_index=validator_index,
    )
    signed_voluntary_exit = sign_voluntary_exit(spec, state, voluntary_exit, privkey)

    yield "pre", state
    yield "voluntary_exit", signed_voluntary_exit
    expect_assertion_error(lambda: spec.process_voluntary_exit(state, signed_voluntary_exit))
    yield "post", None


@with_gloas_and_later
@spec_state_test
def test_builder_voluntary_exit_with_pending_withdrawal(spec, state):
    """Test that builder cannot exit while having pending withdrawal."""
    # Create builder
    builder_index, pubkey = create_test_builder(spec, state)
    privkey = pubkey_to_privkey[pubkey]

    state.finalized_checkpoint.epoch = spec.Epoch(2)
    assert spec.is_active_builder(state, builder_index)

    withdrawal_amount = spec.MIN_ACTIVATION_BALANCE
    withdrawal = spec.BuilderPendingWithdrawal(
        fee_recipient=spec.ExecutionAddress(b"\x70" * 20),
        amount=withdrawal_amount,
        builder_index=builder_index,
    )
    state.builder_pending_withdrawals.append(withdrawal)

    pending_balance = spec.get_pending_balance_to_withdraw_for_builder(state, builder_index)
    assert pending_balance == withdrawal_amount

    current_epoch = spec.get_current_epoch(state)

    validator_index = spec.convert_builder_index_to_validator_index(builder_index)
    voluntary_exit = spec.VoluntaryExit(
        epoch=current_epoch,
        validator_index=validator_index,
    )
    signed_voluntary_exit = sign_voluntary_exit(spec, state, voluntary_exit, privkey)

    yield "pre", state
    yield "voluntary_exit", signed_voluntary_exit
    expect_assertion_error(lambda: spec.process_voluntary_exit(state, signed_voluntary_exit))
    yield "post", None


@with_gloas_and_later
@spec_state_test
@always_bls
def test_builder_voluntary_exit_invalid_signature(spec, state):
    """Test builder voluntary exit with invalid signature."""
    # Create builder
    builder_index, _ = create_test_builder(spec, state)

    state.finalized_checkpoint.epoch = spec.Epoch(2)
    assert spec.is_active_builder(state, builder_index)

    current_epoch = spec.get_current_epoch(state)

    validator_index = spec.convert_builder_index_to_validator_index(builder_index)
    voluntary_exit = spec.VoluntaryExit(
        epoch=current_epoch,
        validator_index=validator_index,
    )
    signed_voluntary_exit = sign_voluntary_exit(spec, state, voluntary_exit, 12345)

    yield "pre", state
    yield "voluntary_exit", signed_voluntary_exit
    expect_assertion_error(lambda: spec.process_voluntary_exit(state, signed_voluntary_exit))
    yield "post", None


@with_gloas_and_later
@spec_state_test
def test_builder_voluntary_exit_inactive_builder(spec, state):
    """Test that inactive builders cannot exit."""
    # Create builder
    builder_index, pubkey = create_test_builder(spec, state)
    privkey = pubkey_to_privkey[pubkey]

    current_epoch = spec.get_current_epoch(state)
    state.builders[builder_index].deposit_epoch = current_epoch

    state.finalized_checkpoint.epoch = current_epoch

    assert not spec.is_active_builder(state, builder_index)

    validator_index = spec.convert_builder_index_to_validator_index(builder_index)
    voluntary_exit = spec.VoluntaryExit(
        epoch=current_epoch,
        validator_index=validator_index,
    )
    signed_voluntary_exit = sign_voluntary_exit(spec, state, voluntary_exit, privkey)

    yield "pre", state
    yield "voluntary_exit", signed_voluntary_exit
    expect_assertion_error(lambda: spec.process_voluntary_exit(state, signed_voluntary_exit))
    yield "post", None


@with_gloas_and_later
@spec_state_test
def test_builder_voluntary_exit_already_exited(spec, state):
    """Test that already-exited builders cannot exit again."""
    # Create builder
    builder_index, pubkey = create_test_builder(spec, state)
    privkey = pubkey_to_privkey[pubkey]

    state.finalized_checkpoint.epoch = spec.Epoch(2)
    current_epoch = spec.get_current_epoch(state)

    state.builders[builder_index].withdrawable_epoch = current_epoch + 10

    assert not spec.is_active_builder(state, builder_index)

    validator_index = spec.convert_builder_index_to_validator_index(builder_index)
    voluntary_exit = spec.VoluntaryExit(
        epoch=current_epoch,
        validator_index=validator_index,
    )
    signed_voluntary_exit = sign_voluntary_exit(spec, state, voluntary_exit, privkey)

    yield "pre", state
    yield "voluntary_exit", signed_voluntary_exit
    expect_assertion_error(lambda: spec.process_voluntary_exit(state, signed_voluntary_exit))
    yield "post", None
