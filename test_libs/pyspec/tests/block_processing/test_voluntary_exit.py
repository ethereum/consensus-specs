from copy import deepcopy
import pytest

import eth2spec.phase1.spec as spec

from eth2spec.phase1.spec import (
    get_active_validator_indices,
    get_churn_limit,
    get_current_epoch,
    process_voluntary_exit,
)
from tests.helpers import (
    build_voluntary_exit,
    pubkey_to_privkey,
)


# mark entire file as 'voluntary_exits'
pytestmark = pytest.mark.voluntary_exits


def run_voluntary_exit_processing(state, voluntary_exit, valid=True):
    """
    Run ``process_voluntary_exit`` returning the pre and post state.
    If ``valid == False``, run expecting ``AssertionError``
    """
    post_state = deepcopy(state)

    if not valid:
        with pytest.raises(AssertionError):
            process_voluntary_exit(post_state, voluntary_exit)
        return state, None

    process_voluntary_exit(post_state, voluntary_exit)

    validator_index = voluntary_exit.validator_index
    assert state.validator_registry[validator_index].exit_epoch == spec.FAR_FUTURE_EPOCH
    assert post_state.validator_registry[validator_index].exit_epoch < spec.FAR_FUTURE_EPOCH

    return state, post_state


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

    pre_state, post_state = run_voluntary_exit_processing(state, voluntary_exit)
    return pre_state, voluntary_exit, post_state


def test_success_exit_queue(state):
    # move state forward PERSISTENT_COMMITTEE_PERIOD epochs to allow for exit
    state.slot += spec.PERSISTENT_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    current_epoch = get_current_epoch(state)

    # exit `MAX_EXITS_PER_EPOCH`
    initial_indices = get_active_validator_indices(state, current_epoch)[:get_churn_limit(state)]
    post_state = state
    for index in initial_indices:
        privkey = pubkey_to_privkey[state.validator_registry[index].pubkey]
        voluntary_exit = build_voluntary_exit(
            state,
            current_epoch,
            index,
            privkey,
        )

        pre_state, post_state = run_voluntary_exit_processing(post_state, voluntary_exit)

    # exit an additional validator
    validator_index = get_active_validator_indices(state, current_epoch)[-1]
    privkey = pubkey_to_privkey[state.validator_registry[validator_index].pubkey]
    voluntary_exit = build_voluntary_exit(
        state,
        current_epoch,
        validator_index,
        privkey,
    )

    pre_state, post_state = run_voluntary_exit_processing(post_state, voluntary_exit)

    assert (
        post_state.validator_registry[validator_index].exit_epoch ==
        post_state.validator_registry[initial_indices[0]].exit_epoch + 1
    )

    return pre_state, voluntary_exit, post_state


def test_validator_not_active(state):
    current_epoch = get_current_epoch(state)
    validator_index = get_active_validator_indices(state, current_epoch)[0]
    privkey = pubkey_to_privkey[state.validator_registry[validator_index].pubkey]

    state.validator_registry[validator_index].activation_epoch = spec.FAR_FUTURE_EPOCH

    #
    # build and test voluntary exit
    #
    voluntary_exit = build_voluntary_exit(
        state,
        current_epoch,
        validator_index,
        privkey,
    )

    pre_state, post_state = run_voluntary_exit_processing(state, voluntary_exit, False)
    return pre_state, voluntary_exit, post_state


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

    pre_state, post_state = run_voluntary_exit_processing(state, voluntary_exit, False)
    return pre_state, voluntary_exit, post_state


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

    pre_state, post_state = run_voluntary_exit_processing(state, voluntary_exit, False)
    return pre_state, voluntary_exit, post_state
