from random import Random

from eth2spec.test.context import spec_state_test, with_altair_and_later
from eth2spec.test.helpers.inactivity_scores import randomize_inactivity_scores, zero_inactivity_scores
from eth2spec.test.helpers.state import (
    next_epoch_via_block,
    set_full_participation,
    set_empty_participation,
)
from eth2spec.test.helpers.epoch_processing import (
    run_epoch_processing_with
)
from eth2spec.test.helpers.random import (
    randomize_attestation_participation,
    randomize_previous_epoch_participation,
)
from eth2spec.test.helpers.rewards import leaking


def run_process_inactivity_updates(spec, state):
    yield from run_epoch_processing_with(spec, state, 'process_inactivity_updates')


@with_altair_and_later
@spec_state_test
def test_genesis(spec, state):
    yield from run_process_inactivity_updates(spec, state)


@with_altair_and_later
@spec_state_test
def test_genesis_random_scores(spec, state):
    rng = Random(10102)
    state.inactivity_scores = [rng.randint(0, 100) for _ in state.inactivity_scores]
    pre_scores = state.inactivity_scores.copy()

    yield from run_process_inactivity_updates(spec, state)

    assert state.inactivity_scores == pre_scores


#
# Genesis epoch processing is skipped
# Thus all of following tests all go past genesis epoch to test core functionality
#

def run_inactivity_scores_test(spec, state, participation_fn=None, inactivity_scores_fn=None, rng=Random(10101)):
    next_epoch_via_block(spec, state)
    if participation_fn is not None:
        participation_fn(spec, state, rng=rng)
    if inactivity_scores_fn is not None:
        inactivity_scores_fn(spec, state, rng=rng)
    yield from run_process_inactivity_updates(spec, state)


@with_altair_and_later
@spec_state_test
def test_all_zero_inactivity_scores_empty_participation(spec, state):
    yield from run_inactivity_scores_test(spec, state, set_empty_participation, zero_inactivity_scores)
    assert set(state.inactivity_scores) == set([0])


@with_altair_and_later
@spec_state_test
@leaking()
def test_all_zero_inactivity_scores_empty_participation_leaking(spec, state):
    yield from run_inactivity_scores_test(spec, state, set_empty_participation, zero_inactivity_scores)

    # Should still in be leak
    assert spec.is_in_inactivity_leak(state)

    for score in state.inactivity_scores:
        assert score > 0


@with_altair_and_later
@spec_state_test
def test_all_zero_inactivity_scores_random_participation(spec, state):
    yield from run_inactivity_scores_test(
        spec, state,
        randomize_attestation_participation, zero_inactivity_scores, rng=Random(5555),
    )
    assert set(state.inactivity_scores) == set([0])


@with_altair_and_later
@spec_state_test
@leaking()
def test_all_zero_inactivity_scores_random_participation_leaking(spec, state):
    # Only randomize participation in previous epoch to remain in leak
    yield from run_inactivity_scores_test(
        spec, state,
        randomize_previous_epoch_participation, zero_inactivity_scores, rng=Random(5555),
    )

    # Check still in leak
    assert spec.is_in_inactivity_leak(state)

    assert 0 in state.inactivity_scores
    assert len(set(state.inactivity_scores)) > 1


@with_altair_and_later
@spec_state_test
def test_all_zero_inactivity_scores_full_participation(spec, state):
    yield from run_inactivity_scores_test(
        spec, state,
        set_full_participation, zero_inactivity_scores,
    )

    assert set(state.inactivity_scores) == set([0])


@with_altair_and_later
@spec_state_test
@leaking()
def test_all_zero_inactivity_scores_full_participation_leaking(spec, state):
    # Only set full participation in previous epoch to remain in leak
    yield from run_inactivity_scores_test(
        spec, state,
        set_full_participation, zero_inactivity_scores,
    )

    # Check still in leak
    assert spec.is_in_inactivity_leak(state)

    assert set(state.inactivity_scores) == set([0])


@with_altair_and_later
@spec_state_test
def test_random_inactivity_scores_empty_participation(spec, state):
    yield from run_inactivity_scores_test(
        spec, state,
        set_empty_participation, randomize_inactivity_scores, Random(9999),
    )


