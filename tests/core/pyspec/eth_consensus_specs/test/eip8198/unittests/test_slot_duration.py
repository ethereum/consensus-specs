"""
Unit tests for the EIP-8198 piecewise time functions, run with
``EIP8198_FORK_EPOCH`` overridden to a small epoch so that the fork-boundary
branches are actually exercised (with the default FAR_FUTURE_EPOCH they are
unreachable).

All assertions are written in terms of the config values so they hold on both
presets (minimal: 6000ms -> 5000ms, mainnet: 12000ms -> 10000ms).
"""

from eth_consensus_specs.test.context import (
    spec_configured_state_test,
    with_phases,
)
from eth_consensus_specs.test.helpers.constants import EIP8198
from eth_consensus_specs.test.helpers.fork_choice import get_genesis_forkchoice_store
from eth_consensus_specs.test.helpers.state import next_epoch

FORK_EPOCH = 2
FORK_EPOCH_OVERRIDE = {"EIP8198_FORK_EPOCH": FORK_EPOCH}


def _fork_params(spec, genesis_time):
    fork_slot = FORK_EPOCH * spec.SLOTS_PER_EPOCH
    pre_ms = spec.config.SLOT_DURATION_MS
    post_ms = spec.config.SLOT_DURATION_MS_EIP8198
    fork_time = genesis_time + fork_slot * pre_ms // 1000
    return fork_slot, pre_ms, post_ms, fork_time


