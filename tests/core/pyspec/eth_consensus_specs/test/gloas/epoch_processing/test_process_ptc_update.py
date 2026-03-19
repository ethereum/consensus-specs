from eth_consensus_specs.test.context import (
    expect_assertion_error,
    single_phase,
    spec_state_test,
    with_phases,
)
from eth_consensus_specs.test.helpers.constants import GLOAS
from eth_consensus_specs.test.helpers.epoch_processing import run_epoch_processing_with


@with_phases([GLOAS])
@spec_state_test
@single_phase
def test_process_ptc_update_caches_last_slot_ptc(spec, state):
    """
    Test that process_ptc_update caches the PTC for the current slot
    (last slot of the epoch) into state.previous_epoch_last_ptc.
    """
    # Advance to last slot of the epoch
    spec.process_slots(state, state.slot + spec.SLOTS_PER_EPOCH - 1)

    # Compute expected PTC for this slot (last slot of epoch, before balance updates)
    expected_ptc = spec.compute_ptc(state, spec.Slot(state.slot))

    yield from run_epoch_processing_with(spec, state, "process_ptc_update")

    assert list(state.previous_epoch_last_ptc) == list(expected_ptc)


@with_phases([GLOAS])
@spec_state_test
@single_phase
def test_get_ptc_returns_cached_previous_for_epoch_boundary(spec, state):
    """
    Test that after crossing an epoch boundary, get_ptc returns the cached
    previous_epoch_last_ptc for the last slot of the previous epoch.
    """
    # Advance to first slot of next epoch
    target_slot = spec.SLOTS_PER_EPOCH
    spec.process_slots(state, target_slot)

    # Now state.slot = SLOTS_PER_EPOCH (first slot of epoch 1)
    # Query PTC for slot SLOTS_PER_EPOCH - 1 (last slot of epoch 0)
    last_slot_prev_epoch = spec.Slot(spec.SLOTS_PER_EPOCH - 1)
    ptc = spec.get_ptc(state, last_slot_prev_epoch)

    # Should match previous_epoch_last_ptc cached during epoch processing
    assert list(ptc) == list(state.previous_epoch_last_ptc)
    # Should not be all zeros (real PTC was cached)
    assert any(v != 0 for v in ptc)


@with_phases([GLOAS])
@spec_state_test
@single_phase
def test_get_ptc_computes_current_epoch_on_demand(spec, state):
    """
    Test that get_ptc computes current epoch PTCs on demand via compute_ptc.
    """
    ptc_slot_0 = spec.get_ptc(state, spec.Slot(0))
    computed_ptc_slot_0 = spec.compute_ptc(state, spec.Slot(0))

    assert list(ptc_slot_0) == list(computed_ptc_slot_0)


@with_phases([GLOAS])
@spec_state_test
@single_phase
def test_compute_ptc_next_epoch_asserts(spec, state):
    """
    Test that compute_ptc does not allow next-epoch computation.
    """
    next_epoch_slot = spec.Slot(spec.SLOTS_PER_EPOCH)
    expect_assertion_error(lambda: spec.compute_ptc(state, next_epoch_slot))


@with_phases([GLOAS])
@spec_state_test
@single_phase
def test_get_ptc_next_epoch_asserts(spec, state):
    """
    Test that get_ptc does not allow next-epoch lookups.
    """
    next_epoch_slot = spec.Slot(spec.SLOTS_PER_EPOCH)
    expect_assertion_error(lambda: spec.get_ptc(state, next_epoch_slot))
