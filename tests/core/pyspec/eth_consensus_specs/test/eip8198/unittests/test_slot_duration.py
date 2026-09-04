"""
Unit tests for the EIP-8198 slot duration schedule and piecewise time
functions, using config overrides that activate a schedule entry.
"""

from eth_consensus_specs.test.context import (
    single_phase,
    spec_configured_state_test,
    spec_test,
    with_config_overrides,
    with_phases,
    with_presets,
)
from eth_consensus_specs.test.helpers.attestations import (
    get_parent_slot,
    get_valid_attestation,
    process_attestation,
)
from eth_consensus_specs.test.helpers.constants import EIP8198, MINIMAL
from eth_consensus_specs.test.helpers.eip8198.schedule import slot_duration_schedule_entry
from eth_consensus_specs.test.helpers.fork_choice import get_genesis_forkchoice_store
from eth_consensus_specs.test.helpers.state import next_epoch

FORK_EPOCH = 2
POST_DURATION_MS = 5000
FORK_EPOCH_OVERRIDE = {
    "EIP8198_FORK_EPOCH": FORK_EPOCH,
    "SLOT_DURATION_SCHEDULE": (
        slot_duration_schedule_entry(0, 6000),
        slot_duration_schedule_entry(FORK_EPOCH, POST_DURATION_MS),
    ),
}
EARLY_SCHEDULE_OVERRIDE = {
    "EIP8198_FORK_EPOCH": 0,
    "SLOT_DURATION_SCHEDULE": (
        slot_duration_schedule_entry(0, 6000),
        slot_duration_schedule_entry(1, POST_DURATION_MS),
    ),
}
SECOND_FORK_EPOCH = 4
SECOND_POST_DURATION_MS = 3000
TWO_ERA_OVERRIDE = {
    "EIP8198_FORK_EPOCH": FORK_EPOCH,
    "SLOT_DURATION_SCHEDULE": (
        slot_duration_schedule_entry(0, 6000),
        slot_duration_schedule_entry(FORK_EPOCH, POST_DURATION_MS),
        slot_duration_schedule_entry(SECOND_FORK_EPOCH, SECOND_POST_DURATION_MS),
    ),
}


def _fork_params(spec, genesis_time):
    fork_slot = FORK_EPOCH * spec.SLOTS_PER_EPOCH
    pre_ms = spec.get_slot_duration_ms(spec.GENESIS_EPOCH)
    post_ms = spec.get_slot_duration_ms(spec.Epoch(FORK_EPOCH))
    fork_time = genesis_time + fork_slot * pre_ms // 1000
    fork_time_ms = genesis_time * 1000 + fork_slot * pre_ms
    return fork_slot, pre_ms, post_ms, fork_time, fork_time_ms


@with_phases([EIP8198])
@spec_configured_state_test(FORK_EPOCH_OVERRIDE, activate_at_genesis=True)
def test_get_slot_duration_ms(spec, state):
    pre_ms = spec.get_slot_duration_ms(spec.GENESIS_EPOCH)
    assert spec.get_slot_duration_ms(spec.Epoch(0)) == pre_ms
    assert spec.get_slot_duration_ms(spec.Epoch(FORK_EPOCH - 1)) == pre_ms
    assert spec.get_slot_duration_ms(spec.Epoch(FORK_EPOCH)) == POST_DURATION_MS
    assert spec.get_slot_duration_ms(spec.Epoch(FORK_EPOCH + 100)) == POST_DURATION_MS


@with_phases([EIP8198])
@spec_configured_state_test(FORK_EPOCH_OVERRIDE, activate_at_genesis=True)
def test_get_slot_from_time_ms_across_fork(spec, state):
    store = get_genesis_forkchoice_store(spec, state)
    fork_slot, _, post_ms, _, fork_time_ms = _fork_params(spec, store.genesis_time)

    # Pre-fork times map at the old duration
    assert spec.get_slot_from_time_ms(store, store.genesis_time * 1000) == 0
    assert spec.get_slot_from_time_ms(store, fork_time_ms - 1) == fork_slot - 1
    # The fork boundary is the start of the fork slot
    assert spec.get_slot_from_time_ms(store, fork_time_ms) == fork_slot
    # Post-fork times map at the new duration, rebased on the fork time
    for k in range(1, 3 * spec.SLOTS_PER_EPOCH):
        assert spec.get_slot_from_time_ms(store, fork_time_ms + k * post_ms) == fork_slot + k
        assert (
            spec.get_slot_from_time_ms(store, fork_time_ms + k * post_ms - 1) == fork_slot + k - 1
        )


