from eth2spec.utils.ssz.ssz_typing import uint256
from eth2spec.test.context import spec_state_test, with_phases, MERGE
from eth2spec.test.helpers.block import (
    build_empty_block_for_next_slot,
)
from eth2spec.test.helpers.engine_apis import (
    StatusCode,
    run_get_execution_payload_with_mock_engine_get_payload,
    with_pow_blocks_and_execute_payload,
)
from eth2spec.test.helpers.fork_choice import (
    add_pow_block,
    get_genesis_forkchoice_store_and_block,
    on_tick_and_append_step,
    prepare_random_hash_pow_block,
    tick_and_add_block,
)
from eth2spec.test.helpers.state import (
    state_transition_and_sign_block,
)
from eth2spec.test.helpers.execution_payload import (
    build_state_with_incomplete_transition,
)


@with_phases([MERGE])
@spec_state_test
def test_all_valid(spec, state):
    test_steps = []
    # Initialization
    state = build_state_with_incomplete_transition(spec, state)
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield 'anchor_state', state
    yield 'anchor_block', anchor_block
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    assert store.time == current_time

    # Block production
    # Required PoW blocks at the merge boundary
    pow_block_parent = prepare_random_hash_pow_block(spec)
    pow_block_parent.parent_hash = spec.Hash32()
    pow_block_parent.total_difficulty = spec.config.TERMINAL_TOTAL_DIFFICULTY - 1
    pow_block = prepare_random_hash_pow_block(spec)
    pow_block.parent_hash = pow_block_parent.block_hash
    pow_block.total_difficulty = spec.config.TERMINAL_TOTAL_DIFFICULTY
    pow_chain = [pow_block_parent, pow_block]
    for pb in pow_chain:
        yield from add_pow_block(pb)

    # Validator guide - get_execution_payload
    fee_recipient = spec.ExecutionAddress(b'\x12' * 20)
    payload_id = spec.PayloadId(1)
    block = build_empty_block_for_next_slot(spec, state)
    block.body.execution_payload = run_get_execution_payload_with_mock_engine_get_payload(
        spec,
        state,
        payload_id=payload_id,
        parent_hash=pow_block.block_hash,
        fee_recipient=fee_recipient,
        test_steps=test_steps,
    )
    signed_block = state_transition_and_sign_block(spec, state, block)

    # For on_block
    def run_tick_and_add_block():
        yield from tick_and_add_block(spec, store, signed_block, test_steps, merge_block=True)
        # valid
        assert spec.get_head(store) == signed_block.message.hash_tree_root()

    yield from with_pow_blocks_and_execute_payload(
        spec,
        pow_chain=pow_chain,
        status=StatusCode.VALID,
        func=run_tick_and_add_block,
        test_steps=test_steps,
    )

    yield 'steps', test_steps


@with_phases([MERGE])
@spec_state_test
def test_block_lookup_failed(spec, state):
    test_steps = []
    # Initialization
    state = build_state_with_incomplete_transition(spec, state)
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield 'anchor_state', state
    yield 'anchor_block', anchor_block
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    assert store.time == current_time

    pow_block = prepare_random_hash_pow_block(spec)
    pow_block.total_difficulty = spec.config.TERMINAL_TOTAL_DIFFICULTY - uint256(1)
    pow_chain = [pow_block]
    for pb in pow_chain:
        yield from add_pow_block(pb)

    # Validator guide - get_execution_payload
    fee_recipient = spec.ExecutionAddress(b'\x12' * 20)
    payload_id = spec.PayloadId(1)
    block = build_empty_block_for_next_slot(spec, state)
    block.body.execution_payload = run_get_execution_payload_with_mock_engine_get_payload(
        spec,
        state,
        payload_id=payload_id,
        parent_hash=pow_block.block_hash,
        fee_recipient=fee_recipient,
        test_steps=test_steps,
    )
    signed_block = state_transition_and_sign_block(spec, state, block)

    def run_tick_and_add_block():
        yield from tick_and_add_block(spec, store, signed_block, test_steps, valid=False, merge_block=True,
                                      block_not_found=True)

    yield from with_pow_blocks_and_execute_payload(
        spec,
        pow_chain=pow_chain,
        status=StatusCode.VALID,
        func=run_tick_and_add_block,
        test_steps=test_steps,
    )
    yield 'steps', test_steps


