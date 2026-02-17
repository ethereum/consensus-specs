from eth_consensus_specs.test.context import (
    always_bls,
    expect_assertion_error,
    spec_state_test,
    with_gloas_and_later,
)
from eth_consensus_specs.test.helpers.keys import builder_pubkey_to_privkey
from eth_consensus_specs.test.helpers.state import next_slots
from eth_consensus_specs.test.helpers.voluntary_exits import sign_voluntary_exit


def advance_past_finalization(spec, state):
    """Advance slots and finalize so that genesis-epoch builders become active."""
    epoch = spec.get_current_epoch(state)
    next_slots(spec, state, spec.SLOTS_PER_EPOCH * 3)
    state.finalized_checkpoint.epoch = epoch + 1


@with_gloas_and_later
@spec_state_test
def test_builder_voluntary_exit__success(spec, state):
    """Test successful builder voluntary exit with no pending balance."""
    builder_index = 0
    pubkey = state.builders[builder_index].pubkey
    privkey = builder_pubkey_to_privkey[pubkey]

    advance_past_finalization(spec, state)
    assert spec.is_active_builder(state, builder_index)

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
def test_builder_voluntary_exit__invalid__inactive_deposit_epoch(spec, state):
    """Test that inactive builders cannot exit."""
    builder_index = 0
    pubkey = state.builders[builder_index].pubkey
    privkey = builder_pubkey_to_privkey[pubkey]

    # Set builder's deposit epoch to a non-finalized epoch
    state.builders[builder_index].deposit_epoch = spec.Epoch(1)

    advance_past_finalization(spec, state)
    assert state.finalized_checkpoint.epoch == state.builders[builder_index].deposit_epoch
    assert not spec.is_active_builder(state, builder_index)

    validator_index = spec.convert_builder_index_to_validator_index(builder_index)
    voluntary_exit = spec.VoluntaryExit(
        epoch=spec.get_current_epoch(state),
        validator_index=validator_index,
    )
    signed_voluntary_exit = sign_voluntary_exit(spec, state, voluntary_exit, privkey)

    yield "pre", state
    yield "voluntary_exit", signed_voluntary_exit
    expect_assertion_error(lambda: spec.process_voluntary_exit(state, signed_voluntary_exit))
    yield "post", None


@with_gloas_and_later
@spec_state_test
def test_builder_voluntary_exit__invalid__inactive_already_exited(spec, state):
    """Test that already-exited builders cannot exit again."""
    builder_index = 0
    pubkey = state.builders[builder_index].pubkey
    privkey = builder_pubkey_to_privkey[pubkey]

    # Set builder's withdrawable epoch which indicates it has initiated an exit
    state.builders[builder_index].withdrawable_epoch = spec.get_current_epoch(state) + 10

    advance_past_finalization(spec, state)
    assert not spec.is_active_builder(state, builder_index)

    validator_index = spec.convert_builder_index_to_validator_index(builder_index)
    voluntary_exit = spec.VoluntaryExit(
        epoch=spec.get_current_epoch(state),
        validator_index=validator_index,
    )
    signed_voluntary_exit = sign_voluntary_exit(spec, state, voluntary_exit, privkey)

    yield "pre", state
    yield "voluntary_exit", signed_voluntary_exit
    expect_assertion_error(lambda: spec.process_voluntary_exit(state, signed_voluntary_exit))
    yield "post", None


@with_gloas_and_later
@spec_state_test
def test_builder_voluntary_exit__invalid__pending_withdrawal(spec, state):
    """Test that builder cannot exit while having pending withdrawal."""
    builder_index = 0
    pubkey = state.builders[builder_index].pubkey
    privkey = builder_pubkey_to_privkey[pubkey]

    advance_past_finalization(spec, state)
    assert spec.is_active_builder(state, builder_index)

    # Add pending withdrawal for this builder
    withdrawal_amount = spec.MIN_ACTIVATION_BALANCE
    withdrawal = spec.BuilderPendingWithdrawal(
        fee_recipient=spec.ExecutionAddress(b"\x70" * 20),
        amount=withdrawal_amount,
        builder_index=builder_index,
    )
    state.builder_pending_withdrawals.append(withdrawal)
    pending_balance = spec.get_pending_balance_to_withdraw_for_builder(state, builder_index)
    assert pending_balance == withdrawal_amount

    validator_index = spec.convert_builder_index_to_validator_index(builder_index)
    voluntary_exit = spec.VoluntaryExit(
        epoch=spec.get_current_epoch(state),
        validator_index=validator_index,
    )
    signed_voluntary_exit = sign_voluntary_exit(spec, state, voluntary_exit, privkey)

    yield "pre", state
    yield "voluntary_exit", signed_voluntary_exit
    expect_assertion_error(lambda: spec.process_voluntary_exit(state, signed_voluntary_exit))
    yield "post", None


@with_gloas_and_later
@spec_state_test
def test_builder_voluntary_exit__invalid__pending_payment(spec, state):
    """Test that builder cannot exit while having pending payment."""
    builder_index = 0
    pubkey = state.builders[builder_index].pubkey
    privkey = builder_pubkey_to_privkey[pubkey]

    advance_past_finalization(spec, state)
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

    validator_index = spec.convert_builder_index_to_validator_index(builder_index)
    voluntary_exit = spec.VoluntaryExit(
        epoch=spec.get_current_epoch(state),
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
def test_builder_voluntary_exit__invalid__bad_signature(spec, state):
    """Test builder voluntary exit with invalid signature."""
    builder_index = 0

    advance_past_finalization(spec, state)
    assert spec.is_active_builder(state, builder_index)

    validator_index = spec.convert_builder_index_to_validator_index(builder_index)
    voluntary_exit = spec.VoluntaryExit(
        epoch=spec.get_current_epoch(state),
        validator_index=validator_index,
    )
    # Use the wrong privkey so the signature is invalid
    signed_voluntary_exit = sign_voluntary_exit(spec, state, voluntary_exit, 12345)

    yield "pre", state
    yield "voluntary_exit", signed_voluntary_exit
    expect_assertion_error(lambda: spec.process_voluntary_exit(state, signed_voluntary_exit))
    yield "post", None
