from eth_consensus_specs.test.context import (
    spec_state_test,
    with_all_phases_from_except,
    with_presets,
)
from eth_consensus_specs.test.helpers.constants import ALTAIR, MINIMAL, PQ
from eth_consensus_specs.test.helpers.state import (
    transition_to,
)


@with_all_phases_from_except(ALTAIR, [PQ])
@spec_state_test
def test_get_sync_subcommittee_pubkeys_current_sync_committee(state, spec):
    # Transition to the head of the next period
    transition_to(
        spec, state, spec.SLOTS_PER_EPOCH * spec.Uint64(spec.EPOCHS_PER_SYNC_COMMITTEE_PERIOD)
    )

    next_slot_epoch = spec.compute_epoch_at_slot(state.slot + 1)
    assert spec.compute_sync_committee_period(
        spec.get_current_epoch(state)
    ) == spec.compute_sync_committee_period(next_slot_epoch)
    sync_committee = state.current_sync_committee
    sync_subcommittee_size = spec.SYNC_COMMITTEE_SIZE // spec.SYNC_COMMITTEE_SUBNET_COUNT
    subcommittee_index = 1
    i = subcommittee_index * sync_subcommittee_size

    expect = sync_committee.pubkeys[i : i + sync_subcommittee_size]
    assert spec.get_sync_subcommittee_pubkeys(state, state.slot, subcommittee_index) == expect


@with_all_phases_from_except(ALTAIR, [PQ])
@spec_state_test
def test_get_sync_subcommittee_pubkeys_next_sync_committee(state, spec):
    # Transition to the end of the current period
    transition_to(
        spec, state, spec.SLOTS_PER_EPOCH * spec.Uint64(spec.EPOCHS_PER_SYNC_COMMITTEE_PERIOD) - 1
    )

    next_slot_epoch = spec.compute_epoch_at_slot(state.slot + 1)
    assert spec.compute_sync_committee_period(
        spec.get_current_epoch(state)
    ) != spec.compute_sync_committee_period(next_slot_epoch)
    sync_committee = state.next_sync_committee
    sync_subcommittee_size = spec.SYNC_COMMITTEE_SIZE // spec.SYNC_COMMITTEE_SUBNET_COUNT
    subcommittee_index = 1
    i = subcommittee_index * sync_subcommittee_size

    expect = sync_committee.pubkeys[i : i + sync_subcommittee_size]
    assert spec.get_sync_subcommittee_pubkeys(state, state.slot, subcommittee_index) == expect


@with_all_phases_from_except(ALTAIR, [PQ])
@with_presets([MINIMAL], reason="too slow to reach the second period boundary")
@spec_state_test
def test_get_sync_subcommittee_pubkeys_message_slot_with_stale_head(state, spec):
    period_length = spec.Uint64(spec.EPOCHS_PER_SYNC_COMMITTEE_PERIOD) * spec.SLOTS_PER_EPOCH
    message_slot = 2 * period_length - 1
    transition_to(spec, state, message_slot - 1)
    assert state.current_sync_committee != state.next_sync_committee

    message_committee = state.next_sync_committee.copy()
    subcommittee_size = spec.SYNC_COMMITTEE_SIZE // spec.SYNC_COMMITTEE_SUBNET_COUNT
    for subcommittee_index in range(spec.SYNC_COMMITTEE_SUBNET_COUNT):
        start = subcommittee_index * subcommittee_size
        expected = message_committee.pubkeys[start : start + subcommittee_size]
        assert (
            spec.get_sync_subcommittee_pubkeys(state, message_slot, subcommittee_index) == expected
        )

    # The same message remains timely just after the boundary, when the head can be at B.
    transition_to(spec, state, message_slot + 1)
    assert state.current_sync_committee == message_committee
    for subcommittee_index in range(spec.SYNC_COMMITTEE_SUBNET_COUNT):
        start = subcommittee_index * subcommittee_size
        expected = message_committee.pubkeys[start : start + subcommittee_size]
        assert (
            spec.get_sync_subcommittee_pubkeys(state, message_slot, subcommittee_index) == expected
        )
