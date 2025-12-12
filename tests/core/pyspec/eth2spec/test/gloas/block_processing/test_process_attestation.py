from eth2spec.test.context import (
    spec_state_test,
    with_gloas_and_later,
)
from eth2spec.test.helpers.attestations import (
    get_valid_attestation,
    run_attestation_processing,
    sign_attestation,
)
from eth2spec.test.helpers.block import apply_empty_block
from eth2spec.test.helpers.state import (
    next_slots,
    transition_to_slot_via_block,
)


def _setup_missed_slot_scenario(spec, state):
    """
    Creates blocks for slots 1, 2, 3 but skips slot 4 (missed slot).
    Returns slot 4's block root (which inherits from slot 3).
    Used for testing is_matching_blockroot=True, is_current_blockroot=False.
    """
    apply_empty_block(spec, state, 1)
    apply_empty_block(spec, state, 2)
    apply_empty_block(spec, state, 3)
    next_slots(spec, state, 2)  # Advance to slot 5 without creating block at slot 4
    return spec.get_block_root_at_slot(state, 4)


def _setup_same_slot_scenario(spec, state, target_slot):
    """
    Creates blocks for slots 1, 2, 3 and advances for inclusion delay.
    Returns the block root for the target slot.
    Used for testing same-slot attestations.
    """
    apply_empty_block(spec, state, 1)
    apply_empty_block(spec, state, 2)
    apply_empty_block(spec, state, 3)
    next_slots(spec, state, spec.MIN_ATTESTATION_INCLUSION_DELAY)
    return spec.get_block_root_at_slot(state, target_slot)


@with_gloas_and_later
@spec_state_test
def test_invalid_attestation_data_index_too_high(spec, state):
    """
    Test that attestation with index >= 2 is invalid in Gloas.
    """
    attestation = get_valid_attestation(spec, state)
    next_slots(spec, state, spec.MIN_ATTESTATION_INCLUSION_DELAY)
    attestation.data.index = 2
    sign_attestation(spec, state, attestation)

    yield from run_attestation_processing(spec, state, attestation, valid=False)


@with_gloas_and_later
@spec_state_test
def test_valid_attestation_data_index_zero_previous_slot(spec, state):
    """
    Test that attestation with index = 0 is valid in Gloas for previous slot attestations.
    """
    # Using basic scenario (advance to slot 5, only creates one block at slot 5)
    transition_to_slot_via_block(spec, state, 5)
    slot_3_block_root = spec.get_block_root_at_slot(state, 3)  # Will be genesis block root
    attestation = get_valid_attestation(spec, state, slot=4, beacon_block_root=slot_3_block_root)
    attestation.data.index = 0
    sign_attestation(spec, state, attestation)

    assert spec.is_attestation_same_slot(state, attestation.data) is False
    yield from run_attestation_processing(spec, state, attestation, valid=True)


@with_gloas_and_later
@spec_state_test
def test_valid_attestation_data_index_one_previous_slot_matching_blockroot(spec, state):
    """
    Test that attestation with index = 1 is valid when is_matching_blockroot=True, is_current_blockroot=False
    (attestation for slot 4 where no block was proposed, so it inherits slot 3's block root).
    """
    slot_4_block_root = _setup_missed_slot_scenario(spec, state)
    attestation = get_valid_attestation(spec, state, slot=4, beacon_block_root=slot_4_block_root)
    attestation.data.index = 1
    sign_attestation(spec, state, attestation)

    # Verify the intended blockroot conditions
    is_matching_blockroot = attestation.data.beacon_block_root == spec.get_block_root_at_slot(
        state, spec.Slot(attestation.data.slot)
    )
    is_current_blockroot = attestation.data.beacon_block_root != spec.get_block_root_at_slot(
        state, spec.Slot(attestation.data.slot - 1)
    )
    assert is_matching_blockroot is True
    assert is_current_blockroot is False

    assert spec.is_attestation_same_slot(state, attestation.data) is False
    yield from run_attestation_processing(spec, state, attestation, valid=True)


@with_gloas_and_later
@spec_state_test
def test_valid_attestation_data_index_one_previous_slot_current_blockroot(spec, state):
    """
    Test that attestation with index = 1 is valid when is_matching_blockroot=False, is_current_blockroot=True.
    """
    transition_to_slot_via_block(spec, state, 5)
    # Custom block root different from any real block root
    custom_block_root = spec.Root(b"\x01" * 32)
    attestation = get_valid_attestation(spec, state, slot=4, beacon_block_root=custom_block_root)
    attestation.data.index = 1
    sign_attestation(spec, state, attestation)

    # Verify the intended blockroot conditions
    is_matching_blockroot = attestation.data.beacon_block_root == spec.get_block_root_at_slot(
        state, spec.Slot(attestation.data.slot)
    )
    is_current_blockroot = attestation.data.beacon_block_root != spec.get_block_root_at_slot(
        state, spec.Slot(attestation.data.slot - 1)
    )
    assert is_matching_blockroot is False
    assert is_current_blockroot is True

    assert spec.is_attestation_same_slot(state, attestation.data) is False
    yield from run_attestation_processing(spec, state, attestation, valid=True)