@with_phases([EIP8198])
@spec_configured_state_test(FORK_EPOCH_OVERRIDE)
def test_get_slot_from_time_across_fork(spec, state):
    store = get_genesis_forkchoice_store(spec, state)
    fork_slot, _, post_ms, fork_time = _fork_params(spec, store.genesis_time)

    # Pre-fork times map at the old duration
    assert spec.get_slot_from_time(store, store.genesis_time) == 0
    assert spec.get_slot_from_time(store, fork_time - 1) == fork_slot - 1
    # The fork boundary is the start of the fork slot
    assert spec.get_slot_from_time(store, fork_time) == fork_slot
    # Post-fork times map at the new duration, rebased on the fork time
    assert spec.get_slot_from_time(store, fork_time + post_ms // 1000 - 1) == fork_slot
    for k in range(1, 3 * spec.SLOTS_PER_EPOCH):
        assert spec.get_slot_from_time(store, fork_time + k * post_ms // 1000) == fork_slot + k


@with_phases([EIP8198])
@spec_configured_state_test(FORK_EPOCH_OVERRIDE)
def test_get_time_at_slot_end_across_fork(spec, state):
    store = get_genesis_forkchoice_store(spec, state)
    fork_slot, _, post_ms, fork_time = _fork_params(spec, store.genesis_time)

    # The last pre-fork slot ends exactly at the fork time
    assert spec.get_time_at_slot_end(store, spec.Slot(fork_slot - 1)) == fork_time
    # The first post-fork slot lasts the new duration
    assert spec.get_time_at_slot_end(store, spec.Slot(fork_slot)) == fork_time + post_ms // 1000
    # Round trip: the end of slot s is the start of slot s + 1
    for s in range(3 * spec.SLOTS_PER_EPOCH):
        slot_end = spec.get_time_at_slot_end(store, spec.Slot(s))
        assert spec.get_slot_from_time(store, slot_end) == s + 1


@with_phases([EIP8198])
@spec_configured_state_test(FORK_EPOCH_OVERRIDE)
def test_get_time_into_slot_ms_across_fork(spec, state):
    store = get_genesis_forkchoice_store(spec, state)
    _, pre_ms, post_ms, fork_time = _fork_params(spec, store.genesis_time)

    # Zero at every slot start, before and after the fork
    for s in range(3 * spec.SLOTS_PER_EPOCH):
        store.time = spec.get_time_at_slot_end(store, spec.Slot(s))
        assert spec.get_time_into_slot_ms(store) == 0

    # Just before the fork: one second before the end of the last pre-fork slot
    store.time = fork_time - 1
    assert spec.get_time_into_slot_ms(store) == pre_ms - 1000

    # Post-fork: offsets are taken modulo the new duration, rebased on the
    # fork time (the old genesis-anchored modulo would give a different value)
    seconds_into_slot = post_ms // 1000 - 1
    store.time = fork_time + seconds_into_slot
    assert spec.get_time_into_slot_ms(store) == seconds_into_slot * 1000
    store.time = fork_time + post_ms // 1000 + seconds_into_slot
    assert spec.get_time_into_slot_ms(store) == seconds_into_slot * 1000


@with_phases([EIP8198])
@spec_configured_state_test(FORK_EPOCH_OVERRIDE)
def test_compute_time_at_slot_across_fork(spec, state):
    fork_slot, pre_ms, post_ms, fork_time = _fork_params(spec, state.genesis_time)

    # Pre-fork slots at the old duration, post-fork slots at the new one
    for s in range(fork_slot + 1):
        assert spec.compute_time_at_slot(state, spec.Slot(s)) == (
            state.genesis_time + s * pre_ms // 1000
        )
    for k in range(1, 3 * spec.SLOTS_PER_EPOCH):
        assert spec.compute_time_at_slot(state, spec.Slot(fork_slot + k)) == (
            fork_time + k * post_ms // 1000
        )

    # Consistency with the fork choice mapping: the timestamp of slot s + 1 is
    # the end of slot s
    store = get_genesis_forkchoice_store(spec, state)
    for s in range(3 * spec.SLOTS_PER_EPOCH):
        assert spec.compute_time_at_slot(state, spec.Slot(s + 1)) == spec.get_time_at_slot_end(
            store, spec.Slot(s)
        )


@with_phases([EIP8198])
@spec_configured_state_test(FORK_EPOCH_OVERRIDE)
def test_get_forkchoice_store_post_fork_anchor(spec, state):
    fork_slot, _, post_ms, fork_time = _fork_params(spec, state.genesis_time)

    # Advance the anchor state past the fork epoch
    for _ in range(FORK_EPOCH + 1):
        next_epoch(spec, state)
    assert state.slot > fork_slot

    anchor_block = spec.BeaconBlock(slot=state.slot, state_root=state.hash_tree_root())
    store = spec.get_forkchoice_store(state, anchor_block)

    expected = fork_time + (state.slot - fork_slot) * post_ms // 1000
    assert store.time == expected
    assert store.time == spec.compute_time_at_slot(state, state.slot)
    assert spec.get_current_slot(store) == state.slot


@with_phases([EIP8198])
@spec_configured_state_test(FORK_EPOCH_OVERRIDE)
def test_compute_time_at_slot_ms_across_fork(spec, state):
    fork_slot, pre_ms, post_ms, _ = _fork_params(spec, state.genesis_time)
    fork_time_ms = state.genesis_time * 1000 + fork_slot * pre_ms

    for s in range(fork_slot + 1):
        assert spec.compute_time_at_slot_ms(state, spec.Slot(s)) == (
            state.genesis_time * 1000 + s * pre_ms
        )
    for k in range(1, 3 * spec.SLOTS_PER_EPOCH):
        assert spec.compute_time_at_slot_ms(state, spec.Slot(fork_slot + k)) == (
            fork_time_ms + k * post_ms
        )

    # Consistency with the second-granularity mapping
    for s in range(3 * spec.SLOTS_PER_EPOCH):
        assert spec.compute_time_at_slot_ms(state, spec.Slot(s)) == (
            spec.compute_time_at_slot(state, spec.Slot(s)) * 1000
        )


@with_phases([EIP8198])
@spec_configured_state_test(FORK_EPOCH_OVERRIDE)
def test_gossip_slot_gates_across_fork(spec, state):
    fork_slot, pre_ms, post_ms, _ = _fork_params(spec, state.genesis_time)
    disparity = spec.config.MAXIMUM_GOSSIP_CLOCK_DISPARITY

    # Wall-clock "now": one second into the third post-fork slot (strictly
    # inside the slot, beyond the disparity allowance, so no boundary case is
    # ambiguous)
    assert disparity < 1000
    now_ms = state.genesis_time * 1000 + fork_slot * pre_ms + 3 * post_ms + 1000
    current_slot = spec.Slot(fork_slot + 3)

    # A message for the current slot is not from the future. With the
    # genesis-anchored formula the computed slot start would be
    # 3 * (pre_ms - post_ms) later than the actual one, exceeding the clock
    # disparity allowance and wrongly rejecting the message.
    assert 3 * (pre_ms - post_ms) > disparity
    assert spec.is_not_from_future_slot(state, current_slot, now_ms)
    # A message one slot ahead is from the future
    assert not spec.is_not_from_future_slot(state, spec.Slot(current_slot + 1), now_ms)

    # A slot range straddling the fork boundary: [fork_slot - 2, fork_slot + 2]
    for slot in range(fork_slot - 2, fork_slot + 3):
        assert spec.is_within_slot_range(state, spec.Slot(slot), spec.Uint64(4), now_ms) == (
            slot + 4 >= current_slot
        )


@with_phases([EIP8198])
@spec_configured_state_test(FORK_EPOCH_OVERRIDE)
def test_compute_fork_version_at_fork(spec, state):
    assert spec.compute_fork_version(spec.Epoch(FORK_EPOCH)) == spec.EIP8198_FORK_VERSION
    assert spec.compute_fork_version(spec.Epoch(FORK_EPOCH - 1)) != spec.EIP8198_FORK_VERSION


@with_phases([EIP8198])
@spec_configured_state_test(FORK_EPOCH_OVERRIDE)
def test_on_tick_across_fork(spec, state):
    store = get_genesis_forkchoice_store(spec, state)
    fork_slot, _, post_ms, fork_time = _fork_params(spec, store.genesis_time)

    # Tick from genesis to a few slots past the fork in one call; the catch-up
    # loop must process every slot boundary at its correct wall-clock time
    spec.on_tick(store, fork_time + 3 * post_ms // 1000)
    assert spec.get_current_slot(store) == fork_slot + 3
    assert spec.get_time_into_slot_ms(store) == 0
