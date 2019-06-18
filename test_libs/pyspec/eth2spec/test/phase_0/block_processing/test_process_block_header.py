from copy import deepcopy

from eth2spec.test.context import spec_state_test, expect_assertion_error, always_bls, with_all_phases
from eth2spec.test.helpers.block import (
    build_empty_block_for_next_slot,
    sign_block
)
from eth2spec.test.helpers.state import next_slot


def prepare_state_for_header_processing(spec, state):
    spec.process_slots(state, state.slot + 1)


def run_block_header_processing(spec, state, block, valid=True):
    """
    Run ``process_block_header``, yielding:
      - pre-state ('pre')
      - block ('block')
      - post-state ('post').
    If ``valid == False``, run expecting ``AssertionError``
    """
    prepare_state_for_header_processing(spec, state)

    yield 'pre', state
    yield 'block', block

    if not valid:
        expect_assertion_error(lambda: spec.process_block_header(state, block))
        yield 'post', None
        return

    spec.process_block_header(state, block)
    yield 'post', state


@with_all_phases
@spec_state_test
def test_success_block_header(spec, state):
    block = build_empty_block_for_next_slot(spec, state, signed=True)
    yield from run_block_header_processing(spec, state, block)


@with_all_phases
@always_bls
@spec_state_test
def test_invalid_sig_block_header(spec, state):
    block = build_empty_block_for_next_slot(spec, state)
    yield from run_block_header_processing(spec, state, block, valid=False)


@with_all_phases
@spec_state_test
def test_invalid_slot_block_header(spec, state):
    block = build_empty_block_for_next_slot(spec, state)
    block.slot = state.slot + 2  # invalid slot
    sign_block(spec, state, block)

    yield from run_block_header_processing(spec, state, block, valid=False)


@with_all_phases
@spec_state_test
def test_invalid_parent_root(spec, state):
    block = build_empty_block_for_next_slot(spec, state)
    block.parent_root = b'\12' * 32  # invalid prev root
    sign_block(spec, state, block)

    yield from run_block_header_processing(spec, state, block, valid=False)


@with_all_phases
@spec_state_test
def test_proposer_slashed(spec, state):
    # use stub state to get proposer index of next slot
    stub_state = deepcopy(state)
    next_slot(spec, stub_state)
    proposer_index = spec.get_beacon_proposer_index(stub_state)

    # set proposer to slashed
    state.validators[proposer_index].slashed = True

    block = build_empty_block_for_next_slot(spec, state, signed=True)

    yield from run_block_header_processing(spec, state, block, valid=False)
