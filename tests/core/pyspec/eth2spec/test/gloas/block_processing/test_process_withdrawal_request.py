from eth2spec.test.context import spec_state_test, with_gloas_and_later


def prepare_builder_withdrawal_request(
    spec, state, builder_index, source_address=None, amount=None
):
    """
    Create a withdrawal request for a builder.

    If source_address is None, uses the correct address from builder's withdrawal credentials.
    If amount is None, uses FULL_EXIT_REQUEST_AMOUNT (builders only support full exits).
    """
    builder = state.builders[builder_index]

    if source_address is None:
        source_address = builder.withdrawal_credentials[12:]

    if amount is None:
        amount = spec.FULL_EXIT_REQUEST_AMOUNT

    return spec.WithdrawalRequest(
        source_address=source_address,
        validator_pubkey=builder.pubkey,
        amount=amount,
    )


def run_builder_withdrawal_request_processing(spec, state, withdrawal_request, success=True):
    """
    Run ``process_withdrawal_request`` for a builder withdrawal request, yielding:
      - pre-state ('pre')
      - withdrawal_request ('withdrawal_request')
      - post-state ('post').

    Args:
        success: If True, expect the exit to be initiated.
                 If False, expect no changes (no-op).
    """
    builder_pubkeys = [b.pubkey for b in state.builders]
    builder_index = builder_pubkeys.index(withdrawal_request.validator_pubkey)
    pre_withdrawable_epoch = state.builders[builder_index].withdrawable_epoch

    yield "pre", state
    yield "withdrawal_request", withdrawal_request

    pre_state = state.copy()

    spec.process_withdrawal_request(state, withdrawal_request)

    yield "post", state

    if not success:
        # No-op: state should be unchanged
        assert pre_state == state
    else:
        # Exit should have been initiated
        assert pre_withdrawable_epoch == spec.FAR_FUTURE_EPOCH
        builder = state.builders[builder_index]
        assert builder.withdrawable_epoch == (
            spec.get_current_epoch(state) + spec.config.MIN_BUILDER_WITHDRAWABILITY_DELAY
        )


#
# Basic full exit tests
#


@with_gloas_and_later
@spec_state_test
def test_process_withdrawal_request__builder_full_exit(spec, state):
    """Test basic builder full exit request."""
    builder_index = 0
    withdrawal_request = prepare_builder_withdrawal_request(spec, state, builder_index)

    yield from run_builder_withdrawal_request_processing(spec, state, withdrawal_request)


@with_gloas_and_later
@spec_state_test
def test_process_withdrawal_request__builder_full_exit_different_builder(spec, state):
    """Test full exit request for a different builder (not index 0)."""
    builder_index = 3
    withdrawal_request = prepare_builder_withdrawal_request(spec, state, builder_index)

    yield from run_builder_withdrawal_request_processing(spec, state, withdrawal_request)


#
# Failure cases - should return early (no-op)
#


@with_gloas_and_later
@spec_state_test
def test_process_withdrawal_request__builder_incorrect_source_address(spec, state):
    """Test that withdrawal request with incorrect source address is a no-op."""
    builder_index = 0
    incorrect_address = b"\x33" * 20
    withdrawal_request = prepare_builder_withdrawal_request(
        spec, state, builder_index, source_address=incorrect_address
    )

    yield from run_builder_withdrawal_request_processing(
        spec, state, withdrawal_request, success=False
    )


@with_gloas_and_later
@spec_state_test
def test_process_withdrawal_request__builder_exiting(spec, state):
    """Test that withdrawal request for exiting/exited builder is a no-op."""
    builder_index = 0
    # Set withdrawable epoch to something other than FAR_FUTURE_EPOCH
    state.builders[builder_index].withdrawable_epoch = spec.get_current_epoch(state) + 10

    withdrawal_request = prepare_builder_withdrawal_request(spec, state, builder_index)

    yield from run_builder_withdrawal_request_processing(
        spec, state, withdrawal_request, success=False
    )


