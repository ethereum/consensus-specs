import random

from eth_consensus_specs.test.context import (
    spec_state_test,
    with_gloas_and_later,
)
from tests.infra.helpers.proposer_slashings import (
    assert_process_proposer_slashing,
    prepare_process_proposer_slashing,
    run_proposer_slashing_processing,
)


@with_gloas_and_later
@spec_state_test
def test_builder_payment_deletion_current_epoch(spec, state):
    """
    Test that builder pending payment is deleted when proposer is slashed in the same epoch as the proposal.

    Input State Configured:
        - state advanced by 2 epochs
        - proposer_slashing: Valid slashing with different parent_root values
        - proposer_slashing.signed_header_1.message.slot: In current epoch
        - builder_pending_payments: Contains entry for slashed proposer with amount = MIN_ACTIVATION_BALANCE

    Output State Verified:
        - validators[slashed_index].slashed: True
        - builder_pending_payments: Entry for slashed proposer removed (slashing within 2-epoch window)
    """
    proposer_slashing, _ = prepare_process_proposer_slashing(
        spec,
        state,
        advance_epochs=2,
        slot_offset=random.randrange(spec.SLOTS_PER_EPOCH),
        parent_root_2=b"\x99" * 32,  # Make headers different
        builder_payment_amount=spec.MIN_ACTIVATION_BALANCE,
        builder_payment_fee_recipient=b"\x42" * 20,
        builder_payment_weight=1000,
    )

    # Verify the slashing is for the current epoch
    slashed_slot = proposer_slashing.signed_header_1.message.slot
    assert spec.compute_epoch_at_slot(slashed_slot) == spec.get_current_epoch(state)

    pre_state = state.copy()

    yield from run_proposer_slashing_processing(spec, state, proposer_slashing)

    assert_process_proposer_slashing(
        spec,
        state,
        pre_state,
        proposer_slashing,
    )


@with_gloas_and_later
@spec_state_test
def test_builder_payment_deletion_previous_epoch(spec, state):
    """
    Test that builder pending payment is deleted when proposer is slashed in the epoch after the proposal.

    Input State Configured:
        - state advanced by 2 epochs, then 1 additional epoch after slashing setup
        - proposer_slashing: Valid slashing with different parent_root values
        - proposer_slashing.signed_header_1.message.slot: In previous epoch
        - builder_pending_payments: Contains entry for slashed proposer with amount = MIN_ACTIVATION_BALANCE

    Output State Verified:
        - validators[slashed_index].slashed: True
        - builder_pending_payments: Entry for slashed proposer removed (slashing within 2-epoch window)
    """
    proposer_slashing, _ = prepare_process_proposer_slashing(
        spec,
        state,
        advance_epochs=2,
        advance_epochs_after=1,  # Slot will be in previous epoch
        slot_offset=random.randrange(spec.SLOTS_PER_EPOCH),
        parent_root_2=b"\x99" * 32,  # Make headers different
        builder_payment_amount=spec.MIN_ACTIVATION_BALANCE,
        builder_payment_fee_recipient=b"\x43" * 20,
        builder_payment_weight=1000,
    )

    # Verify the slashing is for the previous epoch
    slashed_slot = proposer_slashing.signed_header_1.message.slot
    assert spec.compute_epoch_at_slot(slashed_slot) == spec.get_previous_epoch(state)

    pre_state = state.copy()

    yield from run_proposer_slashing_processing(spec, state, proposer_slashing)

    assert_process_proposer_slashing(
        spec,
        state,
        pre_state,
        proposer_slashing,
    )


@with_gloas_and_later
@spec_state_test
def test_builder_payment_deletion_too_late(spec, state):
    """
    Test that builder pending payment is NOT deleted when slashing comes more than two epochs after the proposal slot.

    Input State Configured:
        - state advanced by 2 epochs, then 2 additional epochs after slashing setup
        - proposer_slashing: Valid slashing with different parent_root values
        - proposer_slashing.signed_header_1.message.slot: More than 2 epochs before current epoch

    Output State Verified:
        - validators[slashed_index].slashed: True
        - builder_pending_payments: Unchanged (slashing outside 2-epoch window, no payment deletion)
    """
    proposer_slashing, _ = prepare_process_proposer_slashing(
        spec,
        state,
        advance_epochs=2,
        advance_epochs_after=2,  # Slot will be outside 2-epoch window
        slot_offset=random.randrange(spec.SLOTS_PER_EPOCH),
        parent_root_2=b"\x99" * 32,  # Make headers different
        builder_payment_amount=spec.MIN_ACTIVATION_BALANCE,
        builder_payment_fee_recipient=b"\x46" * 20,
        builder_payment_weight=1000,
    )

    pre_state = state.copy()

    yield from run_proposer_slashing_processing(spec, state, proposer_slashing)

    # Verify standard slashing effects and that payments are unmodified
    assert_process_proposer_slashing(
        spec,
        state,
        pre_state,
        proposer_slashing,
    )