@with_gloas_and_later
@spec_state_test
def test_valid_same_slot_attestation_index_zero(spec, state):
    """
    Test that attestation with index = 0 is still valid in Gloas for same slot.
    """
    attestation_slot = 2
    slot_2_block_root = _setup_same_slot_scenario(spec, state, target_slot=attestation_slot)
    attestation = get_valid_attestation(
        spec, state, slot=attestation_slot, beacon_block_root=slot_2_block_root
    )
    attestation.data.index = 0
    sign_attestation(spec, state, attestation)

    assert spec.is_attestation_same_slot(state, attestation.data) is True
    yield from run_attestation_processing(spec, state, attestation, valid=True)


@with_gloas_and_later
@spec_state_test
def test_invalid_same_slot_attestation_index_one(spec, state):
    """
    Test that same-slot condition with index = 1 is invalid (same-slot must use index = 0).
    """
    attestation_slot = 2
    slot_2_block_root = _setup_same_slot_scenario(spec, state, target_slot=attestation_slot)
    attestation = get_valid_attestation(
        spec, state, slot=attestation_slot, beacon_block_root=slot_2_block_root
    )
    attestation.data.index = 1
    sign_attestation(spec, state, attestation)

    assert spec.is_attestation_same_slot(state, attestation.data) is True
    yield from run_attestation_processing(spec, state, attestation, valid=False)


@with_gloas_and_later
@spec_state_test
def test_builder_payment_weight_tracking(spec, state):
    """
    Test that builder payment weights are tracked correctly for Gloas.
    """
    transition_to_slot_via_block(spec, state, 2)

    # Create attestation for slot 0
    attestation_slot = 0
    attestation = get_valid_attestation(spec, state, slot=attestation_slot, index=0)
    attestation.data.index = 0  # Same-slot (slot 0) must use index 0

    # Get only the first validator to attest
    committee = spec.get_beacon_committee(state, attestation_slot, 0)

    # Clear all bits except first validator
    for i in range(len(attestation.aggregation_bits)):
        attestation.aggregation_bits[i] = i == 0

    attesting_validator_index = committee[0]
    expected_weight_increase = state.validators[attesting_validator_index].effective_balance
    assert expected_weight_increase > 0

    sign_attestation(spec, state, attestation)

    # Manually set up a non-zero builder pending payment for slot 0
    payment_slot_index = spec.SLOTS_PER_EPOCH + attestation_slot % spec.SLOTS_PER_EPOCH
    test_payment_amount = spec.Gwei(1000000000)
    state.builder_pending_payments[payment_slot_index] = spec.BuilderPendingPayment(
        weight=spec.Gwei(0),
        withdrawal=spec.BuilderPendingWithdrawal(
            fee_recipient=spec.ExecutionAddress(),
            amount=test_payment_amount,
            pubkey=state.builders[0].pubkey,
        ),
    )

    # Store initial weight for slot 0
    initial_weight = state.builder_pending_payments[payment_slot_index].weight

    # Process attestation
    yield from run_attestation_processing(spec, state, attestation, valid=True)

    # Check that weight was updated (this verifies the Gloas-specific logic)
    final_weight = state.builder_pending_payments[payment_slot_index].weight

    # Calculate expected weight increase for same-slot attestations in Gloas
    # Weight should increase by the effective balance of the attesting validator
    expected_final_weight = initial_weight + expected_weight_increase

    assert final_weight == expected_final_weight


