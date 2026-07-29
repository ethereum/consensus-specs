"""
Unit tests for the EIP-8198 piecewise time functions, run with
``EIP8198_FORK_EPOCH`` overridden to a small epoch so that the fork-boundary
branches are actually exercised (with the default FAR_FUTURE_EPOCH they are
unreachable).

All assertions are written in terms of the config values so the target slot
duration can be changed without rewriting derived expectations.
"""

from eth_consensus_specs.test.context import (
    single_phase,
    spec_configured_state_test,
    spec_state_test,
    spec_test,
    with_phases,
    with_presets,
)
from eth_consensus_specs.test.helpers.constants import EIP8198, MINIMAL
from eth_consensus_specs.test.helpers.fork_choice import get_genesis_forkchoice_store
from eth_consensus_specs.test.helpers.state import next_epoch

FORK_EPOCH = 2
FORK_EPOCH_OVERRIDE = {"EIP8198_FORK_EPOCH": FORK_EPOCH}


def _fork_params(spec, genesis_time):
    fork_slot = FORK_EPOCH * spec.SLOTS_PER_EPOCH
    pre_ms = spec.config.SLOT_DURATION_MS
    post_ms = spec.config.SLOT_DURATION_MS_EIP8198
    fork_time = genesis_time + fork_slot * pre_ms // 1000
    fork_time_ms = genesis_time * 1000 + fork_slot * pre_ms
    return fork_slot, pre_ms, post_ms, fork_time, fork_time_ms


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

    # Post-fork: offsets are taken modulo the new duration, rebased on the
    # fork time (the old genesis-anchored modulo would give a different value)
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

    # Consistency with the fork choice mapping: the timestamp of slot s + 1 is
    # the end of slot s
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
    assert store.time_ms == spec.compute_time_at_slot_ms(state, state.slot)
    assert spec.get_current_slot(store) == state.slot


@with_phases([EIP8198])
@spec_configured_state_test(FORK_EPOCH_OVERRIDE, activate_at_genesis=True)
def test_compute_time_at_slot_ms_across_fork(spec, state):
    fork_slot, pre_ms, post_ms, _, fork_time_ms = _fork_params(spec, state.genesis_time)

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
@spec_configured_state_test(FORK_EPOCH_OVERRIDE, activate_at_genesis=True)
def test_gossip_slot_gates_across_fork(spec, state):
    fork_slot, pre_ms, post_ms, _, _ = _fork_params(spec, state.genesis_time)
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
    block_time_ms = spec.compute_time_at_slot_ms(state, block_slot)
    block_root = spec.Root(b"\x12" * 32)
    store.blocks[block_root] = spec.BeaconBlock(slot=block_slot)

    store.time_ms = block_time_ms
    spec.record_block_timeliness(store, block_root)
    assert spec.get_time_into_slot_ms(store) == 0
    assert spec.is_proposing_on_time(store)
    assert store.block_timeliness[block_root] == [True, True]

    attestation_due_ms = spec.get_attestation_due_ms()
    payload_attestation_due_ms = spec.get_payload_attestation_due_ms()
    proposer_reorg_cutoff_ms = spec.get_proposer_reorg_cutoff_ms()

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
@spec_state_test
def test_base_reward_uses_eip8198_slot_ratio(spec, state):
    expected = (
        spec.EFFECTIVE_BALANCE_INCREMENT
        * spec.BASE_REWARD_FACTOR
        * spec.config.SLOT_DURATION_MS_EIP8198
        // spec.config.SLOT_DURATION_MS
        // spec.integer_squareroot(spec.get_total_active_balance(state))
    )
    assert spec.get_base_reward_per_increment(state) == expected


@with_phases([EIP8198])
@spec_state_test
def test_inactivity_penalty_uses_eip8198_slot_ratio(spec, state):
    index = 0
    state.inactivity_scores[index] = 1
    _, penalties = spec.get_inactivity_penalty_deltas(state)

    penalty_numerator = state.validators[index].effective_balance * state.inactivity_scores[index]
    penalty_denominator = (
        int(spec.config.INACTIVITY_SCORE_BIAS)
        * int(spec.INACTIVITY_PENALTY_QUOTIENT_BELLATRIX)
        * int(spec.config.SLOT_DURATION_MS)
        * int(spec.config.SLOT_DURATION_MS)
        // (int(spec.config.SLOT_DURATION_MS_EIP8198) * int(spec.config.SLOT_DURATION_MS_EIP8198))
    )
    assert penalties[index] == int(penalty_numerator) // penalty_denominator


