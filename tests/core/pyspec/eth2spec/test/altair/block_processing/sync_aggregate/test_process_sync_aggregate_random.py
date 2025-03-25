import random
from eth2spec.test.helpers.constants import (
    MAINNET,
    MINIMAL,
)
from eth2spec.test.helpers.random import (
    randomize_state,
)
from eth2spec.test.helpers.state import (
    has_active_balance_differential,
)
from eth2spec.test.helpers.sync_committee import (
    compute_committee_indices,
    run_successful_sync_committee_test,
)
from eth2spec.test.helpers.voluntary_exits import (
    get_unslashed_exited_validators,
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
    default_balances_electra,
    misc_balances_electra,
)


def _test_harness_for_randomized_test_case(
    spec, state, expect_duplicates=False, participation_fn=None
):
    committee_indices = compute_committee_indices(state)

    if participation_fn:
        participating_indices = participation_fn(committee_indices)
    else:
        participating_indices = committee_indices

    committee_bits = [index in participating_indices for index in committee_indices]
    committee_size = len(committee_indices)
    if expect_duplicates:
        assert committee_size > len(set(committee_indices))
    else:
        assert committee_size == len(set(committee_indices))

    yield from run_successful_sync_committee_test(
        spec, state, committee_indices, committee_bits
    )


@with_altair_and_later
@with_presets([MAINNET], reason="to create duplicate committee")
@spec_state_test
def test_random_only_one_participant_with_duplicates(spec, state):
    rng = random.Random(101)
    yield from _test_harness_for_randomized_test_case(
        spec,
        state,
        expect_duplicates=True,
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
        expect_duplicates=True,
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
        expect_duplicates=True,
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
        expect_duplicates=True,
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
        expect_duplicates=True,
        participation_fn=lambda comm: rng.sample(comm, len(comm) // 2),
    )


@with_altair_and_later
@with_presets([MAINNET], reason="to create duplicate committee")
@spec_state_test
@single_phase
def test_random_with_exits_with_duplicates(spec, state):
    rng = random.Random(1402)
    randomize_state(spec, state, rng=rng, exit_fraction=0.1, slash_fraction=0.0)
    target_validators = get_unslashed_exited_validators(spec, state)
    assert len(target_validators) != 0
    assert has_active_balance_differential(spec, state)
    yield from _test_harness_for_randomized_test_case(
        spec,
        state,
        expect_duplicates=True,
        participation_fn=lambda comm: rng.sample(comm, len(comm) // 2),
    )


@with_altair_and_later
@with_presets([MINIMAL], reason="to create nonduplicate committee")
@spec_test
@with_custom_state(
    balances_fn=default_balances_electra, threshold_fn=default_activation_threshold
)
@single_phase
def test_random_only_one_participant_without_duplicates(spec, state):
    rng = random.Random(501)
    yield from _test_harness_for_randomized_test_case(
        spec,
        state,
        participation_fn=lambda comm: [rng.choice(comm)],
    )


@with_altair_and_later
@with_presets([MINIMAL], reason="to create nonduplicate committee")
@spec_test
@with_custom_state(
    balances_fn=default_balances_electra, threshold_fn=default_activation_threshold
)
@single_phase
def test_random_low_participation_without_duplicates(spec, state):
    rng = random.Random(601)
    yield from _test_harness_for_randomized_test_case(
        spec,
        state,
        participation_fn=lambda comm: rng.sample(comm, int(len(comm) * 0.25)),
    )


@with_altair_and_later
@with_presets([MINIMAL], reason="to create nonduplicate committee")
@spec_test
@with_custom_state(
    balances_fn=default_balances_electra, threshold_fn=default_activation_threshold
)
@single_phase
def test_random_high_participation_without_duplicates(spec, state):
    rng = random.Random(701)
    yield from _test_harness_for_randomized_test_case(
        spec,
        state,
        participation_fn=lambda comm: rng.sample(comm, int(len(comm) * 0.75)),
    )


@with_altair_and_later
@with_presets([MINIMAL], reason="to create nonduplicate committee")
@spec_test
@with_custom_state(
    balances_fn=default_balances_electra, threshold_fn=default_activation_threshold
)
@single_phase
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
@with_custom_state(
    balances_fn=misc_balances_electra, threshold_fn=default_activation_threshold
)
@single_phase
def test_random_misc_balances_and_half_participation_without_duplicates(spec, state):
    rng = random.Random(1501)
    yield from _test_harness_for_randomized_test_case(
        spec,
        state,
        participation_fn=lambda comm: rng.sample(comm, len(comm) // 2),
    )


@with_altair_and_later
@with_presets([MINIMAL], reason="to create nonduplicate committee")
@spec_test
@with_custom_state(
    balances_fn=default_balances_electra, threshold_fn=default_activation_threshold
)
@single_phase
def test_random_with_exits_without_duplicates(spec, state):
    rng = random.Random(1502)
    randomize_state(spec, state, rng=rng, exit_fraction=0.1, slash_fraction=0.0)
    target_validators = get_unslashed_exited_validators(spec, state)
    assert len(target_validators) != 0
    assert has_active_balance_differential(spec, state)
    yield from _test_harness_for_randomized_test_case(
        spec,
        state,
        participation_fn=lambda comm: rng.sample(comm, len(comm) // 2),
    )
