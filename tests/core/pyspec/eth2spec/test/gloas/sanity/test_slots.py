from eth2spec.test.context import (
    spec_state_test,
    with_gloas_and_later,
)


@with_gloas_and_later
@spec_state_test
def test_execution_payload_availability_reset_from_set(spec, state):
    """
    Test that process_slot correctly resets execution_payload_availability
    from 1 -> 0 for the next slot.
    """
    # Set the next slot's availability to 1 initially
    next_slot_index = (state.slot + 1) % spec.SLOTS_PER_HISTORICAL_ROOT
    state.execution_payload_availability[next_slot_index] = 0b1

    # Verify it's set to 1 before processing
    assert state.execution_payload_availability[next_slot_index] == 0b1

    yield "pre", state
    yield "slots", 1

    # Process one slot
    spec.process_slots(state, state.slot + 1)

    yield "post", state

    # Verify the slot we just processed had its availability reset to 0
    # We advanced from slot N to slot N+1, so check slot N+1's availability
    current_slot_index = state.slot % spec.SLOTS_PER_HISTORICAL_ROOT
    assert state.execution_payload_availability[current_slot_index] == 0b0


@with_gloas_and_later
@spec_state_test
def test_execution_payload_availability_reset_from_unset(spec, state):
    """
    Test that process_slot correctly resets execution_payload_availability
    from 0 -> 0 for the next slot (no change when already unset).
    """
    # Set the next slot's availability to 0 initially
    next_slot_index = (state.slot + 1) % spec.SLOTS_PER_HISTORICAL_ROOT
    state.execution_payload_availability[next_slot_index] = 0b0

    # Verify it's set to 0 before processing
    assert state.execution_payload_availability[next_slot_index] == 0b0

    yield "pre", state
    yield "slots", 1

    # Process one slot
    spec.process_slots(state, state.slot + 1)

    yield "post", state

    # Verify the slot we just processed had its availability reset to 0
    # We advanced from slot N to slot N+1, so check slot N+1's availability
    current_slot_index = state.slot % spec.SLOTS_PER_HISTORICAL_ROOT
    assert state.execution_payload_availability[current_slot_index] == 0b0
