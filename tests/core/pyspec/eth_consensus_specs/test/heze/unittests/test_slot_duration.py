from itertools import pairwise
from math import isqrt

from eth_consensus_specs.test.context import (
    get_copy_of_spec,
    single_phase,
    spec_state_test,
    spec_with_config_overrides,
    with_heze_and_later,
)

SLOT_DURATIONS_MS = [1000, 2000, 4000, 5000, 6000, 8000, 9000, 10000, 11000, 12000, 16000]
FORK_EPOCH = 2


def heze_spec_with_slot_duration(spec, slot_duration_ms, fork_epoch=FORK_EPOCH):
    heze_spec, _ = spec_with_config_overrides(
        get_copy_of_spec(spec),
        {"HEZE_FORK_EPOCH": fork_epoch, "SLOT_DURATION_MS_HEZE": slot_duration_ms},
    )
    return heze_spec


def expected_base_reward(spec, state, index, slot_duration_ms):
    increments = int(state.validators[index].effective_balance) // spec.EFFECTIVE_BALANCE_INCREMENT
    total_active_balance = sum(
        int(state.validators[i].effective_balance)
        for i in range(len(state.validators))
        if spec.is_active_validator(state.validators[i], spec.get_current_epoch(state))
    )
    total_active_balance = max(spec.EFFECTIVE_BALANCE_INCREMENT, total_active_balance)
    return increments * (
        spec.EFFECTIVE_BALANCE_INCREMENT
        * spec.BASE_REWARD_FACTOR
        * slot_duration_ms
        // int(spec.config.SLOT_DURATION_MS)
        // isqrt(total_active_balance)
    )


def fork_epoch_cases(spec, slot_duration_ms):
    genesis_ms = int(spec.config.SLOT_DURATION_MS)
    return [
        (FORK_EPOCH, FORK_EPOCH - 1, genesis_ms),
        (FORK_EPOCH, FORK_EPOCH, slot_duration_ms),
        (0, 0, slot_duration_ms),
        (0, 1, slot_duration_ms),
    ]


def scale_churn(spec, churn, slot_duration_ms):
    churn = churn * slot_duration_ms // int(spec.config.SLOT_DURATION_MS)
    return churn - churn % spec.EFFECTIVE_BALANCE_INCREMENT


@with_heze_and_later
@spec_state_test
@single_phase
def test_slot_duration_ms_across_fork(spec, state):
    genesis_ms = int(spec.config.SLOT_DURATION_MS)
    for slot_duration_ms in SLOT_DURATIONS_MS:
        heze_spec = heze_spec_with_slot_duration(spec, slot_duration_ms)
        assert heze_spec.get_slot_duration_ms(spec.GENESIS_EPOCH) == genesis_ms
        assert heze_spec.get_slot_duration_ms(FORK_EPOCH - 1) == genesis_ms
        assert heze_spec.get_slot_duration_ms(FORK_EPOCH) == slot_duration_ms
        assert heze_spec.get_slot_duration_ms(FORK_EPOCH + 100) == slot_duration_ms


@with_heze_and_later
@spec_state_test
@single_phase
def test_slot_duration_ms_without_scheduled_fork(spec, state):
    for slot_duration_ms in SLOT_DURATIONS_MS:
        heze_spec = heze_spec_with_slot_duration(spec, slot_duration_ms, spec.FAR_FUTURE_EPOCH)
        assert heze_spec.get_slot_duration_ms(FORK_EPOCH + 100) == spec.config.SLOT_DURATION_MS


@with_heze_and_later
@spec_state_test
@single_phase
def test_time_at_slot_ms_across_fork(spec, state):
    genesis_ms = int(spec.config.SLOT_DURATION_MS)
    genesis_time_ms = 1_000_000
    fork_slot = FORK_EPOCH * int(spec.SLOTS_PER_EPOCH)
    for slot_duration_ms in SLOT_DURATIONS_MS:
        heze_spec = heze_spec_with_slot_duration(spec, slot_duration_ms)
        for slot in range(fork_slot + 3 * spec.SLOTS_PER_EPOCH):
            pre_fork_slots = min(slot, fork_slot)
            post_fork_slots = max(slot - fork_slot, 0)
            expected = (
                genesis_time_ms + pre_fork_slots * genesis_ms + post_fork_slots * slot_duration_ms
            )
            time_ms = heze_spec.compute_time_at_slot_ms(genesis_time_ms, spec.Slot(slot))
            assert time_ms == expected
            assert heze_spec.compute_slot_at_time_ms(genesis_time_ms, time_ms) == slot
            next_time_ms = heze_spec.compute_time_at_slot_ms(genesis_time_ms, spec.Slot(slot + 1))
            assert heze_spec.compute_slot_at_time_ms(genesis_time_ms, next_time_ms - 1) == slot


@with_heze_and_later
@spec_state_test
@single_phase
def test_base_reward_across_fork(spec, state):
    index = spec.ValidatorIndex(0)
    for slot_duration_ms in SLOT_DURATIONS_MS:
        for fork_epoch, epoch, duration_ms in fork_epoch_cases(spec, slot_duration_ms):
            heze_spec = heze_spec_with_slot_duration(spec, slot_duration_ms, fork_epoch)
            assert heze_spec.get_base_reward(state, index, spec.Epoch(epoch)) == (
                expected_base_reward(spec, state, index, duration_ms)
            )


