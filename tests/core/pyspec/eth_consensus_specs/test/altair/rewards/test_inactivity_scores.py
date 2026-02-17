from random import Random

import eth_consensus_specs.test.helpers.rewards as rewards_helpers
from eth_consensus_specs.test.context import (
    low_balances,
    misc_balances,
    single_phase,
    spec_state_test,
    spec_test,
    with_altair_and_later,
    with_custom_state,
)
from eth_consensus_specs.test.helpers.inactivity_scores import randomize_inactivity_scores
from eth_consensus_specs.test.helpers.rewards import leaking


@with_altair_and_later
@spec_state_test
def test_random_inactivity_scores_0(spec, state):
    randomize_inactivity_scores(spec, state, rng=Random(9999))
    yield from rewards_helpers.run_test_full_random(spec, state, rng=Random(9999))


@with_altair_and_later
@spec_state_test
def test_random_inactivity_scores_1(spec, state):
    randomize_inactivity_scores(spec, state, rng=Random(10000))
    yield from rewards_helpers.run_test_full_random(spec, state, rng=Random(10000))


@with_altair_and_later
@spec_state_test
def test_half_zero_half_random_inactivity_scores(spec, state):
    randomize_inactivity_scores(spec, state, rng=Random(10101))
    half_val_point = len(state.validators) // 2
    state.inactivity_scores = [0] * half_val_point + state.inactivity_scores[half_val_point:]

    yield from rewards_helpers.run_test_full_random(spec, state, rng=Random(10101))


@with_altair_and_later
@spec_state_test
def test_random_high_inactivity_scores(spec, state):
    randomize_inactivity_scores(spec, state, minimum=500000, maximum=5000000, rng=Random(9998))
    yield from rewards_helpers.run_test_full_random(spec, state, rng=Random(9998))


@with_altair_and_later
@with_custom_state(balances_fn=low_balances, threshold_fn=lambda spec: spec.config.EJECTION_BALANCE)
@spec_test
@single_phase
def test_random_inactivity_scores_low_balances_0(spec, state):
    randomize_inactivity_scores(spec, state, rng=Random(11111))
    yield from rewards_helpers.run_test_full_random(spec, state)


@with_altair_and_later
@with_custom_state(balances_fn=low_balances, threshold_fn=lambda spec: spec.config.EJECTION_BALANCE)
@spec_test
@single_phase
def test_random_inactivity_scores_low_balances_1(spec, state):
    randomize_inactivity_scores(spec, state, rng=Random(22222))
    yield from rewards_helpers.run_test_full_random(spec, state)


@with_altair_and_later
@with_custom_state(
    balances_fn=misc_balances, threshold_fn=lambda spec: spec.config.EJECTION_BALANCE
)
@spec_test
@single_phase
def test_full_random_misc_balances(spec, state):
    randomize_inactivity_scores(spec, state, rng=Random(33333))
    yield from rewards_helpers.run_test_full_random(spec, state)


#
# Leaking variants
#


@with_altair_and_later
@spec_state_test
@leaking()
def test_random_inactivity_scores_leaking_0(spec, state):
    randomize_inactivity_scores(spec, state, rng=Random(9999))
    yield from rewards_helpers.run_test_full_random(spec, state, rng=Random(9999))


@with_altair_and_later
@spec_state_test
@leaking()
def test_random_inactivity_scores_leaking_1(spec, state):
    randomize_inactivity_scores(spec, state, rng=Random(10000))
    yield from rewards_helpers.run_test_full_random(spec, state, rng=Random(10000))


@with_altair_and_later
@spec_state_test
@leaking()
def test_half_zero_half_random_inactivity_scores_leaking(spec, state):
    randomize_inactivity_scores(spec, state, rng=Random(10101))
    half_val_point = len(state.validators) // 2
    state.inactivity_scores = [0] * half_val_point + state.inactivity_scores[half_val_point:]

    yield from rewards_helpers.run_test_full_random(spec, state, rng=Random(10101))


@with_altair_and_later
@spec_state_test
@leaking()
def test_random_high_inactivity_scores_leaking(spec, state):
    randomize_inactivity_scores(spec, state, minimum=500000, maximum=5000000, rng=Random(9998))
    yield from rewards_helpers.run_test_full_random(spec, state, rng=Random(9998))


@with_altair_and_later
@spec_state_test
@leaking(epochs=8)
def test_random_high_inactivity_scores_leaking_8_epochs(spec, state):
    randomize_inactivity_scores(spec, state, minimum=500000, maximum=5000000, rng=Random(9998))
    yield from rewards_helpers.run_test_full_random(spec, state, rng=Random(9998))