@with_altair_and_later
@spec_state_test
@leaking()
def test_random_inactivity_scores_empty_participation_leaking(spec, state):
    yield from run_inactivity_scores_test(
        spec, state,
        set_empty_participation, randomize_inactivity_scores, Random(9999),
    )

    # Check still in leak
    assert spec.is_in_inactivity_leak(state)


@with_altair_and_later
@spec_state_test
def test_random_inactivity_scores_random_participation(spec, state):
    yield from run_inactivity_scores_test(
        spec, state,
        randomize_attestation_participation, randomize_inactivity_scores, Random(22222),
    )


@with_altair_and_later
@spec_state_test
@leaking()
def test_random_inactivity_scores_random_participation_leaking(spec, state):
    # Only randompize participation in previous epoch to remain in leak
    yield from run_inactivity_scores_test(
        spec, state,
        randomize_previous_epoch_participation, randomize_inactivity_scores, Random(22222),
    )

    # Check still in leak
    assert spec.is_in_inactivity_leak(state)


@with_altair_and_later
@spec_state_test
def test_random_inactivity_scores_full_participation(spec, state):
    yield from run_inactivity_scores_test(
        spec, state,
        set_full_participation, randomize_inactivity_scores, Random(33333),
    )


@with_altair_and_later
@spec_state_test
@leaking()
def test_random_inactivity_scores_full_participation_leaking(spec, state):
    # Only set full participation in previous epoch to remain in leak
    yield from run_inactivity_scores_test(
        spec, state,
        set_full_participation, randomize_inactivity_scores, Random(33333),
    )

    # Check still in leak
    assert spec.is_in_inactivity_leak(state)


def slash_some_validators_for_inactivity_scores_test(spec, state, rng=Random(40404040)):
    # ``run_inactivity_scores_test`` runs at the next epoch from `state`.
    # We retrieve the proposer of this future state to avoid
    # accidentally slashing that validator
    future_state = state.copy()
    next_epoch_via_block(spec, future_state)

    proposer_index = spec.get_beacon_proposer_index(future_state)
    # Slash ~1/4 of validaors
    for validator_index in range(len(state.validators)):
        if rng.choice(range(4)) == 0 and validator_index != proposer_index:
            spec.slash_validator(state, validator_index)


@with_altair_and_later
@spec_state_test
def test_some_slashed_zero_scores_full_participation(spec, state):
    slash_some_validators_for_inactivity_scores_test(spec, state, rng=Random(33429))
    yield from run_inactivity_scores_test(
        spec, state,
        set_full_participation, zero_inactivity_scores,
    )

    assert set(state.inactivity_scores) == set([0])


@with_altair_and_later
@spec_state_test
@leaking()
def test_some_slashed_zero_scores_full_participation_leaking(spec, state):
    slash_some_validators_for_inactivity_scores_test(spec, state, rng=Random(332243))
    yield from run_inactivity_scores_test(
        spec, state,
        set_full_participation, zero_inactivity_scores,
    )

    # Check still in leak
    assert spec.is_in_inactivity_leak(state)

    # Ensure some zero scores (non-slashed values) and non-zero scores (slashed vals) in there
    for score, validator in zip(state.inactivity_scores, state.validators):
        if validator.slashed:
            assert score > 0
        else:
            assert score == 0


@with_altair_and_later
@spec_state_test
def test_some_slashed_full_random(spec, state):
    rng = Random(1010222)
    slash_some_validators_for_inactivity_scores_test(spec, state, rng=rng)
    yield from run_inactivity_scores_test(
        spec, state,
        randomize_attestation_participation, randomize_inactivity_scores, rng=rng,
    )


@with_altair_and_later
@spec_state_test
@leaking()
def test_some_slashed_full_random_leaking(spec, state):
    rng = Random(1102233)
    slash_some_validators_for_inactivity_scores_test(spec, state, rng=rng)
    yield from run_inactivity_scores_test(
        spec, state,
        randomize_previous_epoch_participation, randomize_inactivity_scores, rng=rng,
    )

    # Check still in leak
    assert spec.is_in_inactivity_leak(state)
