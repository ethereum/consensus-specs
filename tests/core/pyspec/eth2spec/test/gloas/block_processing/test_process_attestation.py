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
def test_valid_attestation_data_index_one_previous_slot(spec, state):
    """
    Test that attestation with index = 1 is valid in Gloas for previous slot attestations
    """
    # Move forward so we can reference a previous slot
    next_slots(spec, state, 5)

    # Create attestation for a previous slot (not same-slot)
    previous_slot = state.slot - 2
    attestation = get_valid_attestation(spec, state, slot=previous_slot)

    attestation.data.index = 1

    sign_attestation(spec, state, attestation)

    yield from run_attestation_processing(spec, state, attestation, valid=True)


@with_gloas_and_later
@spec_state_test
def test_valid_attestation_data_index_zero(spec, state):
    """
    Test that attestation with index = 0 is still valid in Gloas for same slot
    """
    attestation = get_valid_attestation(spec, state)
    next_slots(spec, state, spec.MIN_ATTESTATION_INCLUSION_DELAY)

    attestation.data.index = 0

    sign_attestation(spec, state, attestation)

    yield from run_attestation_processing(spec, state, attestation, valid=True)


@with_gloas_and_later
@spec_state_test
def test_invalid_same_slot_attestation_index_one(spec, state):
    """
    Test that same-slot condition with index = 1 is invalid (same-slot must use index = 0)
    """
    # Create attestation for slot 0 (which triggers same-slot condition)
    state.slot = 1  # Move to slot 1
    attestation = get_valid_attestation(spec, state, slot=0)
    attestation.data.index = 1

    next_slots(spec, state, spec.MIN_ATTESTATION_INCLUSION_DELAY)

    sign_attestation(spec, state, attestation)

    yield from run_attestation_processing(spec, state, attestation, valid=False)


@with_gloas_and_later
@spec_state_test
def test_previous_epoch_attestation_with_payload_signaling(spec, state):
    """
    Test previous epoch attestation with payload availability signaling
    """
    # Move to next epoch
    next_slots(spec, state, spec.SLOTS_PER_EPOCH)

    # Create attestation for previous epoch - use slot from previous epoch that's not slot 0
    previous_slot = state.slot - spec.SLOTS_PER_EPOCH + 1  # Previous epoch, slot 1
    attestation = get_valid_attestation(spec, state, slot=previous_slot)

    attestation.data.index = 1

    sign_attestation(spec, state, attestation)

    yield from run_attestation_processing(spec, state, attestation, valid=True)


@with_gloas_and_later
@spec_state_test
def test_builder_payment_weight_tracking(spec, state):
    """
    Test that builder payment weights are tracked correctly for Gloas
    """
    # Use slot 0 condition to trigger same-slot logic
    attestation_slot = 0
    state.slot = 2  # Move forward so we can process slot 0 attestation

    # Create attestation for slot 0
    attestation = get_valid_attestation(spec, state, slot=attestation_slot, index=0)
    attestation.data.index = 0  # Same-slot (slot 0) must use index 0

    # Get only the first validator to attest
    committee = spec.get_beacon_committee(state, attestation_slot, 0)

    # Clear all bits except first validator
    for i in range(len(attestation.aggregation_bits)):
        attestation.aggregation_bits[i] = i == 0

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
    attesting_validator_index = committee[0]  # We set only first validator to attest
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
    # Use slot 0 condition to trigger same-slot logic
    attestation_slot = 0
    state.slot = 2  # Move forward so we can process slot 0 attestation

    # Create first attestation for slot 0 with single validator
    attestation1 = get_valid_attestation(spec, state, slot=attestation_slot)
    attestation1.data.index = 0  # Same-slot (slot 0) must use index 0

    # Get committee and set only first validator to attest
    committee = spec.get_beacon_committee(state, attestation_slot, 0)
    for i in range(len(attestation1.aggregation_bits)):
        attestation1.aggregation_bits[i] = i == 0

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
    attestation_slot = 0
    state.slot = 2  # Move forward so we can process slot 0 attestation

    # Set payload availability bit to 0 for slot 0 (payload not available)
    state.execution_payload_availability[attestation_slot % spec.SLOTS_PER_HISTORICAL_ROOT] = 0

    # Create attestation for slot 0
    attestation = get_valid_attestation(spec, state, slot=attestation_slot)
    attestation.data.index = 0  # Same-slot must use index 0

    sign_attestation(spec, state, attestation)

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
    # Move forward to create history but keep within head flag delay
    next_slots(spec, state, spec.MIN_ATTESTATION_INCLUSION_DELAY + 1)

    # Choose a historical slot that's recent enough for head flag
    historical_slot = state.slot - spec.MIN_ATTESTATION_INCLUSION_DELAY
    availability_bit_index = historical_slot % spec.SLOTS_PER_HISTORICAL_ROOT

    # Set payload availability bit to 1 for this slot
    state.execution_payload_availability[availability_bit_index] = 1

    # Create attestation with index = 1 (matching the availability bit)
    attestation = get_valid_attestation(spec, state, slot=historical_slot)
    attestation.data.index = 1  # Should match the availability bit

    sign_attestation(spec, state, attestation)

    # Get the attesting validator
    attesting_indices = spec.get_attesting_indices(state, attestation)
    validator_index = list(attesting_indices)[0]

    # This should pass because data.index (1) matches the availability bit (1)
    yield from run_attestation_processing(spec, state, attestation, valid=True)

    # Verify that head flag was set due to matching payload
    final_participation = state.current_epoch_participation[validator_index]
    final_head_flag = spec.has_flag(final_participation, spec.TIMELY_HEAD_FLAG_INDEX)
    assert final_head_flag, "Should get head flag when payload matches"


