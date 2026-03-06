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
def test_process_ptc_lookbehind_rotates_to_next_epoch(spec, state):
    spec.process_slots(state, state.slot + spec.SLOTS_PER_EPOCH - 1)

    current_epoch = spec.get_current_epoch(state)
    current_epoch_ptc = _compute_epoch_ptc(spec, state, current_epoch)
    state.ptc_lookbehind = current_epoch_ptc + current_epoch_ptc

    next_epoch = spec.Epoch(current_epoch + 1)
    next_epoch_ptc = _compute_epoch_ptc(spec, state, next_epoch)

    yield from run_epoch_processing_with(spec, state, "process_ptc_lookbehind")

    assert list(state.ptc_lookbehind[: spec.SLOTS_PER_EPOCH]) == current_epoch_ptc
    assert list(state.ptc_lookbehind[spec.SLOTS_PER_EPOCH :]) == next_epoch_ptc

    # run_epoch_processing_with does not increment the slot
    state.slot += 1

    assert spec.get_ptc(state, spec.Slot(state.slot - 1)) == current_epoch_ptc[-1]
    assert spec.get_ptc(state, state.slot) == next_epoch_ptc[0]
