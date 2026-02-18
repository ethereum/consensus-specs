from random import Random

from eth_consensus_specs.test.context import spec_state_test, with_altair_and_later
from eth_consensus_specs.test.helpers.epoch_processing import run_epoch_processing_with
from eth_consensus_specs.test.helpers.inactivity_scores import (
    randomize_inactivity_scores,
    zero_inactivity_scores,
)
from eth_consensus_specs.test.helpers.random import (
    randomize_attestation_participation,
    randomize_previous_epoch_participation,
    randomize_state,
)
from eth_consensus_specs.test.helpers.rewards import leaking
from eth_consensus_specs.test.helpers.state import (
    next_epoch,
    next_epoch_via_block,
    set_empty_participation,
    set_full_participation,
)
from eth_consensus_specs.test.helpers.voluntary_exits import exit_validators, get_exited_validators


def run_process_inactivity_updates(spec, state):
    yield from run_epoch_processing_with(spec, state, "process_inactivity_updates")


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


def run_inactivity_scores_test(
    spec, state, participation_fn=None, inactivity_scores_fn=None, rng=None
):
    if rng is None:
        rng = Random(10101)
    while True:
        try:
            next_epoch_via_block(spec, state)
        except AssertionError:
            # If the proposer is slashed, we skip this epoch and try to propose block at the next epoch
            next_epoch(spec, state)
        else:
            break

    if participation_fn is not None:
        participation_fn(spec, state, rng=rng)
    if inactivity_scores_fn is not None:
        inactivity_scores_fn(spec, state, rng=rng)
    yield from run_process_inactivity_updates(spec, state)


@with_altair_and_later
@spec_state_test
def test_all_zero_inactivity_scores_empty_participation(spec, state):
    yield from run_inactivity_scores_test(
        spec, state, set_empty_participation, zero_inactivity_scores
    )
    assert set(state.inactivity_scores) == set([0])


@with_altair_and_later
@spec_state_test
@leaking()
def test_all_zero_inactivity_scores_empty_participation_leaking(spec, state):
    yield from run_inactivity_scores_test(
        spec, state, set_empty_participation, zero_inactivity_scores
    )

    # Should still in be leak
    assert spec.is_in_inactivity_leak(state)

    for score in state.inactivity_scores:
        assert score > 0


@with_altair_and_later
@spec_state_test
def test_all_zero_inactivity_scores_random_participation(spec, state):
    yield from run_inactivity_scores_test(
        spec,
        state,
        randomize_attestation_participation,
        zero_inactivity_scores,
        rng=Random(5555),
    )
    assert set(state.inactivity_scores) == set([0])


@with_altair_and_later
@spec_state_test
@leaking()
def test_all_zero_inactivity_scores_random_participation_leaking(spec, state):
    # Only randomize participation in previous epoch to remain in leak
    yield from run_inactivity_scores_test(
        spec,
        state,
        randomize_previous_epoch_participation,
        zero_inactivity_scores,
        rng=Random(5555),
    )

    # Check still in leak
    assert spec.is_in_inactivity_leak(state)

    assert 0 in state.inactivity_scores
    assert len(set(state.inactivity_scores)) > 1


@with_altair_and_later
@spec_state_test
def test_all_zero_inactivity_scores_full_participation(spec, state):
    yield from run_inactivity_scores_test(
        spec,
        state,
        set_full_participation,
        zero_inactivity_scores,
    )

    assert set(state.inactivity_scores) == set([0])


@with_altair_and_later
@spec_state_test
@leaking()
def test_all_zero_inactivity_scores_full_participation_leaking(spec, state):
    # Only set full participation in previous epoch to remain in leak
    yield from run_inactivity_scores_test(
        spec,
        state,
        set_full_participation,
        zero_inactivity_scores,
    )

    # Check still in leak
    assert spec.is_in_inactivity_leak(state)

    assert set(state.inactivity_scores) == set([0])


@with_altair_and_later
@spec_state_test
def test_random_inactivity_scores_empty_participation(spec, state):
    yield from run_inactivity_scores_test(
        spec,
        state,
        set_empty_participation,
        randomize_inactivity_scores,
        Random(9999),
    )


@with_altair_and_later
@spec_state_test
@leaking()
def test_random_inactivity_scores_empty_participation_leaking(spec, state):
    yield from run_inactivity_scores_test(
        spec,
        state,
        set_empty_participation,
        randomize_inactivity_scores,
        Random(9999),
    )

    # Check still in leak
    assert spec.is_in_inactivity_leak(state)


@with_altair_and_later
@spec_state_test
def test_random_inactivity_scores_random_participation(spec, state):
    yield from run_inactivity_scores_test(
        spec,
        state,
        randomize_attestation_participation,
        randomize_inactivity_scores,
        Random(22222),
    )


@with_altair_and_later
@spec_state_test
@leaking()
def test_random_inactivity_scores_random_participation_leaking(spec, state):
    # Only randomize participation in previous epoch to remain in leak
    yield from run_inactivity_scores_test(
        spec,
        state,
        randomize_previous_epoch_participation,
        randomize_inactivity_scores,
        Random(22222),
    )

    # Check still in leak
    assert spec.is_in_inactivity_leak(state)


@with_altair_and_later
@spec_state_test
def test_random_inactivity_scores_full_participation(spec, state):
    yield from run_inactivity_scores_test(
        spec,
        state,
        set_full_participation,
        randomize_inactivity_scores,
        Random(33333),
    )