@with_phases([EIP8198])
@spec_configured_state_test(TWO_ERA_OVERRIDE, activate_at_genesis=True)
def test_timeline_across_two_eras(spec, state):
    pre_ms = spec.get_slot_duration_ms(spec.GENESIS_EPOCH)
    first_slot = FORK_EPOCH * spec.SLOTS_PER_EPOCH
    second_slot = SECOND_FORK_EPOCH * spec.SLOTS_PER_EPOCH
    genesis_time_ms = state.genesis_time * 1000

    assert spec.get_slot_duration_ms(spec.Epoch(FORK_EPOCH)) == POST_DURATION_MS
    assert spec.get_slot_duration_ms(spec.Epoch(SECOND_FORK_EPOCH)) == SECOND_POST_DURATION_MS

    first_time_ms = genesis_time_ms + first_slot * pre_ms
    second_time_ms = first_time_ms + (second_slot - first_slot) * POST_DURATION_MS
    assert spec.compute_slot_start_time_ms(state.genesis_time, spec.Slot(first_slot)) == (
        first_time_ms
    )
    assert spec.compute_slot_start_time_ms(state.genesis_time, spec.Slot(second_slot)) == (
        second_time_ms
    )
    assert spec.compute_slot_start_time_ms(state.genesis_time, spec.Slot(second_slot + 7)) == (
        second_time_ms + 7 * SECOND_POST_DURATION_MS
    )

    # Round trip across both boundaries, at slot starts and strictly inside
    for slot in range(second_slot + 2 * spec.SLOTS_PER_EPOCH):
        start_ms = spec.compute_slot_start_time_ms(state.genesis_time, spec.Slot(slot))
        assert spec.compute_slot_at_time_ms(state.genesis_time, start_ms) == slot
        assert spec.compute_slot_at_time_ms(state.genesis_time, spec.Uint64(start_ms + 1)) == slot
        if slot > 0:
            assert spec.compute_slot_at_time_ms(state.genesis_time, spec.Uint64(start_ms - 1)) == (
                slot - 1
            )

    # The catch-up loop crosses both boundaries with the right timestamps
    store = get_genesis_forkchoice_store(spec, state)
    spec.on_tick_ms(store, second_time_ms + 3 * SECOND_POST_DURATION_MS)
    assert spec.get_current_slot(store) == second_slot + 3
    assert spec.get_time_into_slot_ms(store) == 0

    # Deadlines follow the schedule entry of the given slot; pre-schedule
    # slots keep the inherited basis-point deadline
    _, first_entry, second_entry = spec.config.SLOT_DURATION_SCHEDULE
    assert spec.get_attestation_due_ms(spec.Slot(first_slot - 1)) == (
        spec.config.ATTESTATION_DUE_BPS_GLOAS * pre_ms // spec.BASIS_POINTS
    )
    assert spec.get_attestation_due_ms(spec.Slot(first_slot)) == first_entry["ATTESTATION_DUE_MS"]
    assert (
        spec.get_attestation_due_ms(spec.Slot(second_slot)) == (second_entry["ATTESTATION_DUE_MS"])
    )


@with_phases([EIP8198])
@spec_configured_state_test(FORK_EPOCH_OVERRIDE, activate_at_genesis=True)
def test_optimistic_sync_current_slot_across_fork(spec, state):
    fork_slot, _, post_ms, _, fork_time_ms = _fork_params(spec, state.genesis_time)

    # The optimistic-sync current-slot gate uses the canonical inverse mapping.
    for k in range(1, 3 * spec.SLOTS_PER_EPOCH):
        current_time_ms = fork_time_ms + k * post_ms
        assert spec.compute_slot_at_time_ms(state.genesis_time, current_time_ms) == fork_slot + k


@with_phases([EIP8198])
@spec_configured_state_test(FORK_EPOCH_OVERRIDE, activate_at_genesis=True)
def test_get_time_at_slot_end_ms_across_fork(spec, state):
    store = get_genesis_forkchoice_store(spec, state)
    fork_slot, _, post_ms, _, fork_time_ms = _fork_params(spec, store.genesis_time)

    # The last pre-fork slot ends exactly at the fork time
    assert spec.get_time_at_slot_end_ms(store, spec.Slot(fork_slot - 1)) == fork_time_ms
    # The first post-fork slot lasts the new duration
    assert spec.get_time_at_slot_end_ms(store, spec.Slot(fork_slot)) == fork_time_ms + post_ms
    # Round trip: the end of slot s is the start of slot s + 1
    for s in range(3 * spec.SLOTS_PER_EPOCH):
        slot_end_ms = spec.get_time_at_slot_end_ms(store, spec.Slot(s))
        assert spec.get_slot_from_time_ms(store, slot_end_ms) == s + 1


