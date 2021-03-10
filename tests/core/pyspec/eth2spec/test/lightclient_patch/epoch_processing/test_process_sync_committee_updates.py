from eth2spec.test.context import (
    PHASE0, PHASE1,
    with_all_phases_except,
    spec_state_test,
)
from eth2spec.test.helpers.state import transition_to
from eth2spec.test.helpers.epoch_processing import (
    run_epoch_processing_with,
)


@with_all_phases_except([PHASE0, PHASE1])
@spec_state_test
def test_sync_committees_progress(spec, state):
    current_epoch = spec.get_current_epoch(state)
    # NOTE: if not in the genesis epoch, period math below needs to be
    # adjusted relative to the current epoch
    assert current_epoch == 0

    first_sync_committee = state.current_sync_committee
    second_sync_committee = state.next_sync_committee

    slot_at_end_of_current_period = spec.EPOCHS_PER_SYNC_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH - 1
    transition_to(spec, state, slot_at_end_of_current_period)

    # Ensure assignments have not changed:
    assert state.current_sync_committee == first_sync_committee
    assert state.next_sync_committee == second_sync_committee

    yield from run_epoch_processing_with(spec, state, 'process_sync_committee_updates')

    # Can compute the third committee having computed final balances in the last epoch
    # of this `EPOCHS_PER_SYNC_COMMITTEE_PERIOD`
    third_sync_committee = spec.get_sync_committee(state, 2 * spec.EPOCHS_PER_SYNC_COMMITTEE_PERIOD)

    assert state.current_sync_committee == second_sync_committee
    assert state.next_sync_committee == third_sync_committee
