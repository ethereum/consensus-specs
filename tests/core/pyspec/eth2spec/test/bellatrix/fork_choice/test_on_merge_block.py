from random import Random

from eth2spec.test.context import BELLATRIX, spec_state_test, with_phases
from eth2spec.test.exceptions import BlockNotFoundException
from eth2spec.test.helpers.block import (
    build_empty_block_for_next_slot,
)
from eth2spec.test.helpers.execution_payload import (
    build_state_with_incomplete_transition,
    compute_el_block_hash,
)
from eth2spec.test.helpers.fork_choice import (
    add_pow_block,
    get_genesis_forkchoice_store_and_block,
    on_tick_and_append_step,
    tick_and_add_block,
)
from eth2spec.test.helpers.pow_block import (
    prepare_random_pow_block,
)
from eth2spec.test.helpers.state import (
    state_transition_and_sign_block,
)
from eth2spec.utils.ssz.ssz_typing import uint256


def with_pow_block_patch(spec, blocks, func):
    def get_pow_block(hash: spec.Bytes32) -> spec.PowBlock:
        for block in blocks:
            if block.block_hash == hash:
                return block
        raise BlockNotFoundException()

    get_pow_block_backup = spec.get_pow_block
    spec.get_pow_block = get_pow_block

    class AtomicBoolean:
        value = False

    is_called = AtomicBoolean()

    def wrap(flag: AtomicBoolean):
        yield from func()
        flag.value = True

    try:
        yield from wrap(is_called)
    finally:
        spec.get_pow_block = get_pow_block_backup
    assert is_called.value


@with_phases([BELLATRIX])
@spec_state_test
def test_all_valid(spec, state):
    test_steps = []
    # Initialization
    state = build_state_with_incomplete_transition(spec, state)
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    assert store.time == current_time

    pow_block_parent = prepare_random_pow_block(spec, rng=Random(1234))
    pow_block_parent.total_difficulty = spec.config.TERMINAL_TOTAL_DIFFICULTY - uint256(1)
    pow_block = prepare_random_pow_block(spec, rng=Random(2345))
    pow_block.parent_hash = pow_block_parent.block_hash
    pow_block.total_difficulty = spec.config.TERMINAL_TOTAL_DIFFICULTY
    pow_blocks = [pow_block, pow_block_parent]
    for pb in pow_blocks:
        yield from add_pow_block(spec, store, pb, test_steps)

    def run_func():
        block = build_empty_block_for_next_slot(spec, state)
        block.body.execution_payload.parent_hash = pow_block.block_hash
        block.body.execution_payload.block_hash = compute_el_block_hash(
            spec, block.body.execution_payload, state
        )
        signed_block = state_transition_and_sign_block(spec, state, block)
        yield from tick_and_add_block(spec, store, signed_block, test_steps, merge_block=True)
        # valid
        assert spec.get_head(store) == signed_block.message.hash_tree_root()

    yield from with_pow_block_patch(spec, pow_blocks, run_func)
    yield "steps", test_steps


@with_phases([BELLATRIX])
@spec_state_test
def test_block_lookup_failed(spec, state):
    test_steps = []
    # Initialization
    state = build_state_with_incomplete_transition(spec, state)
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    assert store.time == current_time

    pow_block = prepare_random_pow_block(spec, rng=Random(1234))
    pow_block.total_difficulty = spec.config.TERMINAL_TOTAL_DIFFICULTY - uint256(1)
    pow_blocks = [pow_block]
    for pb in pow_blocks:
        yield from add_pow_block(spec, store, pb, test_steps)

    def run_func():
        block = build_empty_block_for_next_slot(spec, state)
        block.body.execution_payload.parent_hash = pow_block.block_hash
        block.body.execution_payload.block_hash = compute_el_block_hash(
            spec, block.body.execution_payload, state
        )
        signed_block = state_transition_and_sign_block(spec, state, block)
        yield from tick_and_add_block(
            spec,
            store,
            signed_block,
            test_steps,
            valid=False,
            merge_block=True,
            block_not_found=True,
        )

    yield from with_pow_block_patch(spec, pow_blocks, run_func)
    yield "steps", test_steps


@with_phases([BELLATRIX])
@spec_state_test
def test_too_early_for_merge(spec, state):
    test_steps = []
    # Initialization
    state = build_state_with_incomplete_transition(spec, state)
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    assert store.time == current_time

    pow_block_parent = prepare_random_pow_block(spec, rng=Random(1234))
    pow_block_parent.total_difficulty = spec.config.TERMINAL_TOTAL_DIFFICULTY - uint256(2)
    pow_block = prepare_random_pow_block(spec, rng=Random(2345))
    pow_block.parent_hash = pow_block_parent.block_hash
    pow_block.total_difficulty = spec.config.TERMINAL_TOTAL_DIFFICULTY - uint256(1)
    pow_blocks = [pow_block, pow_block_parent]
    for pb in pow_blocks:
        yield from add_pow_block(spec, store, pb, test_steps)

    def run_func():
        block = build_empty_block_for_next_slot(spec, state)
        block.body.execution_payload.parent_hash = pow_block.block_hash
        block.body.execution_payload.block_hash = compute_el_block_hash(
            spec, block.body.execution_payload, state
        )
        signed_block = state_transition_and_sign_block(spec, state, block)
        yield from tick_and_add_block(
            spec, store, signed_block, test_steps, valid=False, merge_block=True
        )

    yield from with_pow_block_patch(spec, pow_blocks, run_func)
    yield "steps", test_steps


@with_phases([BELLATRIX])
@spec_state_test
def test_too_late_for_merge(spec, state):
    test_steps = []
    # Initialization
    state = build_state_with_incomplete_transition(spec, state)
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    assert store.time == current_time

    pow_block_parent = prepare_random_pow_block(spec, rng=Random(1234))
    pow_block_parent.total_difficulty = spec.config.TERMINAL_TOTAL_DIFFICULTY
    pow_block = prepare_random_pow_block(spec, rng=Random(2345))
    pow_block.parent_hash = pow_block_parent.block_hash
    pow_block.total_difficulty = spec.config.TERMINAL_TOTAL_DIFFICULTY + uint256(1)
    pow_blocks = [pow_block, pow_block_parent]
    for pb in pow_blocks:
        yield from add_pow_block(spec, store, pb, test_steps)

    def run_func():
        block = build_empty_block_for_next_slot(spec, state)
        block.body.execution_payload.parent_hash = pow_block.block_hash
        block.body.execution_payload.block_hash = compute_el_block_hash(
            spec, block.body.execution_payload, state
        )
        signed_block = state_transition_and_sign_block(spec, state, block)
        yield from tick_and_add_block(
            spec, store, signed_block, test_steps, valid=False, merge_block=True
        )

    yield from with_pow_block_patch(spec, pow_blocks, run_func)
    yield "steps", test_steps