@with_phases([EIP8198])
@spec_configured_state_test(FORK_EPOCH_OVERRIDE, activate_at_genesis=True)
def test_get_time_into_slot_ms_across_fork(spec, state):
    store = get_genesis_forkchoice_store(spec, state)
    _, pre_ms, post_ms, fork_time, fork_time_ms = _fork_params(spec, store.genesis_time)

    # Zero at every slot start, before and after the fork
    for s in range(3 * spec.SLOTS_PER_EPOCH):
        store.time_ms = spec.get_time_at_slot_end_ms(store, spec.Slot(s))
        assert spec.get_time_into_slot_ms(store) == 0

    # Just before the fork: one second before the end of the last pre-fork slot
    store.time_ms = (fork_time - 1) * 1000
    assert spec.get_time_into_slot_ms(store) == pre_ms - 1000

    # Post-fork offsets are rebased on the fork time, not genesis
    seconds_into_slot = post_ms // 1000 - 1
    store.time_ms = fork_time_ms + seconds_into_slot * 1000
    assert spec.get_time_into_slot_ms(store) == seconds_into_slot * 1000
    store.time_ms = fork_time_ms + post_ms + seconds_into_slot * 1000
    assert spec.get_time_into_slot_ms(store) == seconds_into_slot * 1000

    # Millisecond precision is retained within a post-fork slot.
    store.time_ms = fork_time_ms + post_ms + 1234
    assert spec.get_time_into_slot_ms(store) == 1234


@with_phases([EIP8198])
@spec_configured_state_test(FORK_EPOCH_OVERRIDE, activate_at_genesis=True)
def test_compute_time_at_slot_across_fork(spec, state):
    fork_slot, pre_ms, post_ms, fork_time, _ = _fork_params(spec, state.genesis_time)

    # Pre-fork slots at the old duration, post-fork slots at the new one
    for s in range(fork_slot + 1):
        assert spec.compute_time_at_slot(state, spec.Slot(s)) == (
            state.genesis_time + s * pre_ms // 1000
        )
    for k in range(1, 3 * spec.SLOTS_PER_EPOCH):
        assert spec.compute_time_at_slot(state, spec.Slot(fork_slot + k)) == (
            fork_time + k * post_ms // 1000
        )

    # Exactness of second-granularity times at every slot boundary
    store = get_genesis_forkchoice_store(spec, state)
    for s in range(3 * spec.SLOTS_PER_EPOCH):
        assert spec.compute_time_at_slot(state, spec.Slot(s + 1)) * 1000 == (
            spec.get_time_at_slot_end_ms(store, spec.Slot(s))
        )


@with_phases([EIP8198])
@spec_configured_state_test(FORK_EPOCH_OVERRIDE, activate_at_genesis=True)
def test_get_forkchoice_store_post_fork_anchor(spec, state):
    fork_slot, _, post_ms, _, fork_time_ms = _fork_params(spec, state.genesis_time)

    # Advance the anchor state past the fork epoch
    for _ in range(FORK_EPOCH + 1):
        next_epoch(spec, state)
    assert state.slot > fork_slot

    anchor_block = spec.BeaconBlock(slot=state.slot, state_root=state.hash_tree_root())
    store = spec.get_forkchoice_store(state, anchor_block)

    assert store.time_ms == fork_time_ms + (state.slot - fork_slot) * post_ms
    assert store.time_ms == spec.compute_time_at_slot_ms(store, state.slot)
    assert spec.get_current_slot(store) == state.slot


@with_phases([EIP8198])
@spec_configured_state_test(FORK_EPOCH_OVERRIDE, activate_at_genesis=True)
def test_compute_time_at_slot_ms_across_fork(spec, state):
    store = get_genesis_forkchoice_store(spec, state)
    fork_slot, pre_ms, post_ms, _, fork_time_ms = _fork_params(spec, state.genesis_time)

    for s in range(fork_slot + 1):
        assert spec.compute_time_at_slot_ms(store, spec.Slot(s)) == (
            state.genesis_time * 1000 + s * pre_ms
        )
    for k in range(1, 3 * spec.SLOTS_PER_EPOCH):
        assert spec.compute_time_at_slot_ms(store, spec.Slot(fork_slot + k)) == (
            fork_time_ms + k * post_ms
        )

    # Consistency with the second-granularity mapping
    for s in range(3 * spec.SLOTS_PER_EPOCH):
        assert spec.compute_time_at_slot_ms(store, spec.Slot(s)) == (
            spec.compute_time_at_slot(state, spec.Slot(s)) * 1000
        )


