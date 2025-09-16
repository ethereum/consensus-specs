from eth2spec.test.context import (
    spec_state_test,
    with_gloas_and_later,
)
from eth2spec.test.helpers.attestations import (
    get_valid_attestation,
    run_attestation_processing,
    sign_attestation,
)
from eth2spec.test.helpers.state import (
    next_slots,
    transition_to_slot_via_block,
)


@with_gloas_and_later
@spec_state_test
def test_invalid_attestation_data_index_too_high(spec, state):
    """
    Test that attestation with index >= 2 is invalid in Gloas
    """
    attestation = get_valid_attestation(spec, state)
    next_slots(spec, state, spec.MIN_ATTESTATION_INCLUSION_DELAY)

    attestation.data.index = 2

    sign_attestation(spec, state, attestation)

    yield from run_attestation_processing(spec, state, attestation, valid=False)


@with_gloas_and_later
@spec_state_test
def test_valid_attestation_data_index_one_previous_slot_matching_blockroot(spec, state):
    """
    Test that attestation with index = 1 is valid when is_matching_blockroot=True, is_current_blockroot=False
    (attestation for slot 4 with slot 4's block root)
    """
    # Apply empty blocks to create proper block progression with different block roots
    transition_to_slot_via_block(spec, state, 5)  # Creates blocks for slots 1-5

    # Use slot 4's block root to make is_matching_blockroot = True
    slot_4_block_root = spec.get_block_root_at_slot(state, 4)
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
    assert is_matching_blockroot is True, "Expected is_matching_blockroot = True"
    assert is_current_blockroot is False, "Expected is_current_blockroot = False"

    assert spec.is_attestation_same_slot(state, attestation.data) is False
    yield from run_attestation_processing(spec, state, attestation, valid=True)


@with_gloas_and_later
@spec_state_test
def test_valid_attestation_data_index_one_previous_slot_current_blockroot(spec, state):
    """
    Test that attestation with index = 1 is valid when is_matching_blockroot=False, is_current_blockroot=True
    """
    # Apply empty blocks to create proper block progression with different block roots
    transition_to_slot_via_block(spec, state, 5)  # Creates blocks for slots 1-5

    # Create a custom arbitrary block root that's guaranteed to be different
    custom_block_root = spec.Root(b"\x01" * 32)  # Different from any real block root
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
    assert is_matching_blockroot is False, "Expected is_matching_blockroot = False"
    assert is_current_blockroot is True, "Expected is_current_blockroot = True"

    assert spec.is_attestation_same_slot(state, attestation.data) is False
    yield from run_attestation_processing(spec, state, attestation, valid=True)


@with_gloas_and_later
@spec_state_test
def test_invalid_same_slot_attestation_index_one(spec, state):
    """
    Test that same-slot condition with index = 1 is invalid (same-slot must use index = 0)
    """
    transition_to_slot_via_block(spec, state, 1)
    transition_to_slot_via_block(spec, state, 2)
    transition_to_slot_via_block(spec, state, 3)
    next_slots(spec, state, spec.MIN_ATTESTATION_INCLUSION_DELAY)

    attestation_slot = 2
    attestation = get_valid_attestation(spec, state, slot=attestation_slot)

    attestation.data.beacon_block_root = spec.get_block_root_at_slot(state, attestation_slot)

    attestation.data.index = 1

    sign_attestation(spec, state, attestation)

    assert spec.is_attestation_same_slot(state, attestation.data) is True
    yield from run_attestation_processing(spec, state, attestation, valid=False)


@with_gloas_and_later
@spec_state_test
def test_valid_attestation_data_index_zero_previous_slot(spec, state):
    """
    Test that attestation with index = 0 is valid in Gloas for previous slot attestations
    """
    transition_to_slot_via_block(spec, state, 5)  # Creates blocks for slots 1-5

    slot_3_block_root = spec.get_block_root_at_slot(state, 3)
    attestation = get_valid_attestation(spec, state, slot=4, beacon_block_root=slot_3_block_root)

    attestation.data.index = 0

    sign_attestation(spec, state, attestation)

    assert spec.is_attestation_same_slot(state, attestation.data) is False
    yield from run_attestation_processing(spec, state, attestation, valid=True)


