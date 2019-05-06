import pytest

import eth2spec.phase0.spec as spec

from eth2spec.phase0.spec import (
    get_active_validator_indices,
    get_churn_limit,
    get_current_epoch,
    process_voluntary_exit,
)
from tests.helpers import (
    build_voluntary_exit,
    pubkey_to_privkey,
)

from tests.context import spec_state_test


def run_voluntary_exit_processing(state, voluntary_exit, valid=True):
    """
    Run ``process_voluntary_exit``, yielding:
      - pre-state ('pre')
      - voluntary_exit ('voluntary_exit')
      - post-state ('post').
    If ``valid == False``, run expecting ``AssertionError``
    """
    validator_index = voluntary_exit.validator_index
    pre_exit_epoch = state.validator_registry[validator_index].exit_epoch

    yield 'pre', state
    yield 'voluntary_exit', voluntary_exit

    if not valid:
        with pytest.raises(AssertionError):
            process_voluntary_exit(state, voluntary_exit)
        yield 'post', None
        return

    process_voluntary_exit(state, voluntary_exit)

    yield 'post', state

    assert pre_exit_epoch == spec.FAR_FUTURE_EPOCH
    assert state.validator_registry[validator_index].exit_epoch < spec.FAR_FUTURE_EPOCH


@spec_state_test
def test_success(state):
    # move state forward PERSISTENT_COMMITTEE_PERIOD epochs to allow for exit
    state.slot += spec.PERSISTENT_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    current_epoch = get_current_epoch(state)
    validator_index = get_active_validator_indices(state, current_epoch)[0]
    privkey = pubkey_to_privkey[state.validator_registry[validator_index].pubkey]

    voluntary_exit = build_voluntary_exit(
        state,
        current_epoch,
        validator_index,
        privkey,
    )

    yield from run_voluntary_exit_processing(state, voluntary_exit)


@spec_state_test
def test_success_exit_queue(state):
    # move state forward PERSISTENT_COMMITTEE_PERIOD epochs to allow for exit
    state.slot += spec.PERSISTENT_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    current_epoch = get_current_epoch(state)

    # exit `MAX_EXITS_PER_EPOCH`
    initial_indices = get_active_validator_indices(state, current_epoch)[:get_churn_limit(state)]

    # Prepare a bunch of exits, based on the current state
    exit_queue = []
    for index in initial_indices:
        privkey = pubkey_to_privkey[state.validator_registry[index].pubkey]
        exit_queue.append(build_voluntary_exit(
            state,
            current_epoch,
            index,
            privkey,
        ))

    # Now run all the exits
    for voluntary_exit in exit_queue:
        # the function yields data, but we are just interested in running it here, ignore yields.
        for _ in run_voluntary_exit_processing(state, voluntary_exit):
            continue

    # exit an additional validator
    validator_index = get_active_validator_indices(state, current_epoch)[-1]
    privkey = pubkey_to_privkey[state.validator_registry[validator_index].pubkey]
    voluntary_exit = build_voluntary_exit(
        state,
        current_epoch,
        validator_index,
        privkey,
    )

    # This is the interesting part of the test: on a pre-state with a full exit queue,
    #  when processing an additional exit, it results in an exit in a later epoch
    yield from run_voluntary_exit_processing(state, voluntary_exit)

    assert (
        state.validator_registry[validator_index].exit_epoch ==
        state.validator_registry[initial_indices[0]].exit_epoch + 1
    )


@spec_state_test
def test_validator_not_active(state):
    current_epoch = get_current_epoch(state)
    validator_index = get_active_validator_indices(state, current_epoch)[0]
    privkey = pubkey_to_privkey[state.validator_registry[validator_index].pubkey]

    state.validator_registry[validator_index].activation_epoch = spec.FAR_FUTURE_EPOCH

    # build and test voluntary exit
    voluntary_exit = build_voluntary_exit(
        state,
        current_epoch,
        validator_index,
        privkey,
    )

    yield from run_voluntary_exit_processing(state, voluntary_exit, False)


@spec_state_test
def test_validator_already_exited(state):
    # move state forward PERSISTENT_COMMITTEE_PERIOD epochs to allow validator able to exit
    state.slot += spec.PERSISTENT_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    current_epoch = get_current_epoch(state)
    validator_index = get_active_validator_indices(state, current_epoch)[0]
    privkey = pubkey_to_privkey[state.validator_registry[validator_index].pubkey]

    # but validator already has exited
    state.validator_registry[validator_index].exit_epoch = current_epoch + 2

    voluntary_exit = build_voluntary_exit(
        state,
        current_epoch,
        validator_index,
        privkey,
    )

    yield from run_voluntary_exit_processing(state, voluntary_exit, False)


@spec_state_test
def test_validator_not_active_long_enough(state):
    current_epoch = get_current_epoch(state)
    validator_index = get_active_validator_indices(state, current_epoch)[0]
    privkey = pubkey_to_privkey[state.validator_registry[validator_index].pubkey]

    voluntary_exit = build_voluntary_exit(
        state,
        current_epoch,
        validator_index,
        privkey,
    )

    assert (
        current_epoch - state.validator_registry[validator_index].activation_epoch <
        spec.PERSISTENT_COMMITTEE_PERIOD
    )

    yield from run_voluntary_exit_processing(state, voluntary_exit, False)
