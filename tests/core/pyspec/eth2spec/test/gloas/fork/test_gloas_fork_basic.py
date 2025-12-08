from eth2spec.test.context import (
    large_validator_set,
    low_balances,
    misc_balances,
    spec_test,
    with_custom_state,
    with_phases,
    with_presets,
    with_state,
)
from eth2spec.test.helpers.constants import (
    FULU,
    GLOAS,
    MINIMAL,
)
from eth2spec.test.helpers.gloas.fork import (
    GLOAS_FORK_TEST_META_TAGS,
    run_fork_test,
)
from eth2spec.test.helpers.state import (
    next_epoch,
    next_epoch_via_block,
)
from eth2spec.test.utils import with_meta_tags


@with_phases(phases=[FULU], other_phases=[GLOAS])
@spec_test
@with_state
@with_meta_tags(GLOAS_FORK_TEST_META_TAGS)
def test_fork_base_state(spec, phases, state):
    yield from run_fork_test(phases[GLOAS], state)


@with_phases(phases=[FULU], other_phases=[GLOAS])
@spec_test
@with_state
@with_meta_tags(GLOAS_FORK_TEST_META_TAGS)
def test_fork_next_epoch(spec, phases, state):
    next_epoch(spec, state)
    yield from run_fork_test(phases[GLOAS], state)


@with_phases(phases=[FULU], other_phases=[GLOAS])
@spec_test
@with_state
@with_meta_tags(GLOAS_FORK_TEST_META_TAGS)
def test_fork_next_epoch_with_block(spec, phases, state):
    next_epoch_via_block(spec, state)
    yield from run_fork_test(phases[GLOAS], state)


@with_phases(phases=[FULU], other_phases=[GLOAS])
@spec_test
@with_state
@with_meta_tags(GLOAS_FORK_TEST_META_TAGS)
def test_fork_many_next_epoch(spec, phases, state):
    for _ in range(3):
        next_epoch(spec, state)
    yield from run_fork_test(phases[GLOAS], state)


@with_phases(phases=[FULU], other_phases=[GLOAS])
@with_custom_state(balances_fn=low_balances, threshold_fn=lambda spec: spec.config.EJECTION_BALANCE)
@spec_test
@with_meta_tags(GLOAS_FORK_TEST_META_TAGS)
def test_fork_random_low_balances(spec, phases, state):
    yield from run_fork_test(phases[GLOAS], state)


@with_phases(phases=[FULU], other_phases=[GLOAS])
@with_custom_state(
    balances_fn=misc_balances, threshold_fn=lambda spec: spec.config.EJECTION_BALANCE
)
@spec_test
@with_meta_tags(GLOAS_FORK_TEST_META_TAGS)
def test_fork_random_misc_balances(spec, phases, state):
    yield from run_fork_test(phases[GLOAS], state)


@with_phases(phases=[FULU], other_phases=[GLOAS])
@with_presets(
    [MINIMAL],
    reason="mainnet config leads to larger validator set than limit of public/private keys pre-generated",
)
@with_custom_state(
    balances_fn=large_validator_set, threshold_fn=lambda spec: spec.config.EJECTION_BALANCE
)
@spec_test
@with_meta_tags(GLOAS_FORK_TEST_META_TAGS)
def test_fork_random_large_validator_set(spec, phases, state):
    yield from run_fork_test(phases[GLOAS], state)
