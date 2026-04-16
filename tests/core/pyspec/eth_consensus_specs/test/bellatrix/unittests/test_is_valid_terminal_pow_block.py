from random import Random

from eth_consensus_specs.test.context import (
    spec_state_test,
    with_bellatrix_and_later,
)
from eth_consensus_specs.test.helpers.pow_block import (
    prepare_random_pow_block,
)
from eth_consensus_specs.utils.ssz.ssz_typing import uint256


@with_bellatrix_and_later
@spec_state_test
def test_is_valid_terminal_pow_block_success_valid(spec, state):
    parent_block = prepare_random_pow_block(spec, rng=Random(1234))
    parent_block.total_difficulty = spec.config.TERMINAL_TOTAL_DIFFICULTY - uint256(1)
    block = prepare_random_pow_block(spec, rng=Random(2345))
    block.parent_hash = parent_block.block_hash
    block.total_difficulty = spec.config.TERMINAL_TOTAL_DIFFICULTY

    assert spec.is_valid_terminal_pow_block(block, parent_block)


@with_bellatrix_and_later
@spec_state_test
def test_is_valid_terminal_pow_block_fail_before_terminal(spec, state):
    parent_block = prepare_random_pow_block(spec, rng=Random(1234))
    parent_block.total_difficulty = spec.config.TERMINAL_TOTAL_DIFFICULTY - uint256(2)
    block = prepare_random_pow_block(spec, rng=Random(2345))
    block.parent_hash = parent_block.block_hash
    block.total_difficulty = spec.config.TERMINAL_TOTAL_DIFFICULTY - uint256(1)

    assert not spec.is_valid_terminal_pow_block(block, parent_block)


@with_bellatrix_and_later
@spec_state_test
def test_is_valid_terminal_pow_block_fail_just_after_terminal(spec, state):
    parent_block = prepare_random_pow_block(spec, rng=Random(1234))
    parent_block.total_difficulty = spec.config.TERMINAL_TOTAL_DIFFICULTY
    block = prepare_random_pow_block(spec, rng=Random(2345))
    block.parent_hash = parent_block.block_hash
    block.total_difficulty = spec.config.TERMINAL_TOTAL_DIFFICULTY + uint256(1)

    assert not spec.is_valid_terminal_pow_block(block, parent_block)