@with_gloas_and_later
@spec_state_test
def test_builder_payment_empty_current_epoch(spec, state):
    """
    Test slashing succeeds when no builder payment exists at current epoch slot.

    Input State Configured:
        - state advanced by 2 epochs
        - proposer_slashing: Valid slashing with different parent_root values
        - proposer_slashing.signed_header_1.message.slot: In current epoch
        - builder_pending_payments: No entry set (empty slot)

    Output State Verified:
        - validators[slashed_index].slashed: True
        - builder_pending_payments: Remains empty (no change)
    """
    proposer_slashing, _ = prepare_process_proposer_slashing(
        spec,
        state,
        advance_epochs=2,
        slot_offset=random.randrange(spec.SLOTS_PER_EPOCH),
        parent_root_2=b"\x99" * 32,
        # No builder_payment_amount - payment slot stays empty
    )

    slashed_slot = proposer_slashing.signed_header_1.message.slot
    assert spec.compute_epoch_at_slot(slashed_slot) == spec.get_current_epoch(state)

    pre_state = state.copy()

    yield from run_proposer_slashing_processing(spec, state, proposer_slashing)

    assert_process_proposer_slashing(
        spec,
        state,
        pre_state,
        proposer_slashing,
    )


@with_gloas_and_later
@spec_state_test
def test_builder_payment_empty_previous_epoch(spec, state):
    """
    Test slashing succeeds when no builder payment exists at previous epoch slot.

    Input State Configured:
        - state advanced by 2 epochs, then 1 additional epoch after slashing setup
        - proposer_slashing: Valid slashing with different parent_root values
        - proposer_slashing.signed_header_1.message.slot: In previous epoch
        - builder_pending_payments: No entry set (empty slot)

    Output State Verified:
        - validators[slashed_index].slashed: True
        - builder_pending_payments: Remains empty (no change)
    """
    proposer_slashing, _ = prepare_process_proposer_slashing(
        spec,
        state,
        advance_epochs=2,
        advance_epochs_after=1,
        slot_offset=random.randrange(spec.SLOTS_PER_EPOCH),
        parent_root_2=b"\x99" * 32,
        # No builder_payment_amount - payment slot stays empty
    )

    slashed_slot = proposer_slashing.signed_header_1.message.slot
    assert spec.compute_epoch_at_slot(slashed_slot) == spec.get_previous_epoch(state)

    pre_state = state.copy()

    yield from run_proposer_slashing_processing(spec, state, proposer_slashing)

    assert_process_proposer_slashing(
        spec,
        state,
        pre_state,
        proposer_slashing,
    )


@with_gloas_and_later
@spec_state_test
def test_builder_payment_empty_old_epoch(spec, state):
    """
    Test slashing succeeds when no builder payment exists at older epoch slot (outside 2-epoch window).

    Input State Configured:
        - state advanced by 2 epochs, then 2 additional epochs after slashing setup
        - proposer_slashing: Valid slashing with different parent_root values
        - proposer_slashing.signed_header_1.message.slot: More than 2 epochs before current epoch
        - builder_pending_payments: No entry set (empty slot)

    Output State Verified:
        - validators[slashed_index].slashed: True
        - builder_pending_payments: Unchanged (slot outside 2-epoch window)
    """
    proposer_slashing, _ = prepare_process_proposer_slashing(
        spec,
        state,
        advance_epochs=2,
        advance_epochs_after=2,
        slot_offset=random.randrange(spec.SLOTS_PER_EPOCH),
        parent_root_2=b"\x99" * 32,
        # No builder_payment_amount - payment slot stays empty
    )

    pre_state = state.copy()

    yield from run_proposer_slashing_processing(spec, state, proposer_slashing)

    assert_process_proposer_slashing(
        spec,
        state,
        pre_state,
        proposer_slashing,
    )


@with_gloas_and_later
@spec_state_test
def test_builder_payment_deletion_current_epoch_first_slot(spec, state):
    """
    Test builder payment deletion at first slot of current epoch.

    Input State Configured:
        - state advanced to first slot of epoch
        - proposer_slashing with headers at slot 0 of current epoch
        - builder_pending_payments: Entry at payment_index = SLOTS_PER_EPOCH

    Output State Verified:
        - validators[slashed_index].slashed: True
        - builder_pending_payments: Entry at index SLOTS_PER_EPOCH deleted
    """
    proposer_slashing, _ = prepare_process_proposer_slashing(
        spec,
        state,
        advance_epochs=2,
        slot_offset=0,  # First slot of epoch
        parent_root_2=b"\x99" * 32,
        builder_payment_amount=spec.MIN_ACTIVATION_BALANCE,
        builder_payment_fee_recipient=b"\x42" * 20,
        builder_payment_weight=1000,
    )

    slashed_slot = proposer_slashing.signed_header_1.message.slot
    assert slashed_slot % spec.SLOTS_PER_EPOCH == 0

    pre_state = state.copy()

    yield from run_proposer_slashing_processing(spec, state, proposer_slashing)

    assert_process_proposer_slashing(
        spec,
        state,
        pre_state,
        proposer_slashing,
    )


