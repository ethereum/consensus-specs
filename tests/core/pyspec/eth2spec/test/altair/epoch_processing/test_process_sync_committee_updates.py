from eth2spec.test.context import (
    spec_state_test,
    spec_test,
    with_all_phases_except,
    with_configs,
    with_custom_state,
    single_phase,
    misc_balances,
)
from eth2spec.test.helpers.constants import (
    PHASE0,
    MINIMAL,
)
from eth2spec.test.helpers.state import transition_to
from eth2spec.test.helpers.epoch_processing import (
    run_epoch_processing_with,
)


def run_sync_committees_progress_test(spec, state):
    first_sync_committee = state.current_sync_committee
    second_sync_committee = state.next_sync_committee

    end_slot_of_current_period = state.slot + spec.EPOCHS_PER_SYNC_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH - 1
    transition_to(spec, state, end_slot_of_current_period)

    # Ensure assignments have not changed:
    assert state.current_sync_committee == first_sync_committee
    assert state.next_sync_committee == second_sync_committee

    yield from run_epoch_processing_with(spec, state, 'process_sync_committee_updates')

    # Can compute the third committee having computed final balances in the last epoch
    # of this `EPOCHS_PER_SYNC_COMMITTEE_PERIOD`
    current_epoch = spec.get_current_epoch(state)
    third_sync_committee = spec.get_sync_committee(state, current_epoch + 2 * spec.EPOCHS_PER_SYNC_COMMITTEE_PERIOD)

    assert state.current_sync_committee == second_sync_committee
    assert state.next_sync_committee == third_sync_committee


@with_all_phases_except([PHASE0])
@spec_state_test
@with_configs([MINIMAL], reason="too slow")
def test_sync_committees_progress_genesis(spec, state):
    # Genesis epoch period has an exceptional case
    spec.get_current_epoch(state)
    assert spec.get_current_epoch(state) == spec.GENESIS_EPOCH

    yield from run_sync_committees_progress_test(spec, state)


@with_all_phases_except([PHASE0])
@spec_state_test
@with_configs([MINIMAL], reason="too slow")
def test_sync_committees_progress_not_genesis(spec, state):
    # Transition out of the genesis epoch period to test non-exceptional case
    start_slot_of_next_period = state.slot + spec.EPOCHS_PER_SYNC_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH
    transition_to(spec, state, start_slot_of_next_period)

    yield from run_sync_committees_progress_test(spec, state)


@with_all_phases_except([PHASE0])
@with_custom_state(balances_fn=misc_balances, threshold_fn=lambda spec: spec.EJECTION_BALANCE)
@spec_test
@single_phase
@with_configs([MINIMAL], reason="too slow")
def test_sync_committees_progress_misc_balances(spec, state):
    yield from run_sync_committees_progress_test(spec, state)
