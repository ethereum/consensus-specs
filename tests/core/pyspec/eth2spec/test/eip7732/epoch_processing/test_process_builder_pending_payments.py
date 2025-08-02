from eth2spec.test.context import (
    spec_state_test,
    with_eip7732_and_later,
)
from eth2spec.test.helpers.epoch_processing import run_epoch_processing_with
from eth2spec.test.helpers.state import next_epoch


def create_builder_pending_payment(spec, builder_index, amount, weight=0, fee_recipient=None):
    """Create a BuilderPendingPayment for testing."""
    if fee_recipient is None:
        fee_recipient = spec.ExecutionAddress()

    return spec.BuilderPendingPayment(
        weight=weight,
        withdrawal=spec.BuilderPendingWithdrawal(
            fee_recipient=fee_recipient,
            amount=amount,
            builder_index=builder_index,
            withdrawable_epoch=spec.FAR_FUTURE_EPOCH,
        ),
    )


def get_quorum_threshold(spec, state):
    """Calculate the quorum threshold for builder payments."""
    return spec.get_builder_payment_quorum_threshold(state)


@with_eip7732_and_later
@spec_state_test
def test_process_builder_pending_payments_empty_queue(spec, state):
    """Test processing with no pending payments."""
    # Advance past genesis epochs
    next_epoch(spec, state)
    next_epoch(spec, state)

    # Populate the first SLOTS_PER_EPOCH with payments to ensure they're not empty
    for i in range(spec.SLOTS_PER_EPOCH):
        payment = create_builder_pending_payment(spec, i, spec.MIN_ACTIVATION_BALANCE, 1)
        state.builder_pending_payments[i] = payment

    pre_builder_pending_withdrawals = len(state.builder_pending_withdrawals)

    yield from run_epoch_processing_with(spec, state, "process_builder_pending_payments")

    # No withdrawals should be added
    assert len(state.builder_pending_withdrawals) == pre_builder_pending_withdrawals

    # Queue should be rotated - first SLOTS_PER_EPOCH should be empty
    for i in range(spec.SLOTS_PER_EPOCH):
        payment = state.builder_pending_payments[i]
        assert payment.weight == 0
        assert payment.withdrawal.amount == 0
        assert payment.withdrawal.builder_index == 0


@with_eip7732_and_later
@spec_state_test
def test_process_builder_pending_payments_below_quorum(spec, state):
    """Test payment below quorum threshold - should not be processed."""
    # Advance past genesis epochs
    next_epoch(spec, state)
    next_epoch(spec, state)

    builder_index = 0
    amount = spec.MIN_ACTIVATION_BALANCE
    quorum = get_quorum_threshold(spec, state)
    weight = quorum // 2  # Below threshold

    # Add pending payment with weight below quorum
    payment = create_builder_pending_payment(spec, builder_index, amount, weight)
    state.builder_pending_payments[0] = payment

    pre_builder_pending_withdrawals = len(state.builder_pending_withdrawals)

    yield from run_epoch_processing_with(spec, state, "process_builder_pending_payments")

    # No withdrawal should be added since weight is below quorum
    assert len(state.builder_pending_withdrawals) == pre_builder_pending_withdrawals

    # Payment should be rotated out of the first SLOTS_PER_EPOCH
    assert state.builder_pending_payments[0].weight == 0


@with_eip7732_and_later
@spec_state_test
def test_process_builder_pending_payments_above_quorum(spec, state):
    """Test payment above quorum threshold - should be processed."""
    # Advance past genesis epochs
    next_epoch(spec, state)
    next_epoch(spec, state)

    builder_index = 0
    amount = spec.MIN_ACTIVATION_BALANCE
    quorum = get_quorum_threshold(spec, state)
    weight = quorum + 1  # Above threshold
    fee_recipient = b"\x42" * 20

    # Add pending payment with weight above quorum
    payment = create_builder_pending_payment(spec, builder_index, amount, weight, fee_recipient)
    state.builder_pending_payments[0] = payment

    pre_builder_pending_withdrawals = len(state.builder_pending_withdrawals)

    yield from run_epoch_processing_with(spec, state, "process_builder_pending_payments")

    # One withdrawal should be added
    assert len(state.builder_pending_withdrawals) == pre_builder_pending_withdrawals + 1

    # Check the withdrawal details
    if len(state.builder_pending_withdrawals) > 0:
        withdrawal = state.builder_pending_withdrawals[len(state.builder_pending_withdrawals) - 1]
    else:
        assert False, "No withdrawals were added despite payment being above quorum"
    assert withdrawal.fee_recipient == fee_recipient
    assert withdrawal.amount == amount
    assert withdrawal.builder_index == builder_index
    assert withdrawal.withdrawable_epoch > spec.get_current_epoch(state)

    # Payment should be rotated out
    assert state.builder_pending_payments[0].weight == 0


@with_eip7732_and_later
@spec_state_test
def test_process_builder_pending_payments_multiple_above_quorum(spec, state):
    """Test multiple payments above quorum threshold."""
    # Advance past genesis epochs
    next_epoch(spec, state)
    next_epoch(spec, state)

    quorum = get_quorum_threshold(spec, state)
    weight = quorum + 1

    # Add multiple payments above quorum
    num_payments = min(3, spec.SLOTS_PER_EPOCH)
    for i in range(num_payments):
        builder_index = i
        amount = spec.MIN_ACTIVATION_BALANCE + i * spec.EFFECTIVE_BALANCE_INCREMENT
        fee_recipient = bytes([0x10 + i]) + b"\x00" * 19

        payment = create_builder_pending_payment(spec, builder_index, amount, weight, fee_recipient)
        state.builder_pending_payments[i] = payment

    pre_builder_pending_withdrawals = len(state.builder_pending_withdrawals)

    yield from run_epoch_processing_with(spec, state, "process_builder_pending_payments")

    # All payments should result in withdrawals
    assert len(state.builder_pending_withdrawals) == pre_builder_pending_withdrawals + num_payments

    # Check each withdrawal
    for i in range(num_payments):
        withdrawal = state.builder_pending_withdrawals[pre_builder_pending_withdrawals + i]
        expected_amount = spec.MIN_ACTIVATION_BALANCE + i * spec.EFFECTIVE_BALANCE_INCREMENT
        expected_fee_recipient = bytes([0x10 + i]) + b"\x00" * 19

        assert withdrawal.amount == expected_amount
        assert withdrawal.builder_index == i
        assert withdrawal.fee_recipient == expected_fee_recipient
        assert withdrawal.withdrawable_epoch > spec.get_current_epoch(state)


