from copy import deepcopy

from eth2spec.phase0.spec import (
    get_beacon_proposer_index,
    cache_state,
    advance_slot,
    process_block_header,
)
from eth2spec.test.context import spec_state_test, expect_assertion_error
from eth2spec.test.helpers import (
    build_empty_block_for_next_slot,
    next_slot,
    make_block_signature
)


def prepare_state_for_header_processing(state):
    cache_state(state)
    advance_slot(state)


def run_block_header_processing(state, block, valid=True):
    """
    Run ``process_block_header``, yielding:
      - pre-state ('pre')
      - block ('block')
      - post-state ('post').
    If ``valid == False``, run expecting ``AssertionError``
    """
    prepare_state_for_header_processing(state)

    yield 'pre', state
    yield 'block', block

    if not valid:
        expect_assertion_error(lambda: process_block_header(state, block))
        yield 'post', None
        return

    process_block_header(state, block)
    yield 'post', state


@spec_state_test
def test_success(state):
    block = build_empty_block_for_next_slot(state, signed=True)
    yield from run_block_header_processing(state, block)


@spec_state_test
def test_invalid_slot(state):
    block = build_empty_block_for_next_slot(state)
    block.slot = state.slot + 2  # invalid slot

    yield from run_block_header_processing(state, block, valid=False)


@spec_state_test
def test_invalid_previous_block_root(state):
    block = build_empty_block_for_next_slot(state)
    block.previous_block_root = b'\12' * 32  # invalid prev root
    make_block_signature(state, block)

    yield from run_block_header_processing(state, block, valid=False)


@spec_state_test
def test_proposer_slashed(state):
    # use stub state to get proposer index of next slot
    stub_state = deepcopy(state)
    next_slot(stub_state)
    proposer_index = get_beacon_proposer_index(stub_state)

    # set proposer to slashed
    state.validator_registry[proposer_index].slashed = True

    block = build_empty_block_for_next_slot(state, signed=True)

    yield from run_block_header_processing(state, block, valid=False)
