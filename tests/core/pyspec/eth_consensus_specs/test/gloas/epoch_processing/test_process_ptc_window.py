from eth_consensus_specs.test.context import (
    single_phase,
    spec_state_test,
    with_phases,
)
from eth_consensus_specs.test.helpers.constants import GLOAS
from eth_consensus_specs.test.helpers.epoch_processing import run_epoch_processing_with


def _compute_epoch_ptc(spec, state, epoch):
    start_slot = spec.compute_start_slot_at_epoch(epoch)
    return [
        spec.compute_ptc(state, spec.Slot(slot))
        for slot in range(start_slot, start_slot + spec.SLOTS_PER_EPOCH)
    ]


@with_phases([GLOAS])
@spec_state_test
@single_phase
def test_process_ptc_window_shifts_all_three_epochs(spec, state):
    """
    Verify that process_ptc_window shifts prev/curr/next correctly
    and that get_ptc returns the right committees afterwards.
    """
    spec.process_slots(state, state.slot + 2 * spec.SLOTS_PER_EPOCH - 1)

    current_epoch = spec.get_current_epoch(state)
    prev_epoch_ptc = _compute_epoch_ptc(spec, state, spec.Epoch(current_epoch - 1))
    curr_epoch_ptc = _compute_epoch_ptc(spec, state, current_epoch)
    next_epoch_ptc = _compute_epoch_ptc(spec, state, spec.Epoch(current_epoch + 1))

    # Set up the 3-epoch window: [prev, curr, next]
    state.ptc_window = prev_epoch_ptc + curr_epoch_ptc + next_epoch_ptc

    # Compute what the new next epoch should be after the shift
    new_next_epoch = spec.Epoch(current_epoch + spec.MIN_SEED_LOOKAHEAD + 1)
    new_next_epoch_ptc = _compute_epoch_ptc(spec, state, new_next_epoch)

    yield from run_epoch_processing_with(spec, state, "process_ptc_window")

    # After shift: [curr, next, new_next]
    SPE = spec.SLOTS_PER_EPOCH
    assert list(state.ptc_window[:SPE]) == curr_epoch_ptc
    assert list(state.ptc_window[SPE : 2 * SPE]) == next_epoch_ptc
    assert list(state.ptc_window[2 * SPE :]) == new_next_epoch_ptc

    # run_epoch_processing_with does not increment the slot, so do it manually
    state.slot += 1

    # Now state_epoch = current_epoch + 1
    # Previous epoch lookup (current_epoch) should hit the first section
    assert spec.get_ptc(state, spec.Slot(state.slot - 1)) == curr_epoch_ptc[-1]
    # Current epoch lookup should hit the second section
    assert spec.get_ptc(state, state.slot) == next_epoch_ptc[0]