@with_gloas_and_later
@spec_state_test
def test_builder_payment_deletion_current_epoch_last_slot(spec, state):
    """
    Test builder payment deletion at last slot of current epoch.

    Input State Configured:
        - state advanced to last slot of epoch
        - proposer_slashing with headers at last slot of current epoch
        - builder_pending_payments: Entry at payment_index = 2*SLOTS_PER_EPOCH - 1

    Output State Verified:
        - validators[slashed_index].slashed: True
        - builder_pending_payments: Entry at index 2*SLOTS_PER_EPOCH - 1 deleted
    """
    proposer_slashing, _ = prepare_process_proposer_slashing(
        spec,
        state,
        advance_epochs=2,
        slot_offset=spec.SLOTS_PER_EPOCH - 1,  # Last slot of epoch
        parent_root_2=b"\x99" * 32,
        builder_payment_amount=spec.MIN_ACTIVATION_BALANCE,
        builder_payment_fee_recipient=b"\x43" * 20,
        builder_payment_weight=1000,
    )

    slashed_slot = proposer_slashing.signed_header_1.message.slot
    assert slashed_slot % spec.SLOTS_PER_EPOCH == spec.SLOTS_PER_EPOCH - 1

    pre_state = state.copy()

    yield from run_proposer_slashing_processing(spec, state, proposer_slashing)

    assert_process_proposer_slashing(
        spec,
        state,
        pre_state,
        proposer_slashing,
    )


@with_gloas_and_later
@spec_state_test
def test_builder_payment_deletion_previous_epoch_first_slot(spec, state):
    """
    Test builder payment deletion at first slot of previous epoch.

    Input State Configured:
        - Headers created at first slot of an epoch
        - state advanced by 1 epoch (slot now in previous epoch)
        - builder_pending_payments: Entry at payment_index = 0

    Output State Verified:
        - validators[slashed_index].slashed: True
        - builder_pending_payments: Entry at index 0 deleted
    """
    proposer_slashing, _ = prepare_process_proposer_slashing(
        spec,
        state,
        advance_epochs=2,
        advance_epochs_after=1,
        slot_offset=0,  # First slot of epoch
        parent_root_2=b"\x99" * 32,
        builder_payment_amount=spec.MIN_ACTIVATION_BALANCE,
        builder_payment_fee_recipient=b"\x44" * 20,
        builder_payment_weight=1000,
    )

    slashed_slot = proposer_slashing.signed_header_1.message.slot
    assert slashed_slot % spec.SLOTS_PER_EPOCH == 0
    assert spec.compute_epoch_at_slot(slashed_slot) == spec.get_previous_epoch(state)

    pre_state = state.copy()

    yield from run_proposer_slashing_processing(spec, state, proposer_slashing)

    assert_process_proposer_slashing(
        spec,
        state,
        pre_state,
        proposer_slashing,
    )


@with_gloas_and_later
@spec_state_test
def test_builder_payment_deletion_previous_epoch_last_slot(spec, state):
    """
    Test builder payment deletion at last slot of previous epoch.

    Input State Configured:
        - Headers created at last slot of an epoch
        - state advanced by 1 epoch (slot now in previous epoch)
        - builder_pending_payments: Entry at payment_index = SLOTS_PER_EPOCH - 1

    Output State Verified:
        - validators[slashed_index].slashed: True
        - builder_pending_payments: Entry at index SLOTS_PER_EPOCH - 1 deleted
    """
    proposer_slashing, _ = prepare_process_proposer_slashing(
        spec,
        state,
        advance_epochs=2,
        advance_epochs_after=1,
        slot_offset=spec.SLOTS_PER_EPOCH - 1,  # Last slot of epoch
        parent_root_2=b"\x99" * 32,
        builder_payment_amount=spec.MIN_ACTIVATION_BALANCE,
        builder_payment_fee_recipient=b"\x45" * 20,
        builder_payment_weight=1000,
    )

    slashed_slot = proposer_slashing.signed_header_1.message.slot
    assert slashed_slot % spec.SLOTS_PER_EPOCH == spec.SLOTS_PER_EPOCH - 1
    assert spec.compute_epoch_at_slot(slashed_slot) == spec.get_previous_epoch(state)

    pre_state = state.copy()

    yield from run_proposer_slashing_processing(spec, state, proposer_slashing)

    assert_process_proposer_slashing(
        spec,
        state,
        pre_state,
        proposer_slashing,
    )