@with_gloas_and_later
@spec_state_test
def test_builder_payment_weight_no_double_counting(spec, state):
    """
    Test that builder payment weights don't double count when will_set_new_flag is False
    (validator already has all eligible participation flags set).
    """
    transition_to_slot_via_block(spec, state, 2)

    # Create first attestation for slot 0 with single validator
    attestation_slot = 0
    attestation1 = get_valid_attestation(spec, state, slot=attestation_slot)
    attestation1.data.index = 0  # Same-slot (slot 0) must use index 0

    # Get committee and set only first validator to attest
    committee = spec.get_beacon_committee(state, attestation_slot, 0)
    for i in range(len(attestation1.aggregation_bits)):
        attestation1.aggregation_bits[i] = i == 0

    attesting_validator_index = committee[0]
    assert state.validators[attesting_validator_index].effective_balance > 0

    sign_attestation(spec, state, attestation1)

    # Manually set up a non-zero builder pending payment for slot 0
    payment_slot_index = spec.SLOTS_PER_EPOCH + attestation_slot % spec.SLOTS_PER_EPOCH
    test_payment_amount = spec.Gwei(1000000000)
    state.builder_pending_payments[payment_slot_index] = spec.BuilderPendingPayment(
        weight=spec.Gwei(0),
        withdrawal=spec.BuilderPendingWithdrawal(
            fee_recipient=spec.ExecutionAddress(),
            amount=test_payment_amount,
            pubkey=state.builders[0].pubkey,
        ),
    )

    # Store initial weight for slot 0
    initial_weight = state.builder_pending_payments[payment_slot_index].weight

    # Process first attestation (this should set flags and increase weight)
    yield from run_attestation_processing(spec, state, attestation1, valid=True)

    # Check weight increased
    after_first_weight = state.builder_pending_payments[payment_slot_index].weight
    attesting_validator_index = committee[0]
    expected_weight_after_first = (
        initial_weight + state.validators[attesting_validator_index].effective_balance
    )
    assert after_first_weight == expected_weight_after_first
    assert after_first_weight > initial_weight, "First attestation should have increased the weight"

    # Create second attestation with SAME validator (should not increase weight again)
    attestation2 = get_valid_attestation(spec, state, slot=attestation_slot)
    attestation2.data.index = 0  # Same-slot (slot 0) must use index 0

    # Set same validator to attest again
    for i in range(len(attestation2.aggregation_bits)):
        attestation2.aggregation_bits[i] = i == 0

    sign_attestation(spec, state, attestation2)

    # Process second attestation (will_set_new_flag should be False, no weight increase)
    yield from run_attestation_processing(spec, state, attestation2, valid=True)

    # Check weight did NOT increase (no double counting)
    # Should be unchanged
    assert state.builder_pending_payments[payment_slot_index].weight == after_first_weight


@with_gloas_and_later
@spec_state_test
def test_matching_payload_true_same_slot(spec, state):
    """
    Test is_matching_payload = True path for same-slot attestations
    (same-slot always sets is_matching_payload = True regardless of availability bit).
    """
    # Use slot 0 to trigger same-slot condition
    transition_to_slot_via_block(spec, state, 2)

    # Set payload availability bit to 0 for slot 0 (payload not available)
    attestation_slot = 0
    state.execution_payload_availability[attestation_slot % spec.SLOTS_PER_HISTORICAL_ROOT] = 0

    # Create attestation for slot 0
    attestation = get_valid_attestation(spec, state, slot=attestation_slot)
    attestation.data.index = 0  # Same-slot must use index 0
    sign_attestation(spec, state, attestation)

    assert spec.is_attestation_same_slot(state, attestation.data) is True

    # This should pass because same-slot always sets is_matching_payload = True
    # regardless of the execution_payload_availability bit
    yield from run_attestation_processing(spec, state, attestation, valid=True)


@with_gloas_and_later
@spec_state_test
def test_matching_payload_true_historical_slot(spec, state):
    """
    Test is_matching_payload = True path for historical slots
    (when data.index matches the payload availability bit).
    """
    # Advance to slot 3 (only creates one block at slot 3)
    transition_to_slot_via_block(spec, state, 3)

    # Move forward to satisfy MIN_ATTESTATION_INCLUSION_DELAY requirement
    next_slots(spec, state, spec.MIN_ATTESTATION_INCLUSION_DELAY)

    # Set payload availability bit to 1 for slot 1
    availability_bit_index = 1
    state.execution_payload_availability[availability_bit_index] = 1

    # Create attestation for slot 1 - should now satisfy inclusion delay and get head flag
    historical_slot = 1
    attestation = get_valid_attestation(spec, state, slot=historical_slot)
    attestation.data.index = 1  # Should match the availability bit
    sign_attestation(spec, state, attestation)

    # Get the attesting validator
    attesting_indices = spec.get_attesting_indices(state, attestation)
    validator_index = list(attesting_indices)[0]

    assert spec.is_attestation_same_slot(state, attestation.data) is False

    # This should pass because data.index (1) matches the availability bit (1)
    yield from run_attestation_processing(spec, state, attestation, valid=True)

    final_participation = state.current_epoch_participation[validator_index]
    source_flag = spec.has_flag(final_participation, spec.TIMELY_SOURCE_FLAG_INDEX)
    target_flag = spec.has_flag(final_participation, spec.TIMELY_TARGET_FLAG_INDEX)
    head_flag = spec.has_flag(final_participation, spec.TIMELY_HEAD_FLAG_INDEX)

    # Verify the core functionality: attestation processes and gets some participation flags
    assert source_flag or target_flag, (
        "Should have participation flags when attestation processes successfully"
    )

    assert not head_flag, "Should not get head flag for historical slot attestation"


