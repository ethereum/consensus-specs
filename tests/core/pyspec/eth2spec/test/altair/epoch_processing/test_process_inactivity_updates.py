from random import Random

from eth2spec.test.context import spec_state_test, with_altair_and_later
from eth2spec.test.helpers.inactivity_scores import randomize_inactivity_scores
from eth2spec.test.helpers.state import (
    next_epoch_via_block,
)
from eth2spec.test.helpers.epoch_processing import (
    run_epoch_processing_with
)
from eth2spec.test.helpers.random import (
    randomize_attestation_participation,
)


def set_full_participation(spec, state):
    full_flags = spec.ParticipationFlags(0)
    for flag_index in range(len(spec.PARTICIPATION_FLAG_WEIGHTS)):
        full_flags = spec.add_flag(full_flags, flag_index)

    for index in range(len(state.validators)):
        state.current_epoch_participation[index] = full_flags
        state.previous_epoch_participation[index] = full_flags


def run_process_inactivity_updates(spec, state):
    yield from run_epoch_processing_with(spec, state, 'process_inactivity_updates')


@with_altair_and_later
@spec_state_test
def test_genesis(spec, state):
    yield from run_process_inactivity_updates(spec, state)


#
# Genesis epoch processing is skipped
# Thus all of following tests all go past genesis epoch to test core functionality
#

@with_altair_and_later
@spec_state_test
def test_all_zero_inactivity_scores_empty_participation(spec, state):
    next_epoch_via_block(spec, state)
    state.inactivity_scores = [0] * len(state.validators)
    yield from run_process_inactivity_updates(spec, state)


@with_altair_and_later
@spec_state_test
def test_all_zero_inactivity_scores_random_participation(spec, state):
    next_epoch_via_block(spec, state)
    state.inactivity_scores = [0] * len(state.validators)
    randomize_attestation_participation(spec, state, rng=Random(5555))
    yield from run_process_inactivity_updates(spec, state)


@with_altair_and_later
@spec_state_test
def test_all_zero_inactivity_scores_full_participation(spec, state):
    next_epoch_via_block(spec, state)
    set_full_participation(spec, state)
    state.inactivity_scores = [0] * len(state.validators)
    yield from run_process_inactivity_updates(spec, state)


@with_altair_and_later
@spec_state_test
def test_random_inactivity_scores_empty_participation(spec, state):
    next_epoch_via_block(spec, state)
    randomize_inactivity_scores(spec, state, rng=Random(9999))
    yield from run_process_inactivity_updates(spec, state)


@with_altair_and_later
@spec_state_test
def test_random_inactivity_scores_random_participation(spec, state):
    next_epoch_via_block(spec, state)
    randomize_attestation_participation(spec, state, rng=Random(22222))
    randomize_inactivity_scores(spec, state, rng=Random(22222))
    yield from run_process_inactivity_updates(spec, state)


@with_altair_and_later
@spec_state_test
def test_random_inactivity_scores_full_participation(spec, state):
    next_epoch_via_block(spec, state)
    set_full_participation(spec, state)
    randomize_inactivity_scores(spec, state, rng=Random(33333))
    yield from run_process_inactivity_updates(spec, state)