@with_gloas_and_later
@spec_state_test
def test_matching_payload_false_historical_slot(spec, state):
    """
    Test is_matching_payload = False path for historical slots
    (when data.index does NOT match the payload availability bit)
    """
    # Move forward to create history but keep within head flag delay
    next_slots(spec, state, spec.MIN_ATTESTATION_INCLUSION_DELAY + 1)

    # Choose a historical slot that's recent enough for head flag
    historical_slot = state.slot - spec.MIN_ATTESTATION_INCLUSION_DELAY
    availability_bit_index = historical_slot % spec.SLOTS_PER_HISTORICAL_ROOT

    # Set payload availability bit to 0 for this slot
    state.execution_payload_availability[availability_bit_index] = 0

    # Create attestation with index = 1 (NOT matching the availability bit)
    attestation = get_valid_attestation(spec, state, slot=historical_slot)
    attestation.data.index = 1  # Does not match the availability bit (0)

    sign_attestation(spec, state, attestation)

    # Get the attesting validator
    attesting_indices = spec.get_attesting_indices(state, attestation)
    validator_index = list(attesting_indices)[0]

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
    Test that matching payload AND blockroot gets the TIMELY_HEAD_FLAG
    """
    # Move forward to avoid same-slot condition
    next_slots(spec, state, 5)

    # Choose a recent slot for timely head flag (but not slot 0 and not current slot)
    historical_slot = state.slot - spec.MIN_ATTESTATION_INCLUSION_DELAY

    availability_bit_index = historical_slot % spec.SLOTS_PER_HISTORICAL_ROOT

    # Set payload availability bit to 1
    state.execution_payload_availability[availability_bit_index] = 1

    # Create attestation with matching payload index
    attestation = get_valid_attestation(spec, state, slot=historical_slot)
    attestation.data.index = 1  # Matches availability bit = 1

    sign_attestation(spec, state, attestation)

    # Get the attesting validator
    attesting_indices = spec.get_attesting_indices(state, attestation)
    validator_index = list(attesting_indices)[0]

    yield from run_attestation_processing(spec, state, attestation, valid=True)

    # Check final participation flags
    final_participation = state.current_epoch_participation[validator_index]
    final_head_flag = spec.has_flag(final_participation, spec.TIMELY_HEAD_FLAG_INDEX)

    assert final_head_flag, "Should have head flag when payload matches and inclusion is timely"


@with_gloas_and_later
@spec_state_test
def test_mismatched_payload_no_head_flag(spec, state):
    """
    Test that mismatched payload prevents TIMELY_HEAD_FLAG even with matching blockroot
    """
    # Move forward to avoid same-slot condition
    next_slots(spec, state, 5)

    # Choose a recent slot for timely inclusion (but not slot 0 and not current slot)
    historical_slot = state.slot - spec.MIN_ATTESTATION_INCLUSION_DELAY
    # Ensure it's not slot 0 to avoid same-slot condition
    if historical_slot == 0:
        historical_slot = 1

    availability_bit_index = historical_slot % spec.SLOTS_PER_HISTORICAL_ROOT

    # Set payload availability bit to 0
    state.execution_payload_availability[availability_bit_index] = 0

    # Create attestation with NON-matching payload index
    attestation = get_valid_attestation(spec, state, slot=historical_slot)
    attestation.data.index = 1  # Does NOT match availability bit = 0

    sign_attestation(spec, state, attestation)

    # Get the attesting validator
    attesting_indices = spec.get_attesting_indices(state, attestation)
    validator_index = list(attesting_indices)[0]

    yield from run_attestation_processing(spec, state, attestation, valid=True)

    # Check final participation flags
    final_participation = state.current_epoch_participation[validator_index]
    final_head_flag = spec.has_flag(final_participation, spec.TIMELY_HEAD_FLAG_INDEX)

    assert not final_head_flag, "Should not get head flag when payload doesn't match"
