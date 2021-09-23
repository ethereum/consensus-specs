from eth2spec.utils.ssz.ssz_typing import uint256
from eth2spec.test.context import spec_state_test, with_phases, MERGE
from eth2spec.test.helpers.block import (
    build_empty_block_for_next_slot
)
from eth2spec.test.helpers.fork_choice import (
    get_genesis_forkchoice_store_and_block,
    on_tick_and_append_step,
    tick_and_add_block,
)
from eth2spec.test.helpers.state import (
    state_transition_and_sign_block,
)
from eth2spec.test.helpers.block import (
    prepare_empty_pow_block
)


def with_pow_block_patch(spec, blocks, func):
    def get_pow_block(hash: spec.Bytes32) -> spec.PowBlock:
        for block in blocks:
            if block.block_hash == hash:
                return block
        raise Exception("Block not found")
    get_pow_block_backup = spec.get_pow_block
    spec.get_pow_block = get_pow_block

    class AtomicBoolean():
        value = False
    is_called = AtomicBoolean()

    def wrap(flag: AtomicBoolean):
        func()
        flag.value = True

    try:
        wrap(is_called)
    finally:
        spec.get_pow_block = get_pow_block_backup
    assert is_called.value


@with_phases([MERGE])
@spec_state_test
def test_all_valid(spec, state):
    test_steps = []
    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield 'anchor_state', state
    yield 'anchor_block', anchor_block
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    assert store.time == current_time

    parent_block = prepare_empty_pow_block(spec)
    parent_block.total_difficulty = spec.config.TERMINAL_TOTAL_DIFFICULTY - uint256(1)
    block = prepare_empty_pow_block(spec)
    block.parent_hash = parent_block.block_hash
    block.total_difficulty = spec.config.TERMINAL_TOTAL_DIFFICULTY
    pow_blocks = [block, parent_block]
    yield 'pow_blocks', pow_blocks

    def run_func():
        block = build_empty_block_for_next_slot(spec, state)
        signed_block = state_transition_and_sign_block(spec, state, block)
        yield from tick_and_add_block(spec, store, signed_block, test_steps)
        # valid
        assert spec.get_head(store) == signed_block.message.hash_tree_root()

    with_pow_block_patch(spec, pow_blocks, run_func)
    yield 'steps', test_steps


@with_phases([MERGE])
@spec_state_test
def test_block_lookup_failed(spec, state):
    test_steps = []
    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield 'anchor_state', state
    yield 'anchor_block', anchor_block
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    assert store.time == current_time


    parent_block = prepare_empty_pow_block(spec)
    parent_block.total_difficulty = spec.config.TERMINAL_TOTAL_DIFFICULTY - uint256(1)
    pow_blocks = [parent_block]
    yield 'pow_blocks', pow_blocks

    def run_func():
        block = build_empty_block_for_next_slot(spec, state)
        signed_block = state_transition_and_sign_block(spec, state, block)
        yield from tick_and_add_block(spec, store, signed_block, test_steps)
        # invalid
        assert spec.get_head(store) == anchor_block.state_root

    with_pow_block_patch(spec, pow_blocks, run_func)
    yield 'steps', test_steps


@with_phases([MERGE])
@spec_state_test
def test_too_early_for_merge(spec, state):
    test_steps = []
    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield 'anchor_state', state
    yield 'anchor_block', anchor_block
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    assert store.time == current_time

    parent_block = prepare_empty_pow_block(spec)
    parent_block.total_difficulty = spec.config.TERMINAL_TOTAL_DIFFICULTY - uint256(2)
    block = prepare_empty_pow_block(spec)
    block.parent_hash = parent_block.block_hash
    block.total_difficulty = spec.config.TERMINAL_TOTAL_DIFFICULTY - uint256(1)
    pow_blocks = [block, parent_block]
    yield 'pow_blocks', pow_blocks

    def run_func():
        block = build_empty_block_for_next_slot(spec, state)
        signed_block = state_transition_and_sign_block(spec, state, block)
        yield from tick_and_add_block(spec, store, signed_block, test_steps)
        # invalid
        assert spec.get_head(store) == anchor_block.state_root

    with_pow_block_patch(spec, pow_blocks, run_func)
    yield 'steps', test_steps


@with_phases([MERGE])
@spec_state_test
def test_too_late_for_merge(spec, state):
    test_steps = []
    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield 'anchor_state', state
    yield 'anchor_block', anchor_block
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    assert store.time == current_time

    parent_block = prepare_empty_pow_block(spec)
    parent_block.total_difficulty = spec.config.TERMINAL_TOTAL_DIFFICULTY
    block = prepare_empty_pow_block(spec)
    block.parent_hash = parent_block.block_hash
    block.total_difficulty = spec.config.TERMINAL_TOTAL_DIFFICULTY + uint256(1)
    pow_blocks = [block, parent_block]
    yield 'pow_blocks', pow_blocks

    def run_func():
        block = build_empty_block_for_next_slot(spec, state)
        signed_block = state_transition_and_sign_block(spec, state, block)
        yield from tick_and_add_block(spec, store, signed_block, test_steps)
        # invalid
        assert spec.get_head(store) == anchor_block.state_root

    with_pow_block_patch(spec, pow_blocks, run_func)
    yield 'steps', test_steps