@with_altair_and_later
@spec_state_test
@leaking()
def test_random_inactivity_scores_full_participation_leaking(spec, state):
    # Only set full participation in previous epoch to remain in leak
    yield from run_inactivity_scores_test(
        spec,
        state,
        set_full_participation,
        randomize_inactivity_scores,
        Random(33333),
    )

    # Check still in leak
    assert spec.is_in_inactivity_leak(state)


def slash_some_validators_for_inactivity_scores_test(spec, state, rng=None):
    if rng is None:
        rng = Random(40404040)
    # ``run_inactivity_scores_test`` runs at the next epoch from `state`.
    # We retrieve the proposer of this future state to avoid
    # accidentally slashing that validator
    future_state = state.copy()
    next_epoch_via_block(spec, future_state)

    proposer_index = spec.get_beacon_proposer_index(future_state)
    # Slash ~1/4 of validators
    for validator_index in range(len(state.validators)):
        if rng.choice(range(4)) == 0 and validator_index != proposer_index:
            spec.slash_validator(state, validator_index)


@with_altair_and_later
@spec_state_test
def test_some_slashed_zero_scores_full_participation(spec, state):
    slash_some_validators_for_inactivity_scores_test(spec, state, rng=Random(33429))
    yield from run_inactivity_scores_test(
        spec,
        state,
        set_full_participation,
        zero_inactivity_scores,
    )

    assert set(state.inactivity_scores) == set([0])


@with_altair_and_later
@spec_state_test
@leaking()
def test_some_slashed_zero_scores_full_participation_leaking(spec, state):
    slash_some_validators_for_inactivity_scores_test(spec, state, rng=Random(332243))
    yield from run_inactivity_scores_test(
        spec,
        state,
        set_full_participation,
        zero_inactivity_scores,
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
        spec,
        state,
        randomize_attestation_participation,
        randomize_inactivity_scores,
        rng=rng,
    )


@with_altair_and_later
@spec_state_test
@leaking()
def test_some_slashed_full_random_leaking(spec, state):
    rng = Random(1102233)
    slash_some_validators_for_inactivity_scores_test(spec, state, rng=rng)
    yield from run_inactivity_scores_test(
        spec,
        state,
        randomize_previous_epoch_participation,
        randomize_inactivity_scores,
        rng=rng,
    )

    # Check still in leak
    assert spec.is_in_inactivity_leak(state)


@with_altair_and_later
@spec_state_test
@leaking()
def test_some_exited_full_random_leaking(spec, state):
    rng = Random(1102233)

    exit_count = 3

    # randomize ahead of time to check exited validators do not have
    # mutations applied to their inactivity scores
    randomize_inactivity_scores(spec, state, rng=rng)

    assert not any(get_exited_validators(spec, state))
    exited_indices = exit_validators(spec, state, exit_count, rng=rng)
    assert not any(get_exited_validators(spec, state))

    # advance the state to effect the exits
    target_epoch = max(state.validators[index].exit_epoch for index in exited_indices)
    # validators that have exited in the previous epoch or earlier will not
    # have their inactivity scores modified, the test advances the state past this point
    # to confirm this invariant:
    previous_epoch = spec.get_previous_epoch(state)
    for _ in range(target_epoch - previous_epoch):
        next_epoch(spec, state)
    assert len(get_exited_validators(spec, state)) == exit_count

    previous_scores = state.inactivity_scores.copy()

    yield from run_inactivity_scores_test(
        spec,
        state,
        randomize_previous_epoch_participation,
        rng=rng,
    )

    # ensure exited validators have their score "frozen" at exit
    # but otherwise there was a change
    some_changed = False
    for index in range(len(state.validators)):
        if index in exited_indices:
            assert previous_scores[index] == state.inactivity_scores[index]
        else:
            previous_score = previous_scores[index]
            current_score = state.inactivity_scores[index]
            if previous_score != current_score:
                some_changed = True
    assert some_changed

    # Check still in leak
    assert spec.is_in_inactivity_leak(state)


def _run_randomized_state_test_for_inactivity_updates(spec, state, rng=None):
    if rng is None:
        rng = Random(13377331)
    randomize_inactivity_scores(spec, state, rng=rng)
    randomize_state(spec, state, rng=rng)

    exited_validators = get_exited_validators(spec, state)
    exited_but_not_slashed = []
    for index in exited_validators:
        validator = state.validators[index]
        if validator.slashed:
            continue
        exited_but_not_slashed.append(index)

    assert len(exited_but_not_slashed) > 0

    some_exited_validator = exited_but_not_slashed[0]

    pre_score_for_exited_validator = state.inactivity_scores[some_exited_validator]

    assert pre_score_for_exited_validator != 0

    assert len(set(state.inactivity_scores)) > 1

    yield from run_inactivity_scores_test(spec, state)

    post_score_for_exited_validator = state.inactivity_scores[some_exited_validator]
    assert pre_score_for_exited_validator == post_score_for_exited_validator


@with_altair_and_later
@spec_state_test
def test_randomized_state(spec, state):
    """
    This test ensures that once a validator has exited,
    their inactivity score does not change.
    """
    rng = Random(10011001)
    yield from _run_randomized_state_test_for_inactivity_updates(spec, state, rng=rng)


@with_altair_and_later
@spec_state_test
@leaking()
def test_randomized_state_leaking(spec, state):
    """
    This test ensures that once a validator has exited,
    their inactivity score does not change, even during a leak.
    Note that slashed validators are still subject to mutations
    (refer ``get_eligible_validator_indices`).
    """
    rng = Random(10011002)
    yield from _run_randomized_state_test_for_inactivity_updates(spec, state, rng=rng)
    # Check still in leak
    assert spec.is_in_inactivity_leak(state)