@with_phases([EIP8198])
@spec_configured_state_test(FORK_EPOCH_OVERRIDE, activate_at_genesis=True)
def test_gossip_slot_gates_across_fork(spec, state):
    store = get_genesis_forkchoice_store(spec, state)
    fork_slot, pre_ms, post_ms, _, _ = _fork_params(spec, state.genesis_time)
    disparity = spec.config.MAXIMUM_GOSSIP_CLOCK_DISPARITY

    # One second into the third post-fork slot, beyond the disparity allowance
    assert disparity < 1000
    now_ms = state.genesis_time * 1000 + fork_slot * pre_ms + 3 * post_ms + 1000
    current_slot = spec.Slot(fork_slot + 3)

    # A genesis-anchored slot start would be off by more than the disparity
    # allowance, wrongly rejecting a current-slot message
    assert 3 * (pre_ms - post_ms) > disparity
    assert not spec.is_future_slot(store, current_slot, now_ms)
    # A message one slot ahead is from the future
    assert spec.is_future_slot(store, spec.Slot(current_slot + 1), now_ms)

    # A slot range straddling the fork boundary: [fork_slot - 2, fork_slot + 2]
    for slot in range(fork_slot - 2, fork_slot + 3):
        assert spec.is_within_slot_range(store, spec.Slot(slot), spec.Uint64(4), now_ms) == (
            slot + 4 >= current_slot
        )


@with_phases([EIP8198])
@spec_configured_state_test(FORK_EPOCH_OVERRIDE, activate_at_genesis=True)
def test_compute_fork_version_at_fork(spec, state):
    assert spec.compute_fork_version(spec.Epoch(FORK_EPOCH)) == spec.config.EIP8198_FORK_VERSION
    assert spec.compute_fork_version(spec.Epoch(FORK_EPOCH - 1)) != spec.config.EIP8198_FORK_VERSION


