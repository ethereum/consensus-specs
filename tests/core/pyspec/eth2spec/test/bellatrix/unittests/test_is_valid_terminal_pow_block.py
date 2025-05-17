from eth2spec.test.context import (
    spec_state_test,
    with_bellatrix_and_later,
)
from eth2spec.test.helpers.pow_block import (
    prepare_random_pow_block,
)
from eth2spec.utils.ssz.ssz_typing import uint256


@with_bellatrix_and_later
@spec_state_test
def test_is_valid_terminal_pow_block_success_valid(spec, state):
    parent_block = prepare_random_pow_block(spec)
    parent_block.total_difficulty = spec.config.TERMINAL_TOTAL_DIFFICULTY - uint256(1)
    block = prepare_random_pow_block(spec)
    block.parent_hash = parent_block.block_hash
    block.total_difficulty = spec.config.TERMINAL_TOTAL_DIFFICULTY

    assert spec.is_valid_terminal_pow_block(block, parent_block)


@with_bellatrix_and_later
@spec_state_test
def test_is_valid_terminal_pow_block_fail_before_terminal(spec, state):
    parent_block = prepare_random_pow_block(spec)
    parent_block.total_difficulty = spec.config.TERMINAL_TOTAL_DIFFICULTY - uint256(2)
    block = prepare_random_pow_block(spec)
    block.parent_hash = parent_block.block_hash
    block.total_difficulty = spec.config.TERMINAL_TOTAL_DIFFICULTY - uint256(1)

    assert not spec.is_valid_terminal_pow_block(block, parent_block)


@with_bellatrix_and_later
@spec_state_test
def test_is_valid_terminal_pow_block_fail_just_after_terminal(spec, state):
    parent_block = prepare_random_pow_block(spec)
    parent_block.total_difficulty = spec.config.TERMINAL_TOTAL_DIFFICULTY
    block = prepare_random_pow_block(spec)
    block.parent_hash = parent_block.block_hash
    block.total_difficulty = spec.config.TERMINAL_TOTAL_DIFFICULTY + uint256(1)

    assert not spec.is_valid_terminal_pow_block(block, parent_block)