@with_eip7732_and_later
@spec_state_test
def test_process_builder_pending_payments_mixed_weights(spec, state):
    """Test mix of payments above and below quorum."""
    # Advance past genesis epochs
    next_epoch(spec, state)
    next_epoch(spec, state)

    quorum = get_quorum_threshold(spec, state)

    # Add payments with different weights
    payments_data = [
        (0, spec.MIN_ACTIVATION_BALANCE, quorum + 1),  # Above threshold
        (1, spec.MIN_ACTIVATION_BALANCE, quorum // 2),  # Below threshold
        (2, spec.MIN_ACTIVATION_BALANCE, quorum + 100),  # Above threshold
        (3, spec.MIN_ACTIVATION_BALANCE, quorum - 1),  # Below threshold
    ]

    for i, (builder_index, amount, weight) in enumerate(payments_data):
        if i >= spec.SLOTS_PER_EPOCH:
            break
        payment = create_builder_pending_payment(spec, builder_index, amount, weight)
        state.builder_pending_payments[i] = payment

    pre_builder_pending_withdrawals = len(state.builder_pending_withdrawals)

    yield from run_epoch_processing_with(spec, state, "process_builder_pending_payments")

    # Only payments with weight > quorum should be processed (indices 0 and 2)
    expected_processed = 2
    assert (
        len(state.builder_pending_withdrawals)
        == pre_builder_pending_withdrawals + expected_processed
    )

    # Check the processed withdrawals
    processed_withdrawals = state.builder_pending_withdrawals[pre_builder_pending_withdrawals:]
    processed_builder_indices = [w.builder_index for w in processed_withdrawals]
    assert 0 in processed_builder_indices
    assert 2 in processed_builder_indices
    assert 1 not in processed_builder_indices
    assert 3 not in processed_builder_indices


@with_eip7732_and_later
@spec_state_test
def test_process_builder_pending_payments_queue_rotation(spec, state):
    """Test that the payment queue is properly rotated after processing."""
    # Advance past genesis epochs
    next_epoch(spec, state)
    next_epoch(spec, state)

    # Fill both epochs of the queue with test data
    test_weight = 12345
    for i in range(2 * spec.SLOTS_PER_EPOCH):
        payment = create_builder_pending_payment(spec, i, spec.MIN_ACTIVATION_BALANCE, test_weight)
        state.builder_pending_payments[i] = payment

    # Store the second epoch data for comparison
    second_epoch_payments = []
    for i in range(spec.SLOTS_PER_EPOCH, 2 * spec.SLOTS_PER_EPOCH):
        payment = state.builder_pending_payments[i]
        second_epoch_payments.append((payment.weight, payment.withdrawal.builder_index))

    yield from run_epoch_processing_with(spec, state, "process_builder_pending_payments")

    # First SLOTS_PER_EPOCH should be the old second epoch
    for i in range(spec.SLOTS_PER_EPOCH):
        payment = state.builder_pending_payments[i]
        expected_weight, expected_builder_index = second_epoch_payments[i]
        assert payment.weight == expected_weight
        assert payment.withdrawal.builder_index == expected_builder_index

    # Second SLOTS_PER_EPOCH should be empty
    for i in range(spec.SLOTS_PER_EPOCH, 2 * spec.SLOTS_PER_EPOCH):
        payment = state.builder_pending_payments[i]
        assert payment.weight == 0
        assert payment.withdrawal.amount == 0
        assert payment.withdrawal.builder_index == 0


@with_eip7732_and_later
@spec_state_test
def test_process_builder_pending_payments_large_amount_churn_impact(spec, state):
    """Test that large payment amounts impact the exit churn correctly."""
    # Advance past genesis epochs
    next_epoch(spec, state)
    next_epoch(spec, state)

    builder_index = 0
    large_amount = spec.MAX_EFFECTIVE_BALANCE_ELECTRA
    quorum = get_quorum_threshold(spec, state)
    weight = quorum + 1

    payment = create_builder_pending_payment(spec, builder_index, large_amount, weight)
    state.builder_pending_payments[0] = payment

    pre_exit_balance_to_consume = state.exit_balance_to_consume
    pre_earliest_exit_epoch = state.earliest_exit_epoch

    yield from run_epoch_processing_with(spec, state, "process_builder_pending_payments")

    # Should have one withdrawal
    assert len(state.builder_pending_withdrawals) >= 1
    withdrawal = state.builder_pending_withdrawals[len(state.builder_pending_withdrawals) - 1]
    assert withdrawal.amount == large_amount

    # Exit queue should be impacted by large amount processing
    # Check that either balance was consumed or exit epoch was impacted
    assert (
        state.exit_balance_to_consume != pre_exit_balance_to_consume
        or state.earliest_exit_epoch != pre_earliest_exit_epoch
    )

    # Withdrawable epoch should account for the large amount
    current_epoch = spec.get_current_epoch(state)
    assert withdrawal.withdrawable_epoch > current_epoch
