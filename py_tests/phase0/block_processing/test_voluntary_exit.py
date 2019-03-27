from copy import deepcopy
import pytest

import eth2.phase0.spec as spec

from eth2.phase0.spec import (
    get_active_validator_indices,
    get_current_epoch,
    process_voluntary_exit,
)
from ..helpers import (
    build_voluntary_exit,
    pubkey_to_privkey,
)


# mark entire file as 'voluntary_exits'
pytestmark = pytest.mark.voluntary_exits


def test_success(state):
    pre_state = deepcopy(state)
    #
    # setup pre_state
    #
    # move state forward PERSISTENT_COMMITTEE_PERIOD epochs to allow for exit
    pre_state.slot += spec.PERSISTENT_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    #
    # build voluntary exit
    #
    current_epoch = get_current_epoch(pre_state)
    validator_index = get_active_validator_indices(pre_state.validator_registry, current_epoch)[0]
    privkey = pubkey_to_privkey[pre_state.validator_registry[validator_index].pubkey]

    voluntary_exit = build_voluntary_exit(
        pre_state,
        current_epoch,
        validator_index,
        privkey,
    )

    post_state = deepcopy(pre_state)

    #
    # test valid exit
    #
    process_voluntary_exit(post_state, voluntary_exit)

    assert not pre_state.validator_registry[validator_index].initiated_exit
    assert post_state.validator_registry[validator_index].initiated_exit

    return pre_state, voluntary_exit, post_state


def test_validator_not_active(state):
    pre_state = deepcopy(state)
    current_epoch = get_current_epoch(pre_state)
    validator_index = get_active_validator_indices(pre_state.validator_registry, current_epoch)[0]
    privkey = pubkey_to_privkey[pre_state.validator_registry[validator_index].pubkey]

    #
    # setup pre_state
    #
    pre_state.validator_registry[validator_index].activation_epoch = spec.FAR_FUTURE_EPOCH

    #
    # build and test voluntary exit
    #
    voluntary_exit = build_voluntary_exit(
        pre_state,
        current_epoch,
        validator_index,
        privkey,
    )

    with pytest.raises(AssertionError):
        process_voluntary_exit(pre_state, voluntary_exit)

    return pre_state, voluntary_exit, None


def test_validator_already_exited(state):
    pre_state = deepcopy(state)
    #
    # setup pre_state
    #
    # move state forward PERSISTENT_COMMITTEE_PERIOD epochs to allow validator able to exit
    pre_state.slot += spec.PERSISTENT_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    current_epoch = get_current_epoch(pre_state)
    validator_index = get_active_validator_indices(pre_state.validator_registry, current_epoch)[0]
    privkey = pubkey_to_privkey[pre_state.validator_registry[validator_index].pubkey]

    # but validator already has exited
    pre_state.validator_registry[validator_index].exit_epoch = current_epoch + 2

    #
    # build voluntary exit
    #
    voluntary_exit = build_voluntary_exit(
        pre_state,
        current_epoch,
        validator_index,
        privkey,
    )

    with pytest.raises(AssertionError):
        process_voluntary_exit(pre_state, voluntary_exit)

    return pre_state, voluntary_exit, None


def test_validator_already_initiated_exit(state):
    pre_state = deepcopy(state)
    #
    # setup pre_state
    #
    # move state forward PERSISTENT_COMMITTEE_PERIOD epochs to allow validator able to exit
    pre_state.slot += spec.PERSISTENT_COMMITTEE_PERIOD * spec.SLOTS_PER_EPOCH

    current_epoch = get_current_epoch(pre_state)
    validator_index = get_active_validator_indices(pre_state.validator_registry, current_epoch)[0]
    privkey = pubkey_to_privkey[pre_state.validator_registry[validator_index].pubkey]

    # but validator already has initiated exit
    pre_state.validator_registry[validator_index].initiated_exit = True

    #
    # build voluntary exit
    #
    voluntary_exit = build_voluntary_exit(
        pre_state,
        current_epoch,
        validator_index,
        privkey,
    )

    with pytest.raises(AssertionError):
        process_voluntary_exit(pre_state, voluntary_exit)

    return pre_state, voluntary_exit, None


def test_validator_not_active_long_enough(state):
    pre_state = deepcopy(state)
    #
    # setup pre_state
    #
    current_epoch = get_current_epoch(pre_state)
    validator_index = get_active_validator_indices(pre_state.validator_registry, current_epoch)[0]
    privkey = pubkey_to_privkey[pre_state.validator_registry[validator_index].pubkey]

    # but validator already has initiated exit
    pre_state.validator_registry[validator_index].initiated_exit = True

    #
    # build voluntary exit
    #
    voluntary_exit = build_voluntary_exit(
        pre_state,
        current_epoch,
        validator_index,
        privkey,
    )

    assert (
        current_epoch - pre_state.validator_registry[validator_index].activation_epoch <
        spec.PERSISTENT_COMMITTEE_PERIOD
    )

    with pytest.raises(AssertionError):
        process_voluntary_exit(pre_state, voluntary_exit)

    return pre_state, voluntary_exit, None
