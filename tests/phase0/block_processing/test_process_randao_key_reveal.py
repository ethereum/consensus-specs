from copy import deepcopy
import pytest

import build.phase0.spec as spec
from build.phase0.spec import (
    get_balance,
    get_current_epoch,
    process_randao_key_reveal,
    RANDAO_PENALTY_EPOCHS,
    CUSTODY_PERIOD_TO_RANDAO_PADDING
)
from tests.phase0.helpers import (
    get_valid_randao_key_reveal,
)

# mark entire file as 'randao_key_reveals'
pytestmark = pytest.mark.randao_key_reveals


def run_randao_key_reveal_processing(state, randao_key_reveal, valid=True):
    """
    Run ``process_randao_key_reveal`` returning the pre and post state.
    If ``valid == False``, run expecting ``AssertionError``
    """
    post_state = deepcopy(state)

    if not valid:
        with pytest.raises(AssertionError):
            process_randao_key_reveal(post_state, randao_key_reveal)
        return state, None

    process_randao_key_reveal(post_state, randao_key_reveal)

    slashed_validator = post_state.validator_registry[randao_key_reveal.revealer_index]

    if randao_key_reveal.epoch >= get_current_epoch(state) + CUSTODY_PERIOD_TO_RANDAO_PADDING:
        assert slashed_validator.slashed
        assert slashed_validator.exit_epoch < spec.FAR_FUTURE_EPOCH
        assert slashed_validator.withdrawable_epoch < spec.FAR_FUTURE_EPOCH
    # lost whistleblower reward
    # FIXME: Currently broken because get_base_reward in genesis epoch is 0
    #assert (
    #    get_balance(post_state, randao_key_reveal.revealer_index) <
    #    get_balance(state, randao_key_reveal.revealer_index)
    #)

    return state, post_state


def test_success(state):
    randao_key_reveal = get_valid_randao_key_reveal(state)

    pre_state, post_state = run_randao_key_reveal_processing(state, randao_key_reveal)

    return pre_state, randao_key_reveal, post_state


def test_reveal_from_current_epoch(state):
    randao_key_reveal = get_valid_randao_key_reveal(state, get_current_epoch(state))

    pre_state, post_state = run_randao_key_reveal_processing(state, randao_key_reveal, False)

    return pre_state, randao_key_reveal, post_state


def test_reveal_from_past_epoch(state):
    randao_key_reveal = get_valid_randao_key_reveal(state, get_current_epoch(state) - 1)

    pre_state, post_state = run_randao_key_reveal_processing(state, randao_key_reveal, False)

    return pre_state, randao_key_reveal, post_state

def test_reveal_with_custody_padding(state):
    randao_key_reveal = get_valid_randao_key_reveal(state, get_current_epoch(state) + CUSTODY_PERIOD_TO_RANDAO_PADDING)
    pre_state, post_state = run_randao_key_reveal_processing(state, randao_key_reveal, True)

    return pre_state, randao_key_reveal, post_state

def test_reveal_with_custody_padding_minus_one(state):
    randao_key_reveal = get_valid_randao_key_reveal(state, get_current_epoch(state) + CUSTODY_PERIOD_TO_RANDAO_PADDING - 1)
    pre_state, post_state = run_randao_key_reveal_processing(state, randao_key_reveal, True)

    return pre_state, randao_key_reveal, post_state

def test_double_reveal(state):
    
    randao_key_reveal1 = get_valid_randao_key_reveal(state, get_current_epoch(state) + RANDAO_PENALTY_EPOCHS + 1)
    pre_state, intermediate_state = run_randao_key_reveal_processing(state, randao_key_reveal1)
    
    randao_key_reveal2 = get_valid_randao_key_reveal(intermediate_state, get_current_epoch(pre_state) + RANDAO_PENALTY_EPOCHS + 1)
    intermediate_state_, post_state = run_randao_key_reveal_processing(intermediate_state, randao_key_reveal2, False)

    return pre_state, [randao_key_reveal1, randao_key_reveal2], post_state

def test_revealer_is_slashed(state):
    randao_key_reveal = get_valid_randao_key_reveal(state, get_current_epoch(state))
    state.validator_registry[randao_key_reveal.revealer_index].slashed = True

    pre_state, post_state = run_randao_key_reveal_processing(state, randao_key_reveal, False)

    return pre_state, randao_key_reveal, post_state
