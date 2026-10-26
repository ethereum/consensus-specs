from eth_consensus_specs.test.context import (
    spec_configured_state_test,
    with_phases,
)
from eth_consensus_specs.test.helpers.constants import HEZE
from eth_consensus_specs.test.helpers.rewards import run_deltas


def _run_inactivity_penalty(spec, state, epoch):
    state.slot = spec.compute_start_slot_at_epoch(epoch + 1) - 1
    state.inactivity_scores[0] = spec.config.INACTIVITY_SCORE_BIAS
    duration_ms = (
        spec.config.SLOT_DURATION_MS
        if epoch <= spec.config.HEZE_FORK_EPOCH
        else spec.config.SLOT_DURATION_MS_HEZE
    )
    penalty_numerator = state.validators[0].effective_balance * state.inactivity_scores[0]
    penalty_denominator = (
        spec.config.INACTIVITY_SCORE_BIAS
        * spec.INACTIVITY_PENALTY_QUOTIENT_BELLATRIX
        * spec.config.SLOT_DURATION_MS**2
        // duration_ms**2
    )
    penalty = penalty_numerator // penalty_denominator

    yield from run_deltas(spec, state)

    rewards, penalties = spec.get_inactivity_penalty_deltas(state)

    assert rewards[0] == 0
    assert penalties[0] == penalty


@with_phases([HEZE])
@spec_configured_state_test(
    {"HEZE_FORK_EPOCH": 2, "SLOT_DURATION_MS_HEZE": 10000}, activate_at_genesis=True
)
def test_inactivity_penalty_previous_epoch_at_heze_fork(spec, state):
    yield from _run_inactivity_penalty(spec, state, spec.config.HEZE_FORK_EPOCH)


@with_phases([HEZE])
@spec_configured_state_test(
    {"HEZE_FORK_EPOCH": 2, "SLOT_DURATION_MS_HEZE": 10000}, activate_at_genesis=True
)
def test_inactivity_penalty_current_epoch_at_heze_fork(spec, state):
    yield from _run_inactivity_penalty(spec, state, spec.config.HEZE_FORK_EPOCH + 1)
