from eth2spec.test.helpers.pow_block import (
    prepare_random_pow_chain,
)
from eth2spec.test.context import (
    spec_state_test,
    with_merge_and_later,
)


# For test_get_pow_block_at_terminal_total_difficulty
IS_HEAD_BLOCK = 'is_head_block'
IS_HEAD_PARENT_BLOCK = 'is_head_parent_block'

# NOTE: The following parameter names are in the view of the head block (the second block)
# 'block_reached_ttd', 'block_parent_hash_is_empty', 'parent_reached_ttd', 'return_block'
expected_results = [
    (False, False, False, None),
    (False, False, True, IS_HEAD_PARENT_BLOCK),
    (False, True, False, None),
    (False, True, True, IS_HEAD_PARENT_BLOCK),
    (True, False, False, IS_HEAD_BLOCK),
    (True, False, True, IS_HEAD_PARENT_BLOCK),
    (True, True, False, IS_HEAD_BLOCK),
    (True, True, True, IS_HEAD_PARENT_BLOCK),
]
# NOTE: since the first block's `parent_hash` is set to `Hash32()` in test, if `parent_reached_ttd is True`,
# it would return the first block (IS_HEAD_PARENT_BLOCK).


@with_merge_and_later
@spec_state_test
def test_get_pow_block_at_terminal_total_difficulty(spec, state):
    for result in expected_results:
        (
            block_reached_ttd,
            block_parent_hash_is_empty,
            parent_reached_ttd,
            return_block
        ) = result
        pow_chain = prepare_random_pow_chain(spec, 2)
        pow_chain.head(-1).parent_hash = spec.Hash32()

        if block_reached_ttd:
            pow_chain.head().total_difficulty = spec.config.TERMINAL_TOTAL_DIFFICULTY
        else:
            pow_chain.head().total_difficulty = spec.config.TERMINAL_TOTAL_DIFFICULTY - 1

        if parent_reached_ttd:
            pow_chain.head(-1).total_difficulty = spec.config.TERMINAL_TOTAL_DIFFICULTY
        else:
            pow_chain.head(-1).total_difficulty = spec.config.TERMINAL_TOTAL_DIFFICULTY - 1

        if block_parent_hash_is_empty:
            pow_chain.head().parent_hash = spec.Hash32()

        pow_block = spec.get_pow_block_at_terminal_total_difficulty(pow_chain.to_dict())
        if return_block == IS_HEAD_BLOCK:
            assert pow_block == pow_chain.head()
        elif return_block == IS_HEAD_PARENT_BLOCK:
            assert pow_block == pow_chain.head(-1)
        elif return_block is None:
            assert pow_block is None
        else:
            raise Exception('Something is wrong')