@with_heze_and_later
@spec_state_test
@single_phase
def test_base_reward_not_shared_between_overrides(spec, state):
    index = spec.ValidatorIndex(0)
    epoch = spec.Epoch(FORK_EPOCH)
    spec.get_base_reward(state, index, epoch)
    for slot_duration_ms in SLOT_DURATIONS_MS:
        heze_spec = heze_spec_with_slot_duration(spec, slot_duration_ms)
        assert heze_spec.get_base_reward(state, index, epoch) == expected_base_reward(
            spec, state, index, slot_duration_ms
        )
    assert spec.get_base_reward(state, index, epoch) == expected_base_reward(
        spec, state, index, int(spec.config.SLOT_DURATION_MS)
    )


@with_heze_and_later
@spec_state_test
@single_phase
def test_churn_limits_across_fork(spec, state):
    total_active_balance = int(spec.get_total_active_balance(state))
    base_churn = max(
        spec.config.MIN_PER_EPOCH_CHURN_LIMIT_ELECTRA,
        total_active_balance // spec.config.CHURN_LIMIT_QUOTIENT_GLOAS,
    )
    activation_churn = min(spec.config.MAX_PER_EPOCH_ACTIVATION_CHURN_LIMIT_GLOAS, base_churn)
    consolidation_churn = total_active_balance // spec.config.CONSOLIDATION_CHURN_LIMIT_QUOTIENT
    for slot_duration_ms in SLOT_DURATIONS_MS:
        for fork_epoch, epoch, duration_ms in fork_epoch_cases(spec, slot_duration_ms):
            heze_spec = heze_spec_with_slot_duration(spec, slot_duration_ms, fork_epoch)
            state.slot = spec.compute_start_slot_at_epoch(epoch)
            assert heze_spec.get_activation_churn_limit(state) == scale_churn(
                spec, activation_churn, duration_ms
            )
            assert heze_spec.get_exit_churn_limit(state) == scale_churn(
                spec, base_churn, duration_ms
            )
            assert heze_spec.get_consolidation_churn_limit(state) == scale_churn(
                spec, consolidation_churn, duration_ms
            )


@with_heze_and_later
@spec_state_test
@single_phase
def test_inactivity_penalty_across_fork(spec, state):
    genesis_ms = int(spec.config.SLOT_DURATION_MS)
    for index in range(len(state.validators)):
        state.inactivity_scores[index] = 1000 + index
    for slot_duration_ms in SLOT_DURATIONS_MS:
        for fork_epoch, previous_epoch, duration_ms in fork_epoch_cases(spec, slot_duration_ms):
            heze_spec = heze_spec_with_slot_duration(spec, slot_duration_ms, fork_epoch)
            state.slot = spec.compute_start_slot_at_epoch(previous_epoch + 1)
            _, penalties = heze_spec.get_inactivity_penalty_deltas(state)
            denominator = (
                spec.config.INACTIVITY_SCORE_BIAS
                * spec.INACTIVITY_PENALTY_QUOTIENT_BELLATRIX
                * genesis_ms**2
                // duration_ms**2
            )
            for index in heze_spec.get_eligible_validator_indices(state):
                expected = (
                    int(state.validators[index].effective_balance)
                    * int(state.inactivity_scores[index])
                    // denominator
                )
                assert penalties[index] == expected


@with_heze_and_later
@spec_state_test
@single_phase
def test_slot_component_duration_ms(spec, state):
    genesis_ms = int(spec.config.SLOT_DURATION_MS)
    for slot_duration_ms in SLOT_DURATIONS_MS:
        for fork_epoch, duration_ms in [
            (FORK_EPOCH, slot_duration_ms),
            (0, slot_duration_ms),
            (spec.FAR_FUTURE_EPOCH, genesis_ms),
        ]:
            heze_spec = heze_spec_with_slot_duration(spec, slot_duration_ms, fork_epoch)
            for basis_points in [0, 1, 2500, 3333, 5000, 6667, 7500, spec.BASIS_POINTS]:
                assert (
                    heze_spec.get_slot_component_duration_ms(basis_points)
                    == basis_points * duration_ms // spec.BASIS_POINTS
                )


@with_heze_and_later
@spec_state_test
@single_phase
def test_payload_timestamp_across_fork(spec, state):
    genesis_time = 1_600_000_000
    fork_slot = FORK_EPOCH * int(spec.SLOTS_PER_EPOCH)
    for slot_duration_ms in SLOT_DURATIONS_MS:
        heze_spec = heze_spec_with_slot_duration(spec, slot_duration_ms)
        timestamps = [
            int(heze_spec.compute_time_at_slot(spec.Uint64(genesis_time), spec.Slot(slot)))
            for slot in range(fork_slot + 3 * int(spec.SLOTS_PER_EPOCH))
        ]
        for slot, timestamp in enumerate(timestamps):
            time_ms = heze_spec.compute_time_at_slot_ms(
                spec.Uint64(genesis_time * 1000), spec.Slot(slot)
            )
            assert timestamp == int(time_ms) // 1000
        post_fork = timestamps[fork_slot:]
        assert all(b - a == slot_duration_ms // 1000 for a, b in pairwise(post_fork))