@with_phases([EIP8198])
@spec_configured_state_test(FORK_EPOCH_OVERRIDE, activate_at_genesis=True)
def test_on_tick_across_fork(spec, state):
    store = get_genesis_forkchoice_store(spec, state)
    fork_slot, _, post_ms, fork_time, fork_time_ms = _fork_params(spec, store.genesis_time)

    # Tick from genesis to a few slots past the fork in one call; the catch-up
    # loop must process every slot boundary at its correct wall-clock time
    spec.on_tick(store, fork_time + 3 * post_ms // 1000)
    assert spec.get_current_slot(store) == fork_slot + 3
    assert spec.get_time_into_slot_ms(store) == 0

    spec.on_tick_ms(store, fork_time_ms + 3 * post_ms + 1234)
    assert store.time_ms == fork_time_ms + 3 * post_ms + 1234
    assert spec.get_time_into_slot_ms(store) == 1234

    next_slot_time_ms = fork_time_ms + 4 * post_ms
    spec.on_tick_per_slot_ms(store, next_slot_time_ms)
    assert store.time_ms == next_slot_time_ms
    assert spec.get_current_slot(store) == fork_slot + 4


@with_phases([EIP8198])
@spec_configured_state_test(FORK_EPOCH_OVERRIDE, activate_at_genesis=True)
def test_forkchoice_timeliness_uses_post_fork_slot_start(spec, state):
    store = get_genesis_forkchoice_store(spec, state)
    fork_slot, _, _, _, _ = _fork_params(spec, store.genesis_time)
    block_slot = spec.Slot(fork_slot + 3)
    block_time_ms = spec.compute_time_at_slot_ms(store, block_slot)
    block_root = spec.Root(b"\x12" * 32)
    store.blocks[block_root] = spec.BeaconBlock(slot=block_slot)

    store.time_ms = block_time_ms
    spec.record_block_timeliness(store, block_root)
    assert spec.get_time_into_slot_ms(store) == 0
    assert spec.is_proposing_on_time(store)
    assert store.block_timeliness[block_root] == [True, True]

    attestation_due_ms = spec.get_attestation_due_ms(block_slot)
    payload_attestation_due_ms = spec.get_payload_attestation_due_ms(block_slot)
    proposer_reorg_cutoff_ms = spec.get_proposer_reorg_cutoff_ms(block_slot)

    store.time_ms = block_time_ms + proposer_reorg_cutoff_ms
    assert spec.is_proposing_on_time(store)
    store.time_ms = block_time_ms + proposer_reorg_cutoff_ms + 1
    assert not spec.is_proposing_on_time(store)

    store.time_ms = block_time_ms + attestation_due_ms - 1
    spec.record_block_timeliness(store, block_root)
    assert store.block_timeliness[block_root] == [True, True]

    store.time_ms = block_time_ms + attestation_due_ms
    spec.record_block_timeliness(store, block_root)
    assert not spec.is_proposing_on_time(store)
    assert store.block_timeliness[block_root] == [False, True]

    store.time_ms = block_time_ms + payload_attestation_due_ms
    spec.record_block_timeliness(store, block_root)
    assert store.block_timeliness[block_root] == [False, False]


@with_phases([EIP8198])
@spec_configured_state_test(FORK_EPOCH_OVERRIDE, activate_at_genesis=True)
def test_boundary_slot_timeliness_uses_new_duration(spec, state):
    # Probe times fall between the new and the old deadlines, so using the
    # wrong slot's duration flips every assertion
    store = get_genesis_forkchoice_store(spec, state)
    fork_slot, pre_ms, _post_ms, _, fork_time_ms = _fork_params(spec, store.genesis_time)

    new_attestation_due_ms = spec.get_attestation_due_ms(spec.Slot(fork_slot))
    old_attestation_due_ms = spec.get_attestation_due_ms(spec.Slot(fork_slot - 1))
    assert new_attestation_due_ms < old_attestation_due_ms
    probe_ms = (new_attestation_due_ms + old_attestation_due_ms) // 2

    block_root = spec.Root(b"\x34" * 32)
    store.blocks[block_root] = spec.BeaconBlock(slot=spec.Slot(fork_slot))
    store.time_ms = fork_time_ms + probe_ms
    spec.record_block_timeliness(store, block_root)
    assert store.block_timeliness[block_root][0] == (probe_ms < new_attestation_due_ms)

    # The last old-duration slot keeps the old deadline
    old_block_root = spec.Root(b"\x56" * 32)
    store.blocks[old_block_root] = spec.BeaconBlock(slot=spec.Slot(fork_slot - 1))
    store.time_ms = fork_time_ms - pre_ms + probe_ms
    spec.record_block_timeliness(store, old_block_root)
    assert store.block_timeliness[old_block_root][0] == (probe_ms < old_attestation_due_ms)

    # Proposer reorg cutoff at the boundary slot follows the new duration
    new_cutoff_ms = spec.get_proposer_reorg_cutoff_ms(spec.Slot(fork_slot))
    old_cutoff_ms = spec.get_proposer_reorg_cutoff_ms(spec.Slot(fork_slot - 1))
    assert new_cutoff_ms < old_cutoff_ms
    cutoff_probe_ms = (new_cutoff_ms + old_cutoff_ms) // 2
    store.time_ms = fork_time_ms + cutoff_probe_ms
    assert spec.is_proposing_on_time(store) == (cutoff_probe_ms <= new_cutoff_ms)


INDEPENDENT_DEADLINE_OVERRIDE = {
    "EIP8198_FORK_EPOCH": FORK_EPOCH,
    "SLOT_DURATION_SCHEDULE": (
        slot_duration_schedule_entry(0, 6000),
        slot_duration_schedule_entry(FORK_EPOCH, POST_DURATION_MS, ATTESTATION_DUE_MS=2000),
    ),
}


@with_phases([EIP8198])
@spec_configured_state_test(INDEPENDENT_DEADLINE_OVERRIDE, activate_at_genesis=True)
def test_deadlines_are_independent_parameters(spec, state):
    fork_slot = spec.Slot(FORK_EPOCH * spec.SLOTS_PER_EPOCH)
    entry = spec.config.SLOT_DURATION_SCHEDULE[1]

    # The configured deadline differs from the inherited fraction and wins
    assert entry["ATTESTATION_DUE_MS"] != (
        spec.config.ATTESTATION_DUE_BPS_GLOAS * POST_DURATION_MS // spec.BASIS_POINTS
    )
    assert spec.get_attestation_due_ms(fork_slot) == entry["ATTESTATION_DUE_MS"]

    # Pre-schedule slots keep the inherited basis-point deadline
    assert spec.get_attestation_due_ms(spec.Slot(fork_slot - 1)) == (
        spec.config.ATTESTATION_DUE_BPS_GLOAS
        * spec.get_slot_duration_ms(spec.GENESIS_EPOCH)
        // spec.BASIS_POINTS
    )


@with_phases([EIP8198])
@spec_configured_state_test(FORK_EPOCH_OVERRIDE, activate_at_genesis=True)
def test_epoch_processing_prices_previous_epoch(spec, state):
    # Advance into the first epoch of the new era: the previous epoch still
    # ran at the old duration
    for _ in range(FORK_EPOCH):
        next_epoch(spec, state)
    assert spec.get_current_epoch(state) == FORK_EPOCH
    previous_epoch = spec.get_previous_epoch(state)
    pre_ms = spec.get_slot_duration_ms(spec.GENESIS_EPOCH)
    assert spec.get_slot_duration_ms(previous_epoch) == pre_ms

    # In-block pricing follows the current (new) duration, epoch-processing
    # pricing the previous (old) one
    current_per_increment = spec.get_base_reward_per_increment(state)
    previous_per_increment = spec.get_base_reward_per_increment_at_epoch(state, previous_epoch)
    sqrt_balance = spec.integer_squareroot(spec.get_total_active_balance(state))
    assert previous_per_increment == (
        spec.EFFECTIVE_BALANCE_INCREMENT * spec.BASE_REWARD_FACTOR // sqrt_balance
    )
    assert current_per_increment == (
        spec.EFFECTIVE_BALANCE_INCREMENT
        * spec.BASE_REWARD_FACTOR
        * POST_DURATION_MS
        // pre_ms
        // sqrt_balance
    )
    assert current_per_increment < previous_per_increment

    # Flag deltas pay the previous epoch at the old duration
    index = spec.ValidatorIndex(0)
    state.previous_epoch_participation[index] = spec.add_flag(
        spec.ParticipationFlags(0), spec.TIMELY_TARGET_FLAG_INDEX
    )
    rewards, penalties = spec.get_flag_index_deltas(state, spec.TIMELY_TARGET_FLAG_INDEX)
    base_reward = spec.get_base_reward_at_epoch(state, index, previous_epoch)
    weight = spec.PARTICIPATION_FLAG_WEIGHTS[spec.TIMELY_TARGET_FLAG_INDEX]
    unslashed_increments = spec.get_total_balance(state, {index}) // (
        spec.EFFECTIVE_BALANCE_INCREMENT
    )
    active_increments = spec.get_total_active_balance(state) // spec.EFFECTIVE_BALANCE_INCREMENT
    assert rewards[index] == (base_reward * weight * unslashed_increments) // (
        active_increments * spec.WEIGHT_DENOMINATOR
    )

    # Non-participants are penalized at the old duration too
    other = spec.ValidatorIndex(1)
    assert penalties[other] == (
        spec.get_base_reward_at_epoch(state, other, previous_epoch)
        * weight
        // spec.WEIGHT_DENOMINATOR
    )

    # Inactivity penalties price the previous epoch at the old duration, so
    # at the boundary the squared ratio is exactly one
    state.inactivity_scores[other] = 4
    _, inactivity_penalties = spec.get_inactivity_penalty_deltas(state)
    penalty_numerator = state.validators[other].effective_balance * state.inactivity_scores[other]
    penalty_denominator = (
        spec.config.INACTIVITY_SCORE_BIAS * spec.INACTIVITY_PENALTY_QUOTIENT_BELLATRIX
    )
    assert inactivity_penalties[other] == penalty_numerator // penalty_denominator


