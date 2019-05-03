from copy import deepcopy
import pytest


from eth2spec.phase0.spec import (
    get_beacon_proposer_index,
    cache_state,
    advance_slot,
    process_block_header,
)
from tests.helpers import (
    build_empty_block_for_next_slot,
    next_slot,
)

# mark entire file as 'header'
pytestmark = pytest.mark.header


def prepare_state_for_header_processing(state):
    cache_state(state)
    advance_slot(state)


def run_block_header_processing(state, block, valid=True):
    """
    Run ``process_block_header`` returning the pre and post state.
    If ``valid == False``, run expecting ``AssertionError``
    """
    prepare_state_for_header_processing(state)
    post_state = deepcopy(state)

    if not valid:
        with pytest.raises(AssertionError):
            process_block_header(post_state, block)
        return state, None

    process_block_header(post_state, block)
    return state, post_state


def test_success(state):
    block = build_empty_block_for_next_slot(state)
    pre_state, post_state = run_block_header_processing(state, block)
    return state, block, post_state


def test_invalid_slot(state):
    block = build_empty_block_for_next_slot(state)
    block.slot = state.slot + 2  # invalid slot

    pre_state, post_state = run_block_header_processing(state, block, valid=False)
    return pre_state, block, None


def test_invalid_previous_block_root(state):
    block = build_empty_block_for_next_slot(state)
    block.previous_block_root = b'\12' * 32  # invalid prev root

    pre_state, post_state = run_block_header_processing(state, block, valid=False)
    return pre_state, block, None


def test_proposer_slashed(state):
    # use stub state to get proposer index of next slot
    stub_state = deepcopy(state)
    next_slot(stub_state)
    proposer_index = get_beacon_proposer_index(stub_state)

    # set proposer to slashed
    state.validator_registry[proposer_index].slashed = True

    block = build_empty_block_for_next_slot(state)

    pre_state, post_state = run_block_header_processing(state, block, valid=False)
    return pre_state, block, None