@with_gloas_and_later
@spec_state_test
def test_matching_payload_false_historical_slot(spec, state):
    """
    Test is_matching_payload = False path for historical slots
    (when data.index does NOT match the payload availability bit).
    """
    apply_empty_block(spec, state, 1)
    apply_empty_block(spec, state, 2)
    apply_empty_block(spec, state, 3)
    next_slots(spec, state, spec.MIN_ATTESTATION_INCLUSION_DELAY)

    # Choose slot 2 which now has a real block root different from genesis
    # Set payload availability bit to 0 for slot 2
    state.execution_payload_availability[2] = 0

    # Create attestation for slot 2 but with slot 1's block root to make it historical (not same-slot)
    slot_1_block_root = spec.get_block_root_at_slot(state, 1)
    attestation = get_valid_attestation(spec, state, slot=2, beacon_block_root=slot_1_block_root)
    attestation.data.index = 1  # Does not match the availability bit (0)
    sign_attestation(spec, state, attestation)

    # Get the attesting validator
    attesting_indices = spec.get_attesting_indices(state, attestation)
    validator_index = list(attesting_indices)[0]

    assert spec.is_attestation_same_slot(state, attestation.data) is False

    # This should still pass (the attestation is valid)
    # but is_matching_payload will be False, affecting participation flags
    yield from run_attestation_processing(spec, state, attestation, valid=True)

    # Verify that head flag was NOT set due to mismatched payload
    final_participation = state.current_epoch_participation[validator_index]
    final_head_flag = spec.has_flag(final_participation, spec.TIMELY_HEAD_FLAG_INDEX)
    assert not final_head_flag, "Should not get head flag when payload doesn't match"


@with_gloas_and_later
@spec_state_test
def test_matching_payload_gets_head_flag(spec, state):
    """
    Test get_attestation_participation_flag_indices for historical slots where
    is_matching_payload = data.index == state.execution_payload_availability[data.slot % SLOTS_PER_HISTORICAL_ROOT]
    and is_matching_head = is_matching_blockroot and is_matching_payload.
    """
    # Use missed slot scenario: blocks for slots 1, 2, 3 but skip slot 4
    slot_4_block_root = _setup_missed_slot_scenario(spec, state)

    # Set payload availability bit to 1 for slot 4
    state.execution_payload_availability[4] = 1

    # Create attestation with index = 1 to match the availability bit
    attestation = get_valid_attestation(spec, state, slot=4, beacon_block_root=slot_4_block_root)
    attestation.data.index = 1  # Should match availability bit = 1
    sign_attestation(spec, state, attestation)

    # Verify this is NOT same-slot
    assert spec.is_attestation_same_slot(state, attestation.data) is False

    # Get the attesting validator
    attesting_indices = spec.get_attesting_indices(state, attestation)
    validator_index = list(attesting_indices)[0]

    yield from run_attestation_processing(spec, state, attestation, valid=True)

    # Verify that head flag is set when is_matching_payload = True
    final_participation = state.current_epoch_participation[validator_index]
    final_head_flag = spec.has_flag(final_participation, spec.TIMELY_HEAD_FLAG_INDEX)

    assert final_head_flag, "Should have head flag when data.index matches payload availability bit"


@with_gloas_and_later
@spec_state_test
def test_mismatched_payload_no_head_flag(spec, state):
    """
    Test that mismatched payload prevents TIMELY_HEAD_FLAG even with matching blockroot.
    """
    # Use missed slot scenario: blocks for slots 1, 2, 3 but skip slot 4
    slot_4_block_root = _setup_missed_slot_scenario(spec, state)

    # Set payload availability bit to 0 for slot 4
    state.execution_payload_availability[4] = 0

    # Create attestation with index = 1 which does NOT match availability bit = 0
    attestation = get_valid_attestation(spec, state, slot=4, beacon_block_root=slot_4_block_root)
    attestation.data.index = 1  # Does NOT match availability bit = 0
    sign_attestation(spec, state, attestation)

    # Get the attesting validator
    attesting_indices = spec.get_attesting_indices(state, attestation)
    validator_index = list(attesting_indices)[0]

    assert spec.is_attestation_same_slot(state, attestation.data) is False

    yield from run_attestation_processing(spec, state, attestation, valid=True)

    # Check final participation flags
    final_participation = state.current_epoch_participation[validator_index]
    final_head_flag = spec.has_flag(final_participation, spec.TIMELY_HEAD_FLAG_INDEX)

    assert not final_head_flag, "Should not get head flag when payload doesn't match"
