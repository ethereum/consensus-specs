from copy import deepcopy
import pytest

import build.phase0.spec as spec
from build.phase0.spec import (
    get_balance,
    get_current_epoch,
    process_randao_reveal_slashing,
    RANDAO_SLASHING_EPOCHS,
    CUSTODY_PERIOD_TO_RANDAO_PADDING
)
from tests.phase0.helpers import (
    get_valid_randao_reveal_slashing,
)

# mark entire file as 'randao_reveal_slashings'
pytestmark = pytest.mark.randao_reveal_slashings


def run_randao_reveal_slashing_processing(state, randao_reveal_slashing, valid=True):
    """
    Run ``process_randao_reveal_slashing`` returning the pre and post state.
    If ``valid == False``, run expecting ``AssertionError``
    """
    post_state = deepcopy(state)

    if not valid:
        with pytest.raises(AssertionError):
            process_randao_reveal_slashing(post_state, randao_reveal_slashing)
        return state, None

    process_randao_reveal_slashing(post_state, randao_reveal_slashing)

    slashed_validator = post_state.validator_registry[randao_reveal_slashing.revealer_index]
    assert not slashed_validator.initiated_exit
    if randao_reveal_slashing.epoch >= get_current_epoch(state) + CUSTODY_PERIOD_TO_RANDAO_PADDING:
        assert slashed_validator.slashed
        assert slashed_validator.exit_epoch < spec.FAR_FUTURE_EPOCH
        assert slashed_validator.withdrawable_epoch < spec.FAR_FUTURE_EPOCH
    # lost whistleblower reward
    assert (
        get_balance(post_state, randao_reveal_slashing.revealer_index) <
        get_balance(state, randao_reveal_slashing.revealer_index)
    )

    return state, post_state


def test_success(state):
    randao_reveal_slashing = get_valid_randao_reveal_slashing(state)

    pre_state, post_state = run_randao_reveal_slashing_processing(state, randao_reveal_slashing)

    return pre_state, randao_reveal_slashing, post_state


def test_reveal_from_current_epoch(state):
    randao_reveal_slashing = get_valid_randao_reveal_slashing(state, get_current_epoch(state))

    pre_state, post_state = run_randao_reveal_slashing_processing(state, randao_reveal_slashing, False)

    return pre_state, randao_reveal_slashing, post_state


def test_reveal_from_past_epoch(state):
    randao_reveal_slashing = get_valid_randao_reveal_slashing(state, get_current_epoch(state) - 1)

    pre_state, post_state = run_randao_reveal_slashing_processing(state, randao_reveal_slashing, False)

    return pre_state, randao_reveal_slashing, post_state

def test_reveal_with_custody_padding(state):
    randao_reveal_slashing = get_valid_randao_reveal_slashing(state, get_current_epoch(state) + CUSTODY_PERIOD_TO_RANDAO_PADDING)
    pre_state, post_state = run_randao_reveal_slashing_processing(state, randao_reveal_slashing, True)

    return pre_state, randao_reveal_slashing, post_state

def test_reveal_with_custody_padding_minus_one(state):
    randao_reveal_slashing = get_valid_randao_reveal_slashing(state, get_current_epoch(state) + CUSTODY_PERIOD_TO_RANDAO_PADDING - 1)
    pre_state, post_state = run_randao_reveal_slashing_processing(state, randao_reveal_slashing, True)

    return pre_state, randao_reveal_slashing, post_state

def test_double_reveal(state):
    
    randao_reveal_slashing1 = get_valid_randao_reveal_slashing(state, get_current_epoch(state) + RANDAO_SLASHING_EPOCHS + 1)
    pre_state, intermediate_state = run_randao_reveal_slashing_processing(state, randao_reveal_slashing1)
    
    randao_reveal_slashing2 = get_valid_randao_reveal_slashing(intermediate_state, get_current_epoch(pre_state) + RANDAO_SLASHING_EPOCHS + 1)
    intermediate_state_, post_state = run_randao_reveal_slashing_processing(intermediate_state, randao_reveal_slashing2, False)


    return pre_state, [randao_reveal_slashing1, randao_reveal_slashing2], post_state

def test_revealer_is_slashed(state):
    randao_reveal_slashing = get_valid_randao_reveal_slashing(state, get_current_epoch(state))
    state.validator_registry[randao_reveal_slashing.revealer_index].slashed = True

    pre_state, post_state = run_randao_reveal_slashing_processing(state, randao_reveal_slashing, False)

    return pre_state, randao_reveal_slashing, post_state
