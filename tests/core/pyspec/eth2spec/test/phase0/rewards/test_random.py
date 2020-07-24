from random import Random

from eth2spec.test.context import (
    with_all_phases,
    spec_test,
    spec_state_test,
    with_custom_state,
    single_phase,
    low_balances, misc_balances,
)
import eth2spec.test.helpers.rewards as rewards_helpers


@with_all_phases
@spec_state_test
def test_full_random_0(spec, state):
    yield from rewards_helpers.run_test_full_random(spec, state, rng=Random(1010))


@with_all_phases
@spec_state_test
def test_full_random_1(spec, state):
    yield from rewards_helpers.run_test_full_random(spec, state, rng=Random(2020))


@with_all_phases
@spec_state_test
def test_full_random_2(spec, state):
    yield from rewards_helpers.run_test_full_random(spec, state, rng=Random(3030))


@with_all_phases
@with_custom_state(balances_fn=low_balances, threshold_fn=lambda spec: spec.EJECTION_BALANCE)
@spec_test
@single_phase
def test_full_random_low_balances(spec, state):
    yield from rewards_helpers.run_test_full_random(spec, state)


@with_all_phases
@with_custom_state(balances_fn=misc_balances, threshold_fn=lambda spec: spec.EJECTION_BALANCE)
@spec_test
@single_phase
def test_full_random_misc_balances(spec, state):
    yield from rewards_helpers.run_test_full_random(spec, state)