@with_phases([MERGE])
@spec_state_test
def test_too_early_for_merge(spec, state):
    test_steps = []
    # Initialization
    state = build_state_with_incomplete_transition(spec, state)
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield 'anchor_state', state
    yield 'anchor_block', anchor_block
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    assert store.time == current_time

    pow_block_parent = prepare_random_hash_pow_block(spec)
    pow_block_parent.total_difficulty = spec.config.TERMINAL_TOTAL_DIFFICULTY - uint256(2)
    pow_block = prepare_random_hash_pow_block(spec)
    pow_block.parent_hash = pow_block_parent.block_hash
    pow_block.total_difficulty = spec.config.TERMINAL_TOTAL_DIFFICULTY - uint256(1)
    pow_chain = [pow_block, pow_block_parent]
    for pb in pow_chain:
        yield from add_pow_block(pb)

    # Validator guide - get_execution_payload
    fee_recipient = spec.ExecutionAddress(b'\x12' * 20)
    payload_id = spec.PayloadId(1)
    block = build_empty_block_for_next_slot(spec, state)
    block.body.execution_payload = run_get_execution_payload_with_mock_engine_get_payload(
        spec,
        state,
        payload_id=payload_id,
        parent_hash=pow_block.block_hash,
        fee_recipient=fee_recipient,
        test_steps=test_steps,
    )
    signed_block = state_transition_and_sign_block(spec, state, block)

    def run_tick_and_add_block():
        yield from tick_and_add_block(spec, store, signed_block, test_steps, valid=False, merge_block=True)

    yield from with_pow_blocks_and_execute_payload(
        spec,
        pow_chain=pow_chain,
        status=StatusCode.VALID,
        func=run_tick_and_add_block,
        test_steps=test_steps,
    )
    yield 'steps', test_steps


@with_phases([MERGE])
@spec_state_test
def test_too_late_for_merge(spec, state):
    test_steps = []
    # Initialization
    state = build_state_with_incomplete_transition(spec, state)
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield 'anchor_state', state
    yield 'anchor_block', anchor_block
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    assert store.time == current_time

    pow_block_parent = prepare_random_hash_pow_block(spec)
    pow_block_parent.total_difficulty = spec.config.TERMINAL_TOTAL_DIFFICULTY
    pow_block = prepare_random_hash_pow_block(spec)
    pow_block.parent_hash = pow_block_parent.block_hash
    pow_block.total_difficulty = spec.config.TERMINAL_TOTAL_DIFFICULTY + uint256(1)
    pow_chain = [pow_block, pow_block_parent]
    for pb in pow_chain:
        yield from add_pow_block(pb)

    # Validator guide - get_execution_payload
    fee_recipient = spec.ExecutionAddress(b'\x12' * 20)
    payload_id = spec.PayloadId(1)
    block = build_empty_block_for_next_slot(spec, state)
    block.body.execution_payload = run_get_execution_payload_with_mock_engine_get_payload(
        spec,
        state,
        payload_id=payload_id,
        parent_hash=pow_block.block_hash,
        fee_recipient=fee_recipient,
        test_steps=test_steps,
    )

    def run_tick_and_add_block():
        block = build_empty_block_for_next_slot(spec, state)
        block.body.execution_payload.parent_hash = pow_block.block_hash
        signed_block = state_transition_and_sign_block(spec, state, block)
        yield from tick_and_add_block(spec, store, signed_block, test_steps, valid=False, merge_block=True)

    yield from with_pow_blocks_and_execute_payload(
        spec,
        pow_chain=pow_chain,
        status=StatusCode.VALID,
        func=run_tick_and_add_block,
        test_steps=test_steps,
    )

    yield 'steps', test_steps
