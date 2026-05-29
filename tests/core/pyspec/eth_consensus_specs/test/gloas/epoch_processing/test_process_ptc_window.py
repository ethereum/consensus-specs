from eth_consensus_specs.test.context import (
    single_phase,
    spec_state_test,
    with_phases,
)
from eth_consensus_specs.test.helpers.constants import GLOAS
from eth_consensus_specs.test.helpers.epoch_processing import run_epoch_processing_with


@with_phases([GLOAS])
@spec_state_test
@single_phase
def test_process_ptc_window__shifts_all_epochs(spec, state):
    """
    Verify that process_ptc_window shifts prev/curr/next correctly
    and that get_ptc returns the right committees afterwards.
    """
    spec.process_slots(state, state.slot + 2 * spec.SLOTS_PER_EPOCH - 1)

    SPE = spec.SLOTS_PER_EPOCH
    # Save current and next epoch sections before the shift
    curr_epoch_ptc = list(state.ptc_window[SPE : 2 * SPE])
    next_epoch_ptc = list(state.ptc_window[2 * SPE : 3 * SPE])

    yield from run_epoch_processing_with(spec, state, "process_ptc_window")

    # After shift: [curr, next, new_next]
    assert list(state.ptc_window[:SPE]) == curr_epoch_ptc
    assert list(state.ptc_window[SPE : 2 * SPE]) == next_epoch_ptc

    # run_epoch_processing_with does not increment the slot, so do it manually
    state.slot += 1

    # Now state_epoch = current_epoch + 1
    # Previous epoch lookup (current_epoch) should hit the first section
    assert spec.get_ptc(state, spec.Slot(state.slot - 1)) == curr_epoch_ptc[-1]
    # Current epoch lookup should hit the second section
    assert spec.get_ptc(state, state.slot) == next_epoch_ptc[0]
