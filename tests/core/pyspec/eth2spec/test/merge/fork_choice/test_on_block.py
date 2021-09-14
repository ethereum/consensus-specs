from eth2spec.utils.ssz.ssz_typing import uint64, uint256
from eth2spec.test.helpers.block import (
    prepare_empty_pow_block
)
from eth2spec.test.context import spec_state_test, expect_assertion_error, with_merge_and_later


def create_transition_store(spec):
    anchor_block = prepare_empty_pow_block(spec)
    transition_store = spec.get_transition_store(anchor_block)
    return transition_store


class BlockNotFoundException(Exception):
    pass


def run_process_merge_execution_payload(spec, transition_store, block, parent_block, payload,
                                        valid=True, block_lookup_success=True):
    """
    Run ``process_merge_execution_payload``, yielding:
      - transition store ('transition_store')
      - current block ('block')
      - parent block ('parent_block')
      - execution payload ('payload')
    If ``valid == False``, run expecting ``AssertionError``
    If ``block_lookup_success == False``, run expecting ``BlockNotFoundException``
    """

    yield 'transition_store', transition_store
    yield 'block', block
    yield 'parent_block', parent_block
    yield 'payload', payload

    def get_pow_block(hash: spec.Bytes32) -> spec.PowBlock:
        if hash == block.block_hash:
            return block
        elif hash == parent_block.block_hash:
            return parent_block
        else:
            raise BlockNotFoundException()
    save_pow_block = spec.get_pow_block

    # Guido authorized everyone to do this
    spec.get_pow_block = get_pow_block
    exception_caught = False
    block_not_found_exception_caught = False
    try:
        spec.process_merge_execution_payload(transition_store, payload)
    except BlockNotFoundException:
        block_not_found_exception_caught = True
    except AssertionError:
        exception_caught = True
    except Exception as e:
        spec.get_pow_block = save_pow_block
        raise e
    spec.get_pow_block = save_pow_block

    if block_lookup_success:
        assert not block_not_found_exception_caught
    else:
        assert block_not_found_exception_caught
    if valid:
        assert not exception_caught
    else:
        assert exception_caught


@with_merge_and_later
@spec_state_test
def test_valid_terminal_pow_block_success_valid_fail_invalid(spec, state):
    transition_store = create_transition_store(spec)
    parent_block = prepare_empty_pow_block(spec)
    parent_block.total_difficulty = transition_store.terminal_total_difficulty - uint256(1)
    block = prepare_empty_pow_block(spec)
    block.parent_hash = parent_block.block_hash
    block.total_difficulty = transition_store.terminal_total_difficulty

    assert spec.is_valid_terminal_pow_block(transition_store, block, parent_block)

    block.is_valid = False
    assert not spec.is_valid_terminal_pow_block(transition_store, block, parent_block)


@with_merge_and_later
@spec_state_test
def test_valid_terminal_pow_block_fail_before_terminal(spec, state):
    transition_store = create_transition_store(spec)
    parent_block = prepare_empty_pow_block(spec)
    parent_block.total_difficulty = transition_store.terminal_total_difficulty - uint256(2)
    block = prepare_empty_pow_block(spec)
    block.parent_hash = parent_block.block_hash
    block.total_difficulty = transition_store.terminal_total_difficulty - uint256(1)

    assert not spec.is_valid_terminal_pow_block(transition_store, block, parent_block)


@with_merge_and_later
@spec_state_test
def test_valid_terminal_pow_block_fail_just_after_terminal(spec, state):
    transition_store = create_transition_store(spec)
    parent_block = prepare_empty_pow_block(spec)
    parent_block.total_difficulty = transition_store.terminal_total_difficulty
    block = prepare_empty_pow_block(spec)
    block.parent_hash = parent_block.block_hash
    block.total_difficulty = transition_store.terminal_total_difficulty + uint256(1)

    assert not spec.is_valid_terminal_pow_block(transition_store, block, parent_block)


@with_merge_and_later
@spec_state_test
def test_process_merge_execution_payload_success(spec, state):
    transition_store = create_transition_store(spec)
    parent_block = prepare_empty_pow_block(spec)
    parent_block.block_hash = spec.Hash32(spec.hash(b'01'))
    parent_block.total_difficulty = transition_store.terminal_total_difficulty - uint256(1)
    block = prepare_empty_pow_block(spec)
    block.parent_hash = parent_block.block_hash
    block.is_processed = True
    block.total_difficulty = transition_store.terminal_total_difficulty
    payload = spec.ExecutionPayload()
    payload.parent_hash = block.block_hash
    yield from run_process_merge_execution_payload(spec, transition_store, block, parent_block, payload)
    block.is_processed = False
    yield from run_process_merge_execution_payload(spec, transition_store, block, parent_block, payload, valid=False)


@with_merge_and_later
@spec_state_test
def test_process_merge_execution_payload_fail_block_lookup(spec, state):
    transition_store = create_transition_store(spec)
    parent_block = prepare_empty_pow_block(spec)
    parent_block.block_hash = spec.Hash32(spec.hash(b'01'))
    parent_block.total_difficulty = transition_store.terminal_total_difficulty - uint256(1)
    block = prepare_empty_pow_block(spec)
    block.parent_hash = parent_block.block_hash
    block.is_processed = True
    block.total_difficulty = transition_store.terminal_total_difficulty
    payload = spec.ExecutionPayload()
    payload.parent_hash = spec.Hash32(spec.hash(b'02'))
    yield from run_process_merge_execution_payload(spec, transition_store, block, parent_block, payload, block_lookup_success=False)


@with_merge_and_later
@spec_state_test
def test_process_merge_execution_payload_fail_parent_block_lookup(spec, state):
    transition_store = create_transition_store(spec)
    parent_block = prepare_empty_pow_block(spec)
    parent_block.block_hash = spec.Hash32(spec.hash(b'01'))
    parent_block.total_difficulty = transition_store.terminal_total_difficulty - uint256(1)
    block = prepare_empty_pow_block(spec)
    block.parent_hash = spec.Hash32(spec.hash(b'00'))
    block.is_processed = True
    block.total_difficulty = transition_store.terminal_total_difficulty
    payload = spec.ExecutionPayload()
    payload.parent_hash = block.block_hash
    yield from run_process_merge_execution_payload(spec, transition_store, block, parent_block, payload, block_lookup_success=False)


@with_merge_and_later
@spec_state_test
def test_process_merge_execution_payload_fail_after_terminal(spec, state):
    transition_store = create_transition_store(spec)
    parent_block = prepare_empty_pow_block(spec)
    parent_block.block_hash = spec.Hash32(spec.hash(b'01'))
    parent_block.total_difficulty = transition_store.terminal_total_difficulty
    block = prepare_empty_pow_block(spec)
    block.parent_hash = parent_block.block_hash
    block.is_processed = True
    block.total_difficulty = transition_store.terminal_total_difficulty + 1
    payload = spec.ExecutionPayload()
    payload.parent_hash = block.block_hash
    yield from run_process_merge_execution_payload(spec, transition_store, block, parent_block, payload, valid=False)