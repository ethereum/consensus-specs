from eth2spec.test.context import (
    with_phases,
    spec_state_test,
)
from eth2spec.test.helpers.state import next_epoch
from eth2spec.test.helpers.typing import SpecForkName
SHARDING = SpecForkName("sharding")


@with_phases([SHARDING])
@spec_state_test
def test_get_committee_count_delta(spec, state):
    assert spec.get_committee_count_delta(state, 0, 0) == 0
    assert spec.get_committee_count_per_slot(state, 0) != 0
    assert spec.get_committee_count_delta(state, 0, 1) == spec.get_committee_count_per_slot(
        state, 0
    )
    assert spec.get_committee_count_delta(state, 1, 2) == spec.get_committee_count_per_slot(
        state, 0
    )
    assert (
        spec.get_committee_count_delta(state, 0, 2)
        == spec.get_committee_count_per_slot(state, 0) * 2
    )
    assert spec.get_committee_count_delta(state, 0, spec.SLOTS_PER_EPOCH) == (
        spec.get_committee_count_per_slot(state, 0) * spec.SLOTS_PER_EPOCH
    )
    assert spec.get_committee_count_delta(state, 0, 2 * spec.SLOTS_PER_EPOCH) == (
        spec.get_committee_count_per_slot(state, 0) * spec.SLOTS_PER_EPOCH
        + spec.get_committee_count_per_slot(state, 1) * spec.SLOTS_PER_EPOCH
    )


@with_phases([SHARDING])
@spec_state_test
def test_get_start_shard_current_epoch_start(spec, state):
    assert state.current_epoch_start_shard == 0
    next_epoch(spec, state)
    active_shard_count = spec.get_active_shard_count(state)
    assert state.current_epoch_start_shard == (
        spec.get_committee_count_delta(state, 0, spec.SLOTS_PER_EPOCH) % active_shard_count
    )
    current_epoch_start_slot = spec.compute_start_slot_at_epoch(spec.get_current_epoch(state))

    slot = current_epoch_start_slot
    start_shard = spec.get_start_shard(state, slot)
    assert start_shard == state.current_epoch_start_shard


@with_phases([SHARDING])
@spec_state_test
def test_get_start_shard_next_slot(spec, state):
    next_epoch(spec, state)
    active_shard_count = spec.get_active_shard_count(state)
    current_epoch_start_slot = spec.compute_start_slot_at_epoch(spec.get_current_epoch(state))

    slot = current_epoch_start_slot + 1
    start_shard = spec.get_start_shard(state, slot)

    current_epoch_start_slot = spec.compute_start_slot_at_epoch(spec.get_current_epoch(state))
    expected_start_shard = (
        state.current_epoch_start_shard
        + spec.get_committee_count_delta(state, start_slot=current_epoch_start_slot, stop_slot=slot)
    ) % active_shard_count
    assert start_shard == expected_start_shard


@with_phases([SHARDING])
@spec_state_test
def test_get_start_shard_previous_slot(spec, state):
    next_epoch(spec, state)
    active_shard_count = spec.get_active_shard_count(state)
    current_epoch_start_slot = spec.compute_start_slot_at_epoch(spec.get_current_epoch(state))

    slot = current_epoch_start_slot - 1
    start_shard = spec.get_start_shard(state, slot)

    current_epoch_start_slot = spec.compute_start_slot_at_epoch(spec.get_current_epoch(state))
    expected_start_shard = (
        state.current_epoch_start_shard
        + spec.MAX_COMMITTEES_PER_SLOT * spec.SLOTS_PER_EPOCH * active_shard_count
        - spec.get_committee_count_delta(state, start_slot=slot, stop_slot=current_epoch_start_slot)
    ) % active_shard_count
    assert start_shard == expected_start_shard


@with_phases([SHARDING])
@spec_state_test
def test_get_start_shard_far_past_epoch(spec, state):
    initial_epoch = spec.get_current_epoch(state)
    initial_start_slot = spec.compute_start_slot_at_epoch(initial_epoch)
    initial_start_shard = state.current_epoch_start_shard

    for _ in range(spec.MAX_SHARDS + 2):
        next_epoch(spec, state)

    assert spec.get_start_shard(state, initial_start_slot) == initial_start_shard
