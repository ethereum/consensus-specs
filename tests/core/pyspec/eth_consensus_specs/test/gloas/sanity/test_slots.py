from eth_consensus_specs.test.context import (
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

    assert state.execution_payload_availability[next_slot_index] == 0b0


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

    assert state.execution_payload_availability[next_slot_index] == 0b0


@with_gloas_and_later
@spec_state_test
def test_ptc_lookbehind_rotates_on_slot_advance(spec, state):
    """
    Test that process_slots correctly rotates ptc_lookbehind:
    old current becomes previous, new current is freshly computed.
    """
    current_ptc = list(state.ptc_lookbehind[1])

    yield "pre", state
    yield "slots", 1

    spec.process_slots(state, state.slot + 1)

    yield "post", state

    new_ptc = list(state.ptc_lookbehind[1])
    # Sanity: the two PTCs should differ, so the rotation test is meaningful
    assert current_ptc != new_ptc
    # After advancing, old current should become previous
    assert list(state.ptc_lookbehind[0]) == current_ptc
    # And new current should be freshly computed for the new slot
    assert new_ptc == list(spec.compute_ptc(state))


@with_gloas_and_later
@spec_state_test
def test_ptc_lookbehind_rotates_across_epoch_boundary(spec, state):
    """
    Test that ptc_lookbehind correctly rotates when crossing an epoch boundary.
    """
    # Advance to the last slot of the epoch
    target_slot = spec.SLOTS_PER_EPOCH - 1
    if state.slot < target_slot:
        spec.process_slots(state, target_slot)

    current_ptc = list(state.ptc_lookbehind[1])

    yield "pre", state
    yield "slots", 1

    # Cross the epoch boundary
    spec.process_slots(state, state.slot + 1)

    yield "post", state

    new_ptc = list(state.ptc_lookbehind[1])
    # Sanity: the two PTCs should differ, so the rotation test is meaningful
    assert current_ptc != new_ptc
    # Old current should become previous
    assert list(state.ptc_lookbehind[0]) == current_ptc
    # New current should be computed for the first slot of the new epoch
    assert new_ptc == list(spec.compute_ptc(state))