@with_gloas_and_later
@spec_state_test
def test_valid_attestation_data_index_zero_same_slot(spec, state):
    """
    Test that attestation with index = 0 is still valid in Gloas for same slot
    """
    transition_to_slot_via_block(spec, state, 1)
    transition_to_slot_via_block(spec, state, 2)
    transition_to_slot_via_block(spec, state, 3)
    next_slots(spec, state, spec.MIN_ATTESTATION_INCLUSION_DELAY)

    attestation_slot = 2
    attestation = get_valid_attestation(spec, state, slot=attestation_slot)

    attestation.data.beacon_block_root = spec.get_block_root_at_slot(state, attestation_slot)

    attestation.data.index = 0

    sign_attestation(spec, state, attestation)

    assert spec.is_attestation_same_slot(state, attestation.data) is True
    yield from run_attestation_processing(spec, state, attestation, valid=True)


@with_gloas_and_later
@spec_state_test
def test_previous_epoch_attestation_with_payload_signaling(spec, state):
    """
    Test previous epoch attestation with payload availability signaling
    """
    # Move to next epoch
    transition_to_slot_via_block(spec, state, spec.SLOTS_PER_EPOCH)

    attestation = get_valid_attestation(
        spec, state, slot=1, beacon_block_root=spec.get_block_root_at_slot(state, 0)
    )

    attestation.data.index = 1

    sign_attestation(spec, state, attestation)

    assert spec.is_attestation_same_slot(state, attestation.data) is False
    yield from run_attestation_processing(spec, state, attestation, valid=True)


@with_gloas_and_later
@spec_state_test
def test_builder_payment_weight_tracking(spec, state):
    """
    Test that builder payment weights are tracked correctly for Gloas
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
    assert state.validators[attesting_validator_index].effective_balance > 0

    sign_attestation(spec, state, attestation)

    # Store initial weight for slot 0
    payment_slot_index = spec.SLOTS_PER_EPOCH + attestation_slot % spec.SLOTS_PER_EPOCH
    initial_weight = state.builder_pending_payments[payment_slot_index].weight

    # Process attestation
    yield from run_attestation_processing(spec, state, attestation, valid=True)

    # Check that weight was updated (this verifies the Gloas-specific logic)
    final_weight = state.builder_pending_payments[payment_slot_index].weight

    # Calculate expected weight increase for same-slot attestations in Gloas
    # Weight should increase by the effective balance of the attesting validator
    expected_weight_increase = state.validators[attesting_validator_index].effective_balance
    expected_final_weight = initial_weight + expected_weight_increase

    assert final_weight == expected_final_weight


@with_gloas_and_later
@spec_state_test
def test_builder_payment_weight_no_double_counting(spec, state):
    """
    Test that builder payment weights don't double count when will_set_new_flag is False
    (validator already has all eligible participation flags set)
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

    # Store initial weight for slot 0
    payment_slot_index = spec.SLOTS_PER_EPOCH + attestation_slot % spec.SLOTS_PER_EPOCH
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
    final_weight = state.builder_pending_payments[payment_slot_index].weight
    assert final_weight == after_first_weight  # Should be unchanged


@with_gloas_and_later
@spec_state_test
def test_matching_payload_true_same_slot(spec, state):
    """
    Test is_matching_payload = True path for same-slot attestations
    (same-slot always sets is_matching_payload = True regardless of availability bit)
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
    (when data.index matches the payload availability bit)
    """
    # Apply empty blocks to create proper block progression with different block roots
    transition_to_slot_via_block(spec, state, 3)  # Creates blocks for slots 1-3

    # Move forward to satisfy MIN_ATTESTATION_INCLUSION_DELAY requirement
    next_slots(spec, state, spec.MIN_ATTESTATION_INCLUSION_DELAY)

    # Set payload availability bit to 1 for slot 1
    availability_bit_index = 1 % spec.SLOTS_PER_HISTORICAL_ROOT
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

    # Verify the core functionality: attestation processes and gets some participation flags
    assert source_flag or target_flag, (
        "Should have participation flags when attestation processes successfully"
    )


