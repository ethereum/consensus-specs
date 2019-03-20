from copy import deepcopy
import pytest


from build.phase0.spec import (
    cache_state,
    advance_slot,
    process_block_header,
)
from tests.phase0.helpers import (
    build_empty_block_for_next_slot,
)

# mark entire file as 'header'
pytestmark = pytest.mark.header


def test_sucess(state):
    pre_state = deepcopy(state)
    block = build_empty_block_for_next_slot(pre_state)

    #
    # setup pre_state to be ready for block transition
    #
    cache_state(pre_state)
    advance_slot(pre_state)

    post_state = deepcopy(pre_state)

    #
    # test block header
    #
    process_block_header(post_state, block)

    return state, [block], post_state


def test_invalid_slot(state):
    pre_state = deepcopy(state)

    # mess up previous block root
    block = build_empty_block_for_next_slot(pre_state)
    block.previous_block_root = b'\12'*32

    #
    # setup pre_state advancing two slots to induce error
    #
    cache_state(pre_state)
    advance_slot(pre_state)
    advance_slot(pre_state)

    post_state = deepcopy(pre_state)

    #
    # test block header
    #
    with pytest.raises(AssertionError):
        process_block_header(post_state, block)

    return state, [block], None


def test_invalid_previous_block_root(state):
    pre_state = deepcopy(state)

    # mess up previous block root
    block = build_empty_block_for_next_slot(pre_state)
    block.previous_block_root = b'\12'*32

    #
    # setup pre_state to be ready for block transition
    #
    cache_state(pre_state)
    advance_slot(pre_state)

    post_state = deepcopy(pre_state)

    #
    # test block header
    #
    with pytest.raises(AssertionError):
        process_block_header(post_state, block)

    return state, [block], None
