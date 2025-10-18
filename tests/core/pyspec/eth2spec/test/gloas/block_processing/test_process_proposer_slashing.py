import random

from eth2spec.test.context import (
    spec_state_test,
    with_gloas_and_later,
)
from eth2spec.test.gloas.epoch_processing.test_process_builder_pending_payments import (
    create_builder_pending_payment,
)
from eth2spec.test.helpers.proposer_slashings import (
    get_valid_proposer_slashing,
)
from eth2spec.test.helpers.state import next_epoch
from eth2spec.test.phase0.block_processing.test_process_proposer_slashing import (
    run_proposer_slashing_processing,
)


@with_gloas_and_later
@spec_state_test
def test_builder_payment_deletion_current_epoch(spec, state):
    """Test that builder pending payment is deleted when proposer is slashed in the same epoch as the proposal."""
    random.seed(1234)
    # Advance past genesis epochs
    next_epoch(spec, state)
    next_epoch(spec, state)
    slashed_slot = state.slot + random.randrange(spec.SLOTS_PER_EPOCH)

    # Create a proposer slashing for the current slot
    proposer_slashing = get_valid_proposer_slashing(
        spec, state, slot=slashed_slot, signed_1=True, signed_2=True
    )
    slashed_proposer_index = proposer_slashing.signed_header_1.message.proposer_index

    # Verify the slashing is for the current epoch
    assert spec.compute_epoch_at_slot(slashed_slot) == spec.get_current_epoch(state)

    # Add a builder pending payment for the slashed proposer in the current epoch
    payment_amount = spec.MIN_ACTIVATION_BALANCE
    payment_weight = 1000
    fee_recipient = b"\x42" * 20

    payment = create_builder_pending_payment(
        spec, slashed_proposer_index, payment_amount, payment_weight, fee_recipient
    )
    # Place in current epoch slot (SLOTS_PER_EPOCH + slot % SLOTS_PER_EPOCH)
    slashed_slot_index = spec.SLOTS_PER_EPOCH + slashed_slot % spec.SLOTS_PER_EPOCH
    state.builder_pending_payments[slashed_slot_index] = payment

    yield from run_proposer_slashing_processing(spec, state, proposer_slashing)
    # Verify the payment has been deleted (replaced with empty payment)
    assert state.builder_pending_payments[slashed_slot_index] == spec.BuilderPendingPayment()


@with_gloas_and_later
@spec_state_test
def test_builder_payment_deletion_previous_epoch(spec, state):
    """Test that builder pending payment is deleted when proposer is slashed in the epoch after the proposal."""
    random.seed(5678)
    # Advance past genesis epochs
    next_epoch(spec, state)
    next_epoch(spec, state)
    slashed_slot = state.slot + random.randrange(spec.SLOTS_PER_EPOCH)
    next_epoch(spec, state)

    proposer_slashing = get_valid_proposer_slashing(
        spec, state, slot=slashed_slot, signed_1=True, signed_2=True
    )
    slashed_proposer_index = proposer_slashing.signed_header_1.message.proposer_index

    # Verify the slashing is for the previous epoch
    assert spec.compute_epoch_at_slot(slashed_slot) == spec.get_previous_epoch(state)

    # Add a builder pending payment for the slashed proposer in the previous epoch
    payment_amount = spec.MIN_ACTIVATION_BALANCE
    payment_weight = 1000
    fee_recipient = b"\x43" * 20

    payment = create_builder_pending_payment(
        spec, slashed_proposer_index, payment_amount, payment_weight, fee_recipient
    )
    # Place in previous epoch slot (slot % SLOTS_PER_EPOCH)
    slashed_slot_index = slashed_slot % spec.SLOTS_PER_EPOCH
    state.builder_pending_payments[slashed_slot_index] = payment

    yield from run_proposer_slashing_processing(spec, state, proposer_slashing)

    # Verify the payment has been deleted (replaced with empty payment)
    assert state.builder_pending_payments[slashed_slot_index] == spec.BuilderPendingPayment()


@with_gloas_and_later
@spec_state_test
def test_builder_payment_deletion_too_late(spec, state):
    """Test that builder pending payment is NOT deleted when slashing comes more than two epochs after the proposal slot."""
    random.seed(9012)
    # Advance past genesis epochs
    next_epoch(spec, state)
    next_epoch(spec, state)
    slashed_slot = state.slot + random.randrange(spec.SLOTS_PER_EPOCH)
    next_epoch(spec, state)
    next_epoch(spec, state)

    proposer_slashing = get_valid_proposer_slashing(
        spec, state, slot=slashed_slot, signed_1=True, signed_2=True
    )

    builder_pending_payments = state.builder_pending_payments

    yield from run_proposer_slashing_processing(spec, state, proposer_slashing)

    # Verify that the payments are unmodified
    assert state.builder_pending_payments == builder_pending_payments
