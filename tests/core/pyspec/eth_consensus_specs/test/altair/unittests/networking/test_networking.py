from eth_consensus_specs.test.context import (
    spec_state_test,
    with_altair_and_later,
)
from eth_consensus_specs.test.helpers.state import (
    transition_to,
)


@with_altair_and_later
@spec_state_test
def test_get_sync_subcommittee_pubkeys_current_sync_committee(state, spec):
    # Transition to the head of the next period
    transition_to(spec, state, spec.SLOTS_PER_EPOCH * spec.EPOCHS_PER_SYNC_COMMITTEE_PERIOD)

    next_slot_epoch = spec.compute_epoch_at_slot(state.slot + 1)
    assert spec.compute_sync_committee_period(
        spec.get_current_epoch(state)
    ) == spec.compute_sync_committee_period(next_slot_epoch)
    sync_committee = state.current_sync_committee
    sync_subcommittee_size = spec.SYNC_COMMITTEE_SIZE // spec.SYNC_COMMITTEE_SUBNET_COUNT
    subcommittee_index = 1
    i = subcommittee_index * sync_subcommittee_size

    expect = sync_committee.pubkeys[i : i + sync_subcommittee_size]
    assert spec.get_sync_subcommittee_pubkeys(state, subcommittee_index) == expect


@with_altair_and_later
@spec_state_test
def test_get_sync_subcommittee_pubkeys_next_sync_committee(state, spec):
    # Transition to the end of the current period
    transition_to(spec, state, spec.SLOTS_PER_EPOCH * spec.EPOCHS_PER_SYNC_COMMITTEE_PERIOD - 1)

    next_slot_epoch = spec.compute_epoch_at_slot(state.slot + 1)
    assert spec.compute_sync_committee_period(
        spec.get_current_epoch(state)
    ) != spec.compute_sync_committee_period(next_slot_epoch)
    sync_committee = state.next_sync_committee
    sync_subcommittee_size = spec.SYNC_COMMITTEE_SIZE // spec.SYNC_COMMITTEE_SUBNET_COUNT
    subcommittee_index = 1
    i = subcommittee_index * sync_subcommittee_size

    expect = sync_committee.pubkeys[i : i + sync_subcommittee_size]
    assert spec.get_sync_subcommittee_pubkeys(state, subcommittee_index) == expect