@with_gloas_and_later
@spec_state_test
def test_matching_payload_false_historical_slot(spec, state):
    """
    Test is_matching_payload = False path for historical slots
    (when data.index does NOT match the payload availability bit)
    """
    # Apply empty blocks to create proper block progression with different block roots
    transition_to_slot_via_block(spec, state, 3)  # Creates blocks for slots 1-3

    # Move forward to be able to process slot 2 attestations with head flag delay
    next_slots(spec, state, spec.MIN_ATTESTATION_INCLUSION_DELAY)

    # Choose slot 2 which now has a real block root different from genesis
    historical_slot = 2
    availability_bit_index = historical_slot % spec.SLOTS_PER_HISTORICAL_ROOT

    # Set payload availability bit to 0 for slot 2
    state.execution_payload_availability[availability_bit_index] = 0

    # Create attestation with index = 1 (NOT matching the availability bit which is 0)
    attestation = get_valid_attestation(spec, state, slot=historical_slot)
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
    Test processing attestation with matching payload for historical slots
    """
    # Apply empty blocks to create proper block progression with different block roots
    transition_to_slot_via_block(spec, state, 3)  # Creates blocks for slots 1-3

    # Move forward exactly 1 slot to get inclusion_delay == MIN_ATTESTATION_INCLUSION_DELAY (which is 1)
    next_slots(spec, state, 1)  # Now at slot 4

    # Choose slot 3 for the attestation so inclusion_delay = 4 - 3 = 1
    # This should NOT be same-slot because we're processing at a different slot
    historical_slot = 3
    availability_bit_index = historical_slot % spec.SLOTS_PER_HISTORICAL_ROOT

    # Set payload availability bit to 1 for slot 3
    state.execution_payload_availability[availability_bit_index] = 1

    # Create attestation with index = 0 for same-slot (as required by Gloas)
    attestation = get_valid_attestation(spec, state, slot=historical_slot)
    attestation.data.index = 0  # Same-slot attestations must use index = 0

    sign_attestation(spec, state, attestation)

    # Get the attesting validator
    attesting_indices = spec.get_attesting_indices(state, attestation)
    validator_index = list(attesting_indices)[0]

    yield from run_attestation_processing(spec, state, attestation, valid=True)

    # Verify that head flag is set when conditions are met
    final_participation = state.current_epoch_participation[validator_index]
    final_head_flag = spec.has_flag(final_participation, spec.TIMELY_HEAD_FLAG_INDEX)

    assert final_head_flag, "Should have head flag when payload matches and inclusion is timely"


@with_gloas_and_later
@spec_state_test
def test_mismatched_payload_no_head_flag(spec, state):
    """
    Test that mismatched payload prevents TIMELY_HEAD_FLAG even with matching blockroot
    """
    # Apply empty blocks to create proper block progression with different block roots
    transition_to_slot_via_block(spec, state, 4)  # Creates blocks for slots 1-4

    # Move forward to be able to process slot 3 attestations within head flag delay
    next_slots(spec, state, spec.MIN_ATTESTATION_INCLUSION_DELAY)

    # Choose slot 3 which now has a real block root different from genesis
    historical_slot = 3
    availability_bit_index = historical_slot % spec.SLOTS_PER_HISTORICAL_ROOT

    # Set payload availability bit to 0 for slot 3
    state.execution_payload_availability[availability_bit_index] = 0

    # Create attestation with NON-matching payload index
    attestation = get_valid_attestation(spec, state, slot=historical_slot)
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
