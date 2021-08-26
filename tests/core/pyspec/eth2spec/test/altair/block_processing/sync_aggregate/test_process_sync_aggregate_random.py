import random
from eth2spec.test.helpers.constants import (
    MAINNET, MINIMAL,
)
from eth2spec.test.helpers.sync_committee import (
    get_committee_indices,
    run_successful_sync_committee_test,
)
from eth2spec.test.context import (
    with_altair_and_later,
    spec_state_test,
    default_activation_threshold,
    misc_balances,
    single_phase,
    with_custom_state,
    with_presets,
    spec_test,
)


def _test_harness_for_randomized_test_case(spec, state, duplicates=False, participation_fn=None):
    committee_indices = get_committee_indices(spec, state, duplicates=duplicates)

    if participation_fn:
        participating_indices = participation_fn(committee_indices)
    else:
        participating_indices = committee_indices

    committee_bits = [index in participating_indices for index in committee_indices]
    committee_size = len(committee_indices)
    if duplicates:
        assert committee_size > len(set(committee_indices))
    else:
        assert committee_size == len(set(committee_indices))

    yield from run_successful_sync_committee_test(spec, state, committee_indices, committee_bits)


@with_altair_and_later
@with_presets([MAINNET], reason="to create duplicate committee")
@spec_state_test
def test_random_only_one_participant_with_duplicates(spec, state):
    rng = random.Random(101)
    yield from _test_harness_for_randomized_test_case(
        spec,
        state,
        duplicates=True,
        participation_fn=lambda comm: [rng.choice(comm)],
    )


@with_altair_and_later
@with_presets([MAINNET], reason="to create duplicate committee")
@spec_state_test
def test_random_low_participation_with_duplicates(spec, state):
    rng = random.Random(201)
    yield from _test_harness_for_randomized_test_case(
        spec,
        state,
        duplicates=True,
        participation_fn=lambda comm: rng.sample(comm, int(len(comm) * 0.25)),
    )


@with_altair_and_later
@with_presets([MAINNET], reason="to create duplicate committee")
@spec_state_test
def test_random_high_participation_with_duplicates(spec, state):
    rng = random.Random(301)
    yield from _test_harness_for_randomized_test_case(
        spec,
        state,
        duplicates=True,
        participation_fn=lambda comm: rng.sample(comm, int(len(comm) * 0.75)),
    )


@with_altair_and_later
@with_presets([MAINNET], reason="to create duplicate committee")
@spec_state_test
def test_random_all_but_one_participating_with_duplicates(spec, state):
    rng = random.Random(401)
    yield from _test_harness_for_randomized_test_case(
        spec,
        state,
        duplicates=True,
        participation_fn=lambda comm: rng.sample(comm, len(comm) - 1),
    )


@with_altair_and_later
@with_presets([MAINNET], reason="to create duplicate committee")
@spec_test
@with_custom_state(balances_fn=misc_balances, threshold_fn=default_activation_threshold)
@single_phase
def test_random_misc_balances_and_half_participation_with_duplicates(spec, state):
    rng = random.Random(1401)
    yield from _test_harness_for_randomized_test_case(
        spec,
        state,
        duplicates=True,
        participation_fn=lambda comm: rng.sample(comm, len(comm) // 2),
    )


@with_altair_and_later
@with_presets([MINIMAL], reason="to create nonduplicate committee")
@spec_state_test
def test_random_only_one_participant_without_duplicates(spec, state):
    rng = random.Random(501)
    yield from _test_harness_for_randomized_test_case(
        spec,
        state,
        participation_fn=lambda comm: [rng.choice(comm)],
    )


@with_altair_and_later
@with_presets([MINIMAL], reason="to create nonduplicate committee")
@spec_state_test
def test_random_low_participation_without_duplicates(spec, state):
    rng = random.Random(601)
    yield from _test_harness_for_randomized_test_case(
        spec,
        state,
        participation_fn=lambda comm: rng.sample(comm, int(len(comm) * 0.25)),
    )


@with_altair_and_later
@with_presets([MINIMAL], reason="to create nonduplicate committee")
@spec_state_test
def test_random_high_participation_without_duplicates(spec, state):
    rng = random.Random(701)
    yield from _test_harness_for_randomized_test_case(
        spec,
        state,
        participation_fn=lambda comm: rng.sample(comm, int(len(comm) * 0.75)),
    )


@with_altair_and_later
@with_presets([MINIMAL], reason="to create nonduplicate committee")
@spec_state_test
def test_random_all_but_one_participating_without_duplicates(spec, state):
    rng = random.Random(801)
    yield from _test_harness_for_randomized_test_case(
        spec,
        state,
        participation_fn=lambda comm: rng.sample(comm, len(comm) - 1),
    )


@with_altair_and_later
@with_presets([MINIMAL], reason="to create nonduplicate committee")
@spec_test
@with_custom_state(balances_fn=misc_balances, threshold_fn=default_activation_threshold)
@single_phase
def test_random_misc_balances_and_half_participation_without_duplicates(spec, state):
    rng = random.Random(1501)
    yield from _test_harness_for_randomized_test_case(
        spec,
        state,
        participation_fn=lambda comm: rng.sample(comm, len(comm) // 2),
    )
