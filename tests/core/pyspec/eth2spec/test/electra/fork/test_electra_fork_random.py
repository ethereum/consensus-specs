from random import Random

from eth2spec.test.context import (
    with_phases,
    with_custom_state,
    with_presets,
    spec_test, with_state,
    low_balances, misc_balances, large_validator_set,
)
from eth2spec.test.utils import with_meta_tags
from eth2spec.test.helpers.constants import (
    DENEB, ELECTRA,
    MINIMAL,
)
from eth2spec.test.helpers.electra.fork import (
    ELECTRA_FORK_TEST_META_TAGS,
    run_fork_test,
)
from eth2spec.test.helpers.random import randomize_state


@with_phases(phases=[DENEB], other_phases=[ELECTRA])
@spec_test
@with_state
@with_meta_tags(ELECTRA_FORK_TEST_META_TAGS)
def test_electra_fork_random_0(spec, phases, state):
    randomize_state(spec, state, rng=Random(1010))
    yield from run_fork_test(phases[ELECTRA], state)


@with_phases(phases=[DENEB], other_phases=[ELECTRA])
@spec_test
@with_state
@with_meta_tags(ELECTRA_FORK_TEST_META_TAGS)
def test_electra_fork_random_1(spec, phases, state):
    randomize_state(spec, state, rng=Random(2020))
    yield from run_fork_test(phases[ELECTRA], state)


@with_phases(phases=[DENEB], other_phases=[ELECTRA])
@spec_test
@with_state
@with_meta_tags(ELECTRA_FORK_TEST_META_TAGS)
def test_electra_fork_random_2(spec, phases, state):
    randomize_state(spec, state, rng=Random(3030))
    yield from run_fork_test(phases[ELECTRA], state)


@with_phases(phases=[DENEB], other_phases=[ELECTRA])
@spec_test
@with_state
@with_meta_tags(ELECTRA_FORK_TEST_META_TAGS)
def test_electra_fork_random_3(spec, phases, state):
    randomize_state(spec, state, rng=Random(4040))
    yield from run_fork_test(phases[ELECTRA], state)


@with_phases(phases=[DENEB], other_phases=[ELECTRA])
@spec_test
@with_custom_state(balances_fn=low_balances, threshold_fn=lambda spec: spec.config.EJECTION_BALANCE)
@with_meta_tags(ELECTRA_FORK_TEST_META_TAGS)
def test_electra_fork_random_low_balances(spec, phases, state):
    randomize_state(spec, state, rng=Random(5050))
    yield from run_fork_test(phases[ELECTRA], state)


@with_phases(phases=[DENEB], other_phases=[ELECTRA])
@spec_test
@with_custom_state(balances_fn=misc_balances, threshold_fn=lambda spec: spec.config.EJECTION_BALANCE)
@with_meta_tags(ELECTRA_FORK_TEST_META_TAGS)
def test_electra_fork_random_misc_balances(spec, phases, state):
    randomize_state(spec, state, rng=Random(6060))
    yield from run_fork_test(phases[ELECTRA], state)


@with_phases(phases=[DENEB], other_phases=[ELECTRA])
@with_presets([MINIMAL],
              reason="mainnet config leads to larger validator set than limit of public/private keys pre-generated")
@spec_test
@with_custom_state(balances_fn=large_validator_set, threshold_fn=lambda spec: spec.config.EJECTION_BALANCE)
@with_meta_tags(ELECTRA_FORK_TEST_META_TAGS)
def test_electra_fork_random_large_validator_set(spec, phases, state):
    randomize_state(spec, state, rng=Random(7070))
    yield from run_fork_test(phases[ELECTRA], state)
