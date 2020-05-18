from random import Random

from eth2spec.test.context import with_all_phases, spec_state_test
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
