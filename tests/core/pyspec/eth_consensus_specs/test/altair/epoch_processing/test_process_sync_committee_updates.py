from eth_consensus_specs.test.context import (
    always_bls,
    misc_balances,
    single_phase,
    spec_state_test,
    spec_test,
    with_altair_and_later,
    with_custom_state,
    with_presets,
)
from eth_consensus_specs.test.helpers.constants import MINIMAL
from eth_consensus_specs.test.helpers.epoch_processing import (
    run_epoch_processing_with,
)
from eth_consensus_specs.test.helpers.state import transition_to

#
# Note:
# Calculating sync committees requires pubkey aggregation, thus all tests are generated with `always_bls`
#


def run_sync_committees_progress_test(spec, state):
    first_sync_committee = state.current_sync_committee.copy()
    second_sync_committee = state.next_sync_committee.copy()

    current_period = spec.compute_sync_committee_period(spec.get_current_epoch(state))
    next_period = current_period + 1
    next_period_start_epoch = next_period * spec.EPOCHS_PER_SYNC_COMMITTEE_PERIOD
    next_period_start_slot = next_period_start_epoch * spec.SLOTS_PER_EPOCH
    end_slot_of_current_period = next_period_start_slot - 1
    transition_to(spec, state, end_slot_of_current_period)

    # Ensure assignments have not changed:
    assert state.current_sync_committee == first_sync_committee
    assert state.next_sync_committee == second_sync_committee

    yield from run_epoch_processing_with(spec, state, "process_sync_committee_updates")

    # Can compute the third committee having computed final balances in the last epoch
    # of this `EPOCHS_PER_SYNC_COMMITTEE_PERIOD`
    third_sync_committee = spec.get_next_sync_committee(state)

    # Ensure assignments have changed:
    assert state.next_sync_committee != second_sync_committee
    if current_period > 0:
        assert state.current_sync_committee != first_sync_committee
    else:
        # Current and next are duplicated in genesis period so remain stable
        assert state.current_sync_committee == first_sync_committee

    # Ensure expected committees were calculated
    assert state.current_sync_committee == second_sync_committee
    assert state.next_sync_committee == third_sync_committee


@with_altair_and_later
@spec_state_test
@always_bls
@with_presets([MINIMAL], reason="too slow")
def test_sync_committees_progress_genesis(spec, state):
    # Genesis epoch period has an exceptional case
    assert spec.get_current_epoch(state) == spec.GENESIS_EPOCH

    yield from run_sync_committees_progress_test(spec, state)


@with_altair_and_later
@spec_state_test
@always_bls
@with_presets([MINIMAL], reason="too slow")
def test_sync_committees_progress_not_genesis(spec, state):
    # Transition out of the genesis epoch period to test non-exceptional case
    assert spec.get_current_epoch(state) == spec.GENESIS_EPOCH
    slot_in_next_period = state.slot + spec.EPOCHS_PER_SYNC_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH
    transition_to(spec, state, slot_in_next_period)

    yield from run_sync_committees_progress_test(spec, state)


@with_altair_and_later
@with_custom_state(
    balances_fn=misc_balances, threshold_fn=lambda spec: spec.config.EJECTION_BALANCE
)
@spec_test
@single_phase
@always_bls
@with_presets([MINIMAL], reason="too slow")
def test_sync_committees_progress_misc_balances_genesis(spec, state):
    # Genesis epoch period has an exceptional case
    assert spec.get_current_epoch(state) == spec.GENESIS_EPOCH

    yield from run_sync_committees_progress_test(spec, state)


@with_altair_and_later
@with_custom_state(
    balances_fn=misc_balances, threshold_fn=lambda spec: spec.config.EJECTION_BALANCE
)
@spec_test
@single_phase
@always_bls
@with_presets([MINIMAL], reason="too slow")
def test_sync_committees_progress_misc_balances_not_genesis(spec, state):
    # Transition out of the genesis epoch period to test non-exceptional case
    assert spec.get_current_epoch(state) == spec.GENESIS_EPOCH
    slot_in_next_period = state.slot + spec.EPOCHS_PER_SYNC_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH
    transition_to(spec, state, slot_in_next_period)

    yield from run_sync_committees_progress_test(spec, state)


@with_altair_and_later
@spec_state_test
@always_bls
@with_presets([MINIMAL], reason="too slow")
def test_sync_committees_no_progress_not_at_period_boundary(spec, state):
    assert spec.get_current_epoch(state) == spec.GENESIS_EPOCH
    slot_not_at_period_boundary = state.slot + spec.SLOTS_PER_EPOCH
    transition_to(spec, state, slot_not_at_period_boundary)

    first_sync_committee = state.current_sync_committee.copy()
    second_sync_committee = state.next_sync_committee.copy()

    yield from run_epoch_processing_with(spec, state, "process_sync_committee_updates")

    # Ensure assignments have not changed:
    assert state.current_sync_committee == first_sync_committee
    assert state.next_sync_committee == second_sync_committee