@with_phases([EIP8198])
@spec_configured_state_test(FORK_EPOCH_OVERRIDE, activate_at_genesis=True)
def test_proposer_reward_prices_attestation_target_epoch(spec, state):
    # Advance to the first slot of the new era
    for _ in range(FORK_EPOCH):
        next_epoch(spec, state)
    assert spec.get_current_epoch(state) == FORK_EPOCH

    # A valid attestation for the last old-era slot, included in the new era
    attestation = get_valid_attestation(spec, state, slot=spec.Slot(state.slot - 1), signed=True)
    data = attestation.data
    assert data.target.epoch == FORK_EPOCH - 1

    # The proposer's cut is priced at the attestation's (old-era) epoch. All
    # flags are newly set, since the state has no prior participation.
    participation_flag_indices = spec.get_attestation_participation_flag_indices(
        state, data, state.slot - data.slot, get_parent_slot(state)
    )
    expected_numerator = 0
    wrong_numerator = 0
    for index in spec.get_attesting_indices(state, attestation):
        for flag_index, weight in enumerate(spec.PARTICIPATION_FLAG_WEIGHTS):
            if flag_index in participation_flag_indices:
                expected_numerator += (
                    spec.get_base_reward_at_epoch(state, index, data.target.epoch) * weight
                )
                wrong_numerator += (
                    spec.get_base_reward_at_epoch(state, index, spec.get_current_epoch(state))
                    * weight
                )
    denominator = (
        (spec.WEIGHT_DENOMINATOR - spec.PROPOSER_WEIGHT)
        * spec.WEIGHT_DENOMINATOR
        // spec.PROPOSER_WEIGHT
    )
    assert expected_numerator // denominator != wrong_numerator // denominator

    proposer_index = spec.get_beacon_proposer_index(state)
    pre_balance = state.balances[proposer_index]
    process_attestation(spec, state, attestation)
    assert state.balances[proposer_index] - pre_balance == expected_numerator // denominator


@with_phases([EIP8198])
@spec_configured_state_test(EARLY_SCHEDULE_OVERRIDE, activate_at_genesis=True)
def test_base_reward_uses_scheduled_slot_ratio(spec, state):
    next_epoch(spec, state)
    next_epoch(spec, state)
    duration_ms = spec.get_slot_duration_ms(spec.get_current_epoch(state))
    assert duration_ms == POST_DURATION_MS
    expected = (
        spec.EFFECTIVE_BALANCE_INCREMENT
        * spec.BASE_REWARD_FACTOR
        * duration_ms
        // spec.get_slot_duration_ms(spec.GENESIS_EPOCH)
        // spec.integer_squareroot(spec.get_total_active_balance(state))
    )
    assert spec.get_base_reward_per_increment(state) == expected


@with_phases([EIP8198])
@spec_configured_state_test(EARLY_SCHEDULE_OVERRIDE, activate_at_genesis=True)
def test_inactivity_penalty_uses_scheduled_slot_ratio(spec, state):
    next_epoch(spec, state)
    next_epoch(spec, state)
    index = 0
    state.inactivity_scores[index] = 1
    _, penalties = spec.get_inactivity_penalty_deltas(state)

    penalty_numerator = state.validators[index].effective_balance * state.inactivity_scores[index]
    duration_ms = int(spec.get_slot_duration_ms(spec.get_current_epoch(state)))
    penalty_denominator = (
        int(spec.config.INACTIVITY_SCORE_BIAS)
        * int(spec.INACTIVITY_PENALTY_QUOTIENT_BELLATRIX)
        * int(spec.get_slot_duration_ms(spec.GENESIS_EPOCH))
        * int(spec.get_slot_duration_ms(spec.GENESIS_EPOCH))
        // (duration_ms * duration_ms)
    )
    assert penalties[index] == int(penalty_numerator) // penalty_denominator


@with_phases([EIP8198])
@with_presets([MINIMAL], reason="uses minimal churn quotients for a compact boundary state")
@spec_configured_state_test(EARLY_SCHEDULE_OVERRIDE, activate_at_genesis=True)
def test_churn_scales_before_increment_rounding(spec, state):
    next_epoch(spec, state)
    next_epoch(spec, state)
    for validator in state.validators:
        validator.effective_balance = 0
    target_total = spec.Gwei(1_959_000_000_000)
    state.validators[0].effective_balance = target_total
    assert spec.get_total_active_balance(state) == target_total
    duration_ms = spec.get_slot_duration_ms(spec.get_current_epoch(state))
    assert duration_ms == POST_DURATION_MS

    raw_activation_exit = max(
        spec.config.MIN_PER_EPOCH_CHURN_LIMIT_ELECTRA,
        target_total // spec.config.CHURN_LIMIT_QUOTIENT_GLOAS,
    )
    expected_activation_exit = (
        raw_activation_exit * duration_ms // spec.get_slot_duration_ms(spec.GENESIS_EPOCH)
    )
    expected_activation_exit -= expected_activation_exit % spec.EFFECTIVE_BALANCE_INCREMENT
    assert spec.get_activation_churn_limit(state) == expected_activation_exit
    assert spec.get_exit_churn_limit(state) == expected_activation_exit

    raw_consolidation = target_total // spec.config.CONSOLIDATION_CHURN_LIMIT_QUOTIENT
    expected_consolidation = (
        raw_consolidation * duration_ms // spec.get_slot_duration_ms(spec.GENESIS_EPOCH)
    )
    expected_consolidation -= expected_consolidation % spec.EFFECTIVE_BALANCE_INCREMENT
    assert spec.get_consolidation_churn_limit(state) == expected_consolidation