@with_phases([EIP8198])
@with_presets([MINIMAL], reason="uses minimal churn quotients for a compact boundary state")
@spec_state_test
def test_churn_scales_before_increment_rounding(spec, state):
    for validator in state.validators:
        validator.effective_balance = 0
    target_total = spec.Gwei(1_959_000_000_000)
    state.validators[0].effective_balance = target_total
    assert spec.get_total_active_balance(state) == target_total

    raw_activation_exit = max(
        spec.config.MIN_PER_EPOCH_CHURN_LIMIT_ELECTRA,
        target_total // spec.config.CHURN_LIMIT_QUOTIENT_GLOAS,
    )
    expected_activation_exit = (
        raw_activation_exit * spec.config.SLOT_DURATION_MS_EIP8198 // spec.config.SLOT_DURATION_MS
    )
    expected_activation_exit -= expected_activation_exit % spec.EFFECTIVE_BALANCE_INCREMENT
    assert spec.get_activation_churn_limit(state) == expected_activation_exit
    assert spec.get_exit_churn_limit(state) == expected_activation_exit

    raw_consolidation = target_total // spec.config.CONSOLIDATION_CHURN_LIMIT_QUOTIENT
    expected_consolidation = (
        raw_consolidation * spec.config.SLOT_DURATION_MS_EIP8198 // spec.config.SLOT_DURATION_MS
    )
    expected_consolidation -= expected_consolidation % spec.EFFECTIVE_BALANCE_INCREMENT
    assert spec.get_consolidation_churn_limit(state) == expected_consolidation


@with_phases([EIP8198])
@spec_configured_state_test(
    {"EIP8198_FORK_EPOCH": 4096},
    activate_at_genesis=True,
)
def test_blob_schedule_and_retention_parameters(spec, state):
    fork_epoch = spec.config.EIP8198_FORK_EPOCH
    pre_fork_parameters = spec.get_blob_parameters(spec.Epoch(fork_epoch - 1))
    post_fork_parameters = spec.get_blob_parameters(spec.Epoch(fork_epoch))

    assert post_fork_parameters.epoch == fork_epoch
    assert post_fork_parameters.max_blobs_per_block == (
        pre_fork_parameters.max_blobs_per_block
        * spec.config.SLOT_DURATION_MS_EIP8198
        // spec.config.SLOT_DURATION_MS
    )

    # The retention windows keep the inherited epoch count up to the fork,
    # then grow by one epoch per epoch until they reach the scaled count.
    pre_blob = spec.config.MIN_EPOCHS_FOR_BLOB_SIDECARS_REQUESTS
    post_blob = pre_blob * spec.config.SLOT_DURATION_MS // spec.config.SLOT_DURATION_MS_EIP8198
    blob_growth = post_blob - pre_blob
    assert spec.get_min_epochs_for_blob_sidecars_requests(spec.Epoch(fork_epoch - 1)) == pre_blob
    assert spec.get_min_epochs_for_blob_sidecars_requests(spec.Epoch(fork_epoch)) == pre_blob
    assert spec.get_min_epochs_for_blob_sidecars_requests(spec.Epoch(fork_epoch + 1)) == (
        pre_blob + 1
    )
    assert spec.get_min_epochs_for_blob_sidecars_requests(
        spec.Epoch(fork_epoch + blob_growth - 1)
    ) == (post_blob - 1)
    assert spec.get_min_epochs_for_blob_sidecars_requests(spec.Epoch(fork_epoch + blob_growth)) == (
        post_blob
    )
    assert spec.get_min_epochs_for_blob_sidecars_requests(
        spec.Epoch(fork_epoch + blob_growth + 1)
    ) == (post_blob)

    pre_column = spec.config.MIN_EPOCHS_FOR_DATA_COLUMN_SIDECARS_REQUESTS
    post_column = pre_column * spec.config.SLOT_DURATION_MS // spec.config.SLOT_DURATION_MS_EIP8198
    column_growth = post_column - pre_column
    assert spec.get_min_epochs_for_data_column_sidecars_requests(spec.Epoch(fork_epoch - 1)) == (
        pre_column
    )
    assert spec.get_min_epochs_for_data_column_sidecars_requests(spec.Epoch(fork_epoch)) == (
        pre_column
    )
    assert spec.get_min_epochs_for_data_column_sidecars_requests(spec.Epoch(fork_epoch + 1)) == (
        pre_column + 1
    )
    assert spec.get_min_epochs_for_data_column_sidecars_requests(
        spec.Epoch(fork_epoch + column_growth)
    ) == (post_column)
    assert spec.get_min_epochs_for_data_column_sidecars_requests(
        spec.Epoch(fork_epoch + column_growth + 1)
    ) == (post_column)


