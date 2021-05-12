from random import Random

from eth2spec.test.context import spec_state_test, with_altair_and_later
from eth2spec.test.helpers.inactivity_scores import randomize_inactivity_scores
from eth2spec.test.helpers.state import (
    next_epoch_via_block,
)
from eth2spec.test.helpers.epoch_processing import (
    run_epoch_processing_with
)


def set_full_participation(spec, state):
    full_flags = spec.ParticipationFlags(0)
    for flag_index in range(len(spec.PARTICIPATION_FLAG_WEIGHTS)):
        full_flags = spec.add_flag(full_flags, flag_index)

    for index in range(len(state.validators)):
        state.previous_epoch_participation[index] = full_flags


def randomize_flags(spec, state, rng=Random(2080)):
    for index in range(len(state.validators)):
        # ~1/3 have bad head or bad target or not timely enough
        is_timely_correct_head = rng.randint(0, 2) != 0
        flags = state.previous_epoch_participation[index]

        def set_flag(index, value):
            nonlocal flags
            flag = spec.ParticipationFlags(2**index)
            if value:
                flags |= flag
            else:
                flags &= 0xff ^ flag

        set_flag(spec.TIMELY_HEAD_FLAG_INDEX, is_timely_correct_head)
        if is_timely_correct_head:
            # If timely head, then must be timely target
            set_flag(spec.TIMELY_TARGET_FLAG_INDEX, True)
            # If timely head, then must be timely source
            set_flag(spec.TIMELY_SOURCE_FLAG_INDEX, True)
        else:
            # ~50% of remaining have bad target or not timely enough
            set_flag(spec.TIMELY_TARGET_FLAG_INDEX, rng.choice([True, False]))
            # ~50% of remaining have bad source or not timely enough
            set_flag(spec.TIMELY_SOURCE_FLAG_INDEX, rng.choice([True, False]))
        state.previous_epoch_participation[index] = flags


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
    state.inactivity_scores = [0] * len(state.validators)
    yield from run_process_inactivity_updates(spec, state)


@with_altair_and_later
@spec_state_test
def test_all_zero_inactivity_scores_random_participation(spec, state):
    next_epoch_via_block(spec, state)
    state.inactivity_scores = [0] * len(state.validators)
    randomize_flags(spec, state)
    yield from run_process_inactivity_updates(spec, state)


@with_altair_and_later
@spec_state_test
def test_all_zero_inactivity_scores_full_participation(spec, state):
    next_epoch_via_block(spec, state)
    state.inactivity_scores = [0] * len(state.validators)
    set_full_participation(spec, state)
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
    randomize_inactivity_scores(spec, state, rng=Random(22222))
    randomize_flags(spec, state)
    yield from run_process_inactivity_updates(spec, state)


@with_altair_and_later
@spec_state_test
def test_random_inactivity_scores_full_participation(spec, state):
    next_epoch_via_block(spec, state)
    randomize_inactivity_scores(spec, state, rng=Random(33333))
    set_full_participation(spec, state)
    yield from run_process_inactivity_updates(spec, state)
