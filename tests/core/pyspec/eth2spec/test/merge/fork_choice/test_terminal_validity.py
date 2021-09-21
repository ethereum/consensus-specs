from eth2spec.utils.ssz.ssz_typing import uint256
from eth2spec.test.helpers.block import (
    prepare_empty_pow_block
)
from eth2spec.test.context import spec_state_test, with_merge_and_later


class BlockNotFoundException(Exception):
    pass


# Copy of conditional merge part of `on_block(store: Store, signed_block: SignedBeaconBlock)` handler
def process_merge_execution_payload(spec, execution_payload):
    pow_block = spec.get_pow_block(execution_payload.parent_hash)
    pow_parent = spec.get_pow_block(pow_block.parent_hash)
    assert spec.is_valid_terminal_pow_block(pow_block, pow_parent)


def run_process_merge_execution_payload(spec, block, parent_block, payload,
                                        valid=True, block_lookup_success=True):
    """
    Run ``process_merge_execution_payload``, yielding:
      - current block ('block')
      - parent block ('parent_block')
      - execution payload ('payload')
    If ``valid == False``, run expecting ``AssertionError``
    If ``block_lookup_success == False``, run expecting ``BlockNotFoundException``
    """

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
        process_merge_execution_payload(spec, payload)
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
def test_valid_terminal_pow_block_success_valid(spec, state):
    parent_block = prepare_empty_pow_block(spec)
    parent_block.total_difficulty = spec.config.TERMINAL_TOTAL_DIFFICULTY - uint256(1)
    block = prepare_empty_pow_block(spec)
    block.parent_hash = parent_block.block_hash
    block.total_difficulty = spec.config.TERMINAL_TOTAL_DIFFICULTY

    assert spec.is_valid_terminal_pow_block(block, parent_block)


@with_merge_and_later
@spec_state_test
def test_valid_terminal_pow_block_fail_before_terminal(spec, state):
    parent_block = prepare_empty_pow_block(spec)
    parent_block.total_difficulty = spec.config.TERMINAL_TOTAL_DIFFICULTY - uint256(2)
    block = prepare_empty_pow_block(spec)
    block.parent_hash = parent_block.block_hash
    block.total_difficulty = spec.config.TERMINAL_TOTAL_DIFFICULTY - uint256(1)

    assert not spec.is_valid_terminal_pow_block(block, parent_block)


@with_merge_and_later
@spec_state_test
def test_valid_terminal_pow_block_fail_just_after_terminal(spec, state):
    parent_block = prepare_empty_pow_block(spec)
    parent_block.total_difficulty = spec.config.TERMINAL_TOTAL_DIFFICULTY
    block = prepare_empty_pow_block(spec)
    block.parent_hash = parent_block.block_hash
    block.total_difficulty = spec.config.TERMINAL_TOTAL_DIFFICULTY + uint256(1)

    assert not spec.is_valid_terminal_pow_block(block, parent_block)


@with_merge_and_later
@spec_state_test
def test_process_merge_execution_payload_success(spec, state):
    parent_block = prepare_empty_pow_block(spec)
    parent_block.block_hash = spec.Hash32(spec.hash(b'01'))
    parent_block.total_difficulty = spec.config.TERMINAL_TOTAL_DIFFICULTY - uint256(1)
    block = prepare_empty_pow_block(spec)
    block.parent_hash = parent_block.block_hash
    block.total_difficulty = spec.config.TERMINAL_TOTAL_DIFFICULTY
    payload = spec.ExecutionPayload()
    payload.parent_hash = block.block_hash
    yield from run_process_merge_execution_payload(spec, block, parent_block, payload)


@with_merge_and_later
@spec_state_test
def test_process_merge_execution_payload_fail_block_lookup(spec, state):
    parent_block = prepare_empty_pow_block(spec)
    parent_block.block_hash = spec.Hash32(spec.hash(b'01'))
    parent_block.total_difficulty = spec.config.TERMINAL_TOTAL_DIFFICULTY - uint256(1)
    block = prepare_empty_pow_block(spec)
    block.parent_hash = parent_block.block_hash
    block.total_difficulty = spec.config.TERMINAL_TOTAL_DIFFICULTY
    payload = spec.ExecutionPayload()
    payload.parent_hash = spec.Hash32(spec.hash(b'02'))
    yield from run_process_merge_execution_payload(spec, block, parent_block, payload,
                                                   block_lookup_success=False)


@with_merge_and_later
@spec_state_test
def test_process_merge_execution_payload_fail_parent_block_lookup(spec, state):
    parent_block = prepare_empty_pow_block(spec)
    parent_block.block_hash = spec.Hash32(spec.hash(b'01'))
    parent_block.total_difficulty = spec.config.TERMINAL_TOTAL_DIFFICULTY - uint256(1)
    block = prepare_empty_pow_block(spec)
    block.parent_hash = spec.Hash32(spec.hash(b'00'))
    block.total_difficulty = spec.config.TERMINAL_TOTAL_DIFFICULTY
    payload = spec.ExecutionPayload()
    payload.parent_hash = block.block_hash
    yield from run_process_merge_execution_payload(spec, block, parent_block, payload,
                                                   block_lookup_success=False)


@with_merge_and_later
@spec_state_test
def test_process_merge_execution_payload_fail_after_terminal(spec, state):
    parent_block = prepare_empty_pow_block(spec)
    parent_block.block_hash = spec.Hash32(spec.hash(b'01'))
    parent_block.total_difficulty = spec.config.TERMINAL_TOTAL_DIFFICULTY
    block = prepare_empty_pow_block(spec)
    block.parent_hash = parent_block.block_hash
    block.total_difficulty = spec.config.TERMINAL_TOTAL_DIFFICULTY + 1
    payload = spec.ExecutionPayload()
    payload.parent_hash = block.block_hash
    yield from run_process_merge_execution_payload(spec, block, parent_block, payload, valid=False)
