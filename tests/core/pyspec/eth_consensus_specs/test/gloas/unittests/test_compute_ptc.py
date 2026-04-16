from eth_consensus_specs.test.context import (
    single_phase,
    spec_test,
    with_phases,
    with_state,
)
from eth_consensus_specs.test.helpers.constants import GLOAS


@with_phases([GLOAS])
@spec_test
@with_state
@single_phase
def test_compute_ptc_excludes_slashed_validators(spec, state):
    """
    [EIP-8045] ``compute_ptc`` must not include slashed validators in the
    payload timeliness committee for any slot in the current epoch.
    """
    epoch = spec.get_current_epoch(state)
    active = spec.get_active_validator_indices(state, epoch)
    slashed = set(active[: len(active) // 2])
    for validator_index in slashed:
        state.validators[validator_index].slashed = True

    start_slot = spec.compute_start_slot_at_epoch(epoch)
    for slot_offset in range(spec.SLOTS_PER_EPOCH):
        slot = spec.Slot(start_slot + slot_offset)
        ptc = spec.compute_ptc(state, slot)
        for validator_index in ptc:
            assert validator_index not in slashed
            assert not state.validators[validator_index].slashed