@with_gloas_and_later
@spec_state_test
def test_process_withdrawal_request__builder_partial_withdrawal_not_supported(spec, state):
    """Test that partial withdrawal requests for builders are a no-op (only full exits supported)."""
    builder_index = 0
    # Use an amount that is not FULL_EXIT_REQUEST_AMOUNT
    partial_amount = spec.Gwei(1 * spec.ETH_TO_GWEI)
    withdrawal_request = prepare_builder_withdrawal_request(
        spec, state, builder_index, amount=partial_amount
    )

    yield from run_builder_withdrawal_request_processing(
        spec, state, withdrawal_request, success=False
    )


@with_gloas_and_later
@spec_state_test
def test_process_withdrawal_request__builder_with_pending_payment(spec, state):
    """Test that builder with pending payment cannot exit."""
    builder_index = 0
    builder = state.builders[builder_index]

    # Add a pending payment for this builder
    fee_recipient = builder.withdrawal_credentials[12:]
    pending_withdrawal = spec.BuilderPendingWithdrawal(
        fee_recipient=fee_recipient,
        amount=spec.Gwei(1 * spec.ETH_TO_GWEI),
        builder_index=builder_index,
    )
    pending_payment = spec.BuilderPendingPayment(
        weight=spec.Gwei(1),
        withdrawal=pending_withdrawal,
    )
    state.builder_pending_payments[0] = pending_payment

    withdrawal_request = prepare_builder_withdrawal_request(spec, state, builder_index)

    yield from run_builder_withdrawal_request_processing(
        spec, state, withdrawal_request, success=False
    )


@with_gloas_and_later
@spec_state_test
def test_process_withdrawal_request__builder_with_pending_withdrawal(spec, state):
    """Test that builder with pending withdrawal cannot exit."""
    builder_index = 0
    builder = state.builders[builder_index]

    # Add a pending withdrawal for this builder
    fee_recipient = builder.withdrawal_credentials[12:]
    pending_withdrawal = spec.BuilderPendingWithdrawal(
        fee_recipient=fee_recipient,
        amount=spec.Gwei(1 * spec.ETH_TO_GWEI),
        builder_index=builder_index,
    )
    state.builder_pending_withdrawals.append(pending_withdrawal)

    withdrawal_request = prepare_builder_withdrawal_request(spec, state, builder_index)

    yield from run_builder_withdrawal_request_processing(
        spec, state, withdrawal_request, success=False
    )


@with_gloas_and_later
@spec_state_test
def test_process_withdrawal_request__builder_unknown_pubkey(spec, state):
    """Test that withdrawal request with unknown pubkey is a no-op."""
    # Create a withdrawal request with a pubkey that doesn't exist
    unknown_pubkey = spec.BLSPubkey(b"\x99" * 48)
    withdrawal_request = spec.WithdrawalRequest(
        source_address=b"\x22" * 20,
        validator_pubkey=unknown_pubkey,
        amount=spec.FULL_EXIT_REQUEST_AMOUNT,
    )

    pre_state = state.copy()

    yield "pre", state
    yield "withdrawal_request", withdrawal_request

    spec.process_withdrawal_request(state, withdrawal_request)

    yield "post", state

    # State should be unchanged
    assert pre_state == state


#
# Queue full edge case
#


@with_gloas_and_later
@spec_state_test
def test_process_withdrawal_request__builder_full_exit_with_queue_full(spec, state):
    """Test that builder full exit still works even when partial withdrawal queue is full."""
    builder_index = 0

    # Fill the partial withdrawal queue to the max
    partial_withdrawal = spec.PendingPartialWithdrawal(
        validator_index=1, amount=1, withdrawable_epoch=spec.get_current_epoch(state)
    )
    state.pending_partial_withdrawals = [
        partial_withdrawal
    ] * spec.PENDING_PARTIAL_WITHDRAWALS_LIMIT

    withdrawal_request = prepare_builder_withdrawal_request(spec, state, builder_index)

    # Full exit should still succeed
    yield from run_builder_withdrawal_request_processing(spec, state, withdrawal_request)
