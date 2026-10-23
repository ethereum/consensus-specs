from eth_consensus_specs.test.context import (
    spec_configured_state_test,
    with_phases,
)
from eth_consensus_specs.test.helpers.constants import HEZE
from eth_consensus_specs.test.helpers.heze.slot_duration import (
    expected_base_reward_per_increment,
)


def _run_participation_deltas(spec, state, epoch):
    state.slot = spec.compute_start_slot_at_epoch(epoch + 1) - 1
    state.previous_epoch_participation[0] = spec.ParticipationFlags(0b111)
    duration_ms = (
        spec.config.SLOT_DURATION_MS
        if epoch <= spec.config.HEZE_FORK_EPOCH
        else spec.config.SLOT_DURATION_MS_HEZE
    )
    base_reward_per_increment = expected_base_reward_per_increment(spec, state, duration_ms)
    increment = spec.EFFECTIVE_BALANCE_INCREMENT
    active_increments = sum(v.effective_balance for v in state.validators) // increment
    participating_increments_0 = state.validators[0].effective_balance // increment
    base_reward = participating_increments_0 * base_reward_per_increment
    rewards = sum(
        base_reward
        * weight
        * participating_increments_0
        // (active_increments * spec.WEIGHT_DENOMINATOR)
        for weight in spec.PARTICIPATION_FLAG_WEIGHTS
    )
    participating_increments_1 = state.validators[1].effective_balance // increment
    base_penalty = participating_increments_1 * base_reward_per_increment
    penalties = sum(
        base_penalty * weight // spec.WEIGHT_DENOMINATOR
        for weight in (spec.TIMELY_SOURCE_WEIGHT, spec.TIMELY_TARGET_WEIGHT)
    )
    balances = list(state.balances)

    yield "pre", state
    spec.process_rewards_and_penalties(state)
    yield "post", state

    assert state.balances[0] == balances[0] + rewards
    assert state.balances[1] == balances[1] - penalties


@with_phases([HEZE])
@spec_configured_state_test({"HEZE_FORK_EPOCH": 2}, activate_at_genesis=True)
def test_participation_deltas_previous_epoch_at_heze_fork(spec, state):
    yield from _run_participation_deltas(spec, state, spec.config.HEZE_FORK_EPOCH)


@with_phases([HEZE])
@spec_configured_state_test({"HEZE_FORK_EPOCH": 2}, activate_at_genesis=True)
def test_participation_deltas_current_epoch_at_heze_fork(spec, state):
    yield from _run_participation_deltas(spec, state, spec.config.HEZE_FORK_EPOCH + 1)