@with_phases([EIP8198])
@spec_configured_state_test(
    {
        "EIP8198_FORK_EPOCH": 8192,
        "SLOT_DURATION_SCHEDULE": (
            slot_duration_schedule_entry(0, 6000),
            slot_duration_schedule_entry(8192, 5000),
        ),
    },
    activate_at_genesis=True,
)
def test_retention_window_preserves_wall_clock_length(spec, state):
    fork_epoch = int(spec.config.EIP8198_FORK_EPOCH)
    start_of = spec.get_data_column_sidecars_retention_start
    window_epochs = spec.config.MIN_EPOCHS_FOR_DATA_COLUMN_SIDECARS_REQUESTS
    window_ms = (
        spec.Uint64(window_epochs)
        * spec.SLOTS_PER_EPOCH
        * spec.get_slot_duration_ms(spec.GENESIS_EPOCH)
    )

    # Early epochs clamp at genesis
    assert start_of(spec.GENESIS_EPOCH) == spec.GENESIS_EPOCH
    assert start_of(spec.Epoch(window_epochs - 1)) == spec.GENESIS_EPOCH

    # Up to the fork, the window is exactly the inherited epoch count
    assert start_of(spec.Epoch(fork_epoch - 1)) == fork_epoch - 1 - window_epochs
    assert start_of(spec.Epoch(fork_epoch)) == fork_epoch - window_epochs

    # After the fork, the window's wall-clock length is preserved, with less
    # than one pre-fork epoch of overshoot
    pre_epoch_ms = spec.SLOTS_PER_EPOCH * spec.get_slot_duration_ms(spec.GENESIS_EPOCH)
    for k in (1, 7, int(window_epochs // 2), int(window_epochs), int(window_epochs) + 100):
        current_epoch = spec.Epoch(fork_epoch + k)
        start_epoch = start_of(current_epoch)
        coverage_ms = spec.compute_slot_range_duration_ms(
            spec.compute_start_slot_at_epoch(start_epoch),
            spec.compute_start_slot_at_epoch(current_epoch),
        )
        assert window_ms <= coverage_ms < window_ms + pre_epoch_ms


@with_phases([EIP8198])
@spec_test
@single_phase
def test_genesis_schedule_keeps_base_duration(spec):
    assert len(spec.config.SLOT_DURATION_SCHEDULE) == 1
    assert spec.config.SLOT_DURATION_SCHEDULE[0]["EPOCH"] == spec.GENESIS_EPOCH
    for epoch in (spec.GENESIS_EPOCH, spec.Epoch(8192), spec.Epoch(100_000)):
        assert spec.get_slot_duration_ms(epoch) == spec.get_slot_duration_ms(spec.GENESIS_EPOCH)
        slot = spec.compute_start_slot_at_epoch(epoch)
        start_ms = spec.compute_slot_start_time_ms(spec.Uint64(0), slot)
        assert start_ms == slot * spec.get_slot_duration_ms(spec.GENESIS_EPOCH)
        assert spec.compute_slot_at_time_ms(spec.Uint64(0), start_ms) == slot
    for epoch in (spec.Epoch(8192), spec.Epoch(100_000)):
        assert spec.get_data_column_sidecars_retention_start(epoch) == (
            epoch - spec.config.MIN_EPOCHS_FOR_DATA_COLUMN_SIDECARS_REQUESTS
        )


@with_phases([EIP8198])
@spec_configured_state_test(FORK_EPOCH_OVERRIDE, activate_at_genesis=True)
def test_slot_range_duration_cross_fork(spec, state):
    fork_slot = spec.Slot(FORK_EPOCH * spec.SLOTS_PER_EPOCH)
    start_slot = spec.Slot(fork_slot - spec.SLOTS_PER_EPOCH)
    end_slot = spec.Slot(fork_slot + spec.SLOTS_PER_EPOCH)
    expected_ms = spec.SLOTS_PER_EPOCH * (
        spec.get_slot_duration_ms(spec.GENESIS_EPOCH) + POST_DURATION_MS
    )

    assert spec.compute_slot_range_duration_ms(start_slot, end_slot) == expected_ms


@with_phases([EIP8198])
@spec_test
@with_config_overrides(FORK_EPOCH_OVERRIDE)
@single_phase
def test_intra_slot_deadlines_use_scheduled_duration(spec):
    pre_slot = spec.Slot(0)
    post_slot = spec.Slot(FORK_EPOCH * spec.SLOTS_PER_EPOCH)
    for slot, duration_ms in [
        (pre_slot, spec.get_slot_duration_ms(spec.GENESIS_EPOCH)),
        (post_slot, POST_DURATION_MS),
    ]:
        assert spec.get_proposer_reorg_cutoff_ms(slot) == (
            spec.config.PROPOSER_REORG_CUTOFF_BPS * duration_ms // spec.BASIS_POINTS
        )
        assert spec.get_attestation_due_ms(slot) == (
            spec.config.ATTESTATION_DUE_BPS_GLOAS * duration_ms // spec.BASIS_POINTS
        )
        assert spec.get_sync_message_due_ms(slot) == (
            spec.config.SYNC_MESSAGE_DUE_BPS_GLOAS * duration_ms // spec.BASIS_POINTS
        )
        assert spec.get_aggregate_due_ms(slot) == (
            spec.config.AGGREGATE_DUE_BPS_GLOAS * duration_ms // spec.BASIS_POINTS
        )
        assert spec.get_contribution_due_ms(slot) == (
            spec.config.CONTRIBUTION_DUE_BPS_GLOAS * duration_ms // spec.BASIS_POINTS
        )
        assert spec.get_payload_due_ms(slot) == (
            spec.config.PAYLOAD_DUE_BPS * duration_ms // spec.BASIS_POINTS
        )
        assert spec.get_payload_attestation_due_ms(slot) == (
            spec.config.PAYLOAD_ATTESTATION_DUE_BPS * duration_ms // spec.BASIS_POINTS
        )
        assert spec.get_inclusion_list_due_ms(slot) == (
            spec.config.INCLUSION_LIST_DUE_BPS * duration_ms // spec.BASIS_POINTS
        )


@with_phases([EIP8198])
@spec_configured_state_test(FORK_EPOCH_OVERRIDE, activate_at_genesis=True)
def test_timing_from_genesis_schedule(spec, state):
    fork_slot = spec.compute_start_slot_at_epoch(spec.Epoch(FORK_EPOCH))
    expected_ms = state.genesis_time * 1000 + fork_slot * 6000 + 5000
    assert spec.compute_time_at_slot(state, spec.Slot(fork_slot + 1)) * 1000 == expected_ms
    assert spec.compute_slot_at_time_ms(state.genesis_time, expected_ms) == fork_slot + 1
    assert spec.get_slot_duration_ms(spec.GENESIS_EPOCH) == 6000