@with_phases([EIP8198])
@spec_test
@single_phase
def test_retention_parameters_when_fork_disabled(spec):
    assert spec.config.EIP8198_FORK_EPOCH == spec.FAR_FUTURE_EPOCH
    for epoch in (spec.GENESIS_EPOCH, spec.Epoch(1024), spec.FAR_FUTURE_EPOCH):
        assert spec.get_min_epochs_for_blob_sidecars_requests(epoch) == (
            spec.config.MIN_EPOCHS_FOR_BLOB_SIDECARS_REQUESTS
        )
        assert spec.get_min_epochs_for_data_column_sidecars_requests(epoch) == (
            spec.config.MIN_EPOCHS_FOR_DATA_COLUMN_SIDECARS_REQUESTS
        )


@with_phases([EIP8198])
@spec_configured_state_test(FORK_EPOCH_OVERRIDE, activate_at_genesis=True)
def test_slot_range_duration_cross_fork(spec, state):
    fork_slot = spec.Slot(FORK_EPOCH * spec.SLOTS_PER_EPOCH)
    start_slot = spec.Slot(fork_slot - spec.SLOTS_PER_EPOCH)
    end_slot = spec.Slot(fork_slot + spec.SLOTS_PER_EPOCH)
    expected_ms = spec.SLOTS_PER_EPOCH * (
        spec.config.SLOT_DURATION_MS + spec.config.SLOT_DURATION_MS_EIP8198
    )

    assert spec.compute_slot_range_duration_ms(start_slot, end_slot) == expected_ms


@with_phases([EIP8198])
@spec_test
@single_phase
def test_intra_slot_deadlines_use_eip8198_duration(spec):
    duration_ms = spec.config.SLOT_DURATION_MS_EIP8198
    assert spec.get_proposer_reorg_cutoff_ms() == (
        spec.config.PROPOSER_REORG_CUTOFF_BPS * duration_ms // spec.BASIS_POINTS
    )
    assert spec.get_attestation_due_ms() == (
        spec.config.ATTESTATION_DUE_BPS_GLOAS * duration_ms // spec.BASIS_POINTS
    )
    assert spec.get_sync_message_due_ms() == (
        spec.config.SYNC_MESSAGE_DUE_BPS_GLOAS * duration_ms // spec.BASIS_POINTS
    )
    assert spec.get_aggregate_due_ms() == (
        spec.config.AGGREGATE_DUE_BPS_GLOAS * duration_ms // spec.BASIS_POINTS
    )
    assert spec.get_contribution_due_ms() == (
        spec.config.CONTRIBUTION_DUE_BPS_GLOAS * duration_ms // spec.BASIS_POINTS
    )
    assert spec.get_payload_due_ms() == (
        spec.config.PAYLOAD_DUE_BPS * duration_ms // spec.BASIS_POINTS
    )
    assert spec.get_payload_attestation_due_ms() == (
        spec.config.PAYLOAD_ATTESTATION_DUE_BPS * duration_ms // spec.BASIS_POINTS
    )
    assert spec.get_inclusion_list_due_ms() == (
        spec.config.INCLUSION_LIST_DUE_BPS * duration_ms // spec.BASIS_POINTS
    )
