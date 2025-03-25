from random import Random

from eth2spec.test.context import (
    with_phases,
    with_custom_state,
    with_presets,
    spec_test,
    with_state,
    low_balances,
    misc_balances,
    large_validator_set,
)
from eth2spec.test.utils import with_meta_tags
from eth2spec.test.helpers.constants import (
    PHASE0,
    ALTAIR,
    MINIMAL,
)
from eth2spec.test.helpers.altair.fork import (
    ALTAIR_FORK_TEST_META_TAGS,
    run_fork_test,
)
from eth2spec.test.helpers.random import (
    randomize_state,
    randomize_attestation_participation,
)


@with_phases(phases=[PHASE0], other_phases=[ALTAIR])
@spec_test
@with_state
@with_meta_tags(ALTAIR_FORK_TEST_META_TAGS)
def test_altair_fork_random_0(spec, phases, state):
    randomize_state(spec, state, rng=Random(1010))
    yield from run_fork_test(phases[ALTAIR], state)


@with_phases(phases=[PHASE0], other_phases=[ALTAIR])
@spec_test
@with_state
@with_meta_tags(ALTAIR_FORK_TEST_META_TAGS)
def test_altair_fork_random_1(spec, phases, state):
    randomize_state(spec, state, rng=Random(2020))
    yield from run_fork_test(phases[ALTAIR], state)


@with_phases(phases=[PHASE0], other_phases=[ALTAIR])
@spec_test
@with_state
@with_meta_tags(ALTAIR_FORK_TEST_META_TAGS)
def test_altair_fork_random_2(spec, phases, state):
    randomize_state(spec, state, rng=Random(3030))
    yield from run_fork_test(phases[ALTAIR], state)


@with_phases(phases=[PHASE0], other_phases=[ALTAIR])
@spec_test
@with_state
@with_meta_tags(ALTAIR_FORK_TEST_META_TAGS)
def test_altair_fork_random_3(spec, phases, state):
    randomize_state(spec, state, rng=Random(4040))
    yield from run_fork_test(phases[ALTAIR], state)


@with_phases(phases=[PHASE0], other_phases=[ALTAIR])
@spec_test
@with_state
@with_meta_tags(ALTAIR_FORK_TEST_META_TAGS)
def test_altair_fork_random_duplicate_attestations(spec, phases, state):
    randomize_state(spec, state, rng=Random(1111))
    # Note: `run_fork_test` empties `current_epoch_attestations`
    state.previous_epoch_attestations = (
        state.previous_epoch_attestations + state.previous_epoch_attestations
    )
    yield from run_fork_test(phases[ALTAIR], state)


@with_phases(phases=[PHASE0], other_phases=[ALTAIR])
@spec_test
@with_state
@with_meta_tags(ALTAIR_FORK_TEST_META_TAGS)
def test_altair_fork_random_mismatched_attestations(spec, phases, state):
    # Create a random state
    randomize_state(spec, state, rng=Random(2222))

    # Now make two copies
    state_0 = state.copy()
    state_1 = state.copy()

    # Randomize attestation participation of both
    randomize_attestation_participation(spec, state_0, rng=Random(3333))
    randomize_attestation_participation(spec, state_1, rng=Random(4444))

    # Note: `run_fork_test` empties `current_epoch_attestations`
    # Use pending attestations from both random states in a single state for testing
    state_0.previous_epoch_attestations = (
        state_0.previous_epoch_attestations + state_1.previous_epoch_attestations
    )
    yield from run_fork_test(phases[ALTAIR], state_0)


@with_phases(phases=[PHASE0], other_phases=[ALTAIR])
@spec_test
@with_custom_state(
    balances_fn=low_balances, threshold_fn=lambda spec: spec.config.EJECTION_BALANCE
)
@with_meta_tags(ALTAIR_FORK_TEST_META_TAGS)
def test_altair_fork_random_low_balances(spec, phases, state):
    randomize_state(spec, state, rng=Random(5050))
    yield from run_fork_test(phases[ALTAIR], state)


@with_phases(phases=[PHASE0], other_phases=[ALTAIR])
@spec_test
@with_custom_state(
    balances_fn=misc_balances, threshold_fn=lambda spec: spec.config.EJECTION_BALANCE
)
@with_meta_tags(ALTAIR_FORK_TEST_META_TAGS)
def test_altair_fork_random_misc_balances(spec, phases, state):
    randomize_state(spec, state, rng=Random(6060))
    yield from run_fork_test(phases[ALTAIR], state)


@with_phases(phases=[PHASE0], other_phases=[ALTAIR])
@with_presets(
    [MINIMAL],
    reason="mainnet config leads to larger validator set than limit of public/private keys pre-generated",
)
@spec_test
@with_custom_state(
    balances_fn=large_validator_set,
    threshold_fn=lambda spec: spec.config.EJECTION_BALANCE,
)
@with_meta_tags(ALTAIR_FORK_TEST_META_TAGS)
def test_altair_fork_random_large_validator_set(spec, phases, state):
    randomize_state(spec, state, rng=Random(7070))
    yield from run_fork_test(phases[ALTAIR], state)
