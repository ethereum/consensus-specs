from eth2spec.test.context import (
    MINIMAL,
    spec_state_test,
    with_merge_and_later,
    with_presets,
)
from eth2spec.test.helpers.block import (
    build_empty_block_for_next_slot,
)
from eth2spec.test.helpers.engine_apis import (
    StatusCode,
    with_mock_engine_prepare_payload,
    with_pow_blocks_and_execute_payload,
)
from eth2spec.test.helpers.execution_payload import (
    build_state_with_incomplete_transition,
    build_empty_execution_payload,
)
from eth2spec.test.helpers.fork_choice import (
    add_pow_block,
    get_genesis_forkchoice_store_and_block,
    on_tick_and_append_step,
    prepare_empty_pow_block,
    tick_and_add_block,
)
from eth2spec.test.helpers.state import (
    state_transition_and_sign_block,
)


@with_merge_and_later
@with_presets([MINIMAL], reason="WIP")  # FIXME: remove it later
@spec_state_test
def test_engine_execution_payload(spec, state):
    test_steps = []
    # Initialization
    state = build_state_with_incomplete_transition(spec, state)
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield 'anchor_state', state
    yield 'anchor_block', anchor_block
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    assert store.time == current_time

    pow_block_parent = prepare_empty_pow_block(spec)
    pow_block_parent.total_difficulty = spec.config.TERMINAL_TOTAL_DIFFICULTY - 1
    pow_block = prepare_empty_pow_block(spec)
    pow_block.parent_hash = pow_block_parent.block_hash
    pow_block.total_difficulty = spec.config.TERMINAL_TOTAL_DIFFICULTY
    pow_chain = [pow_block, pow_block_parent]
    for pb in pow_chain:
        yield from add_pow_block(spec, store, pb, test_steps)

    fee_recipient = b'\x12' * 20
    payload_id = spec.PayloadId(1)

    # For the block proposer
    def run_prepare_execution_payload():
        spec.prepare_execution_payload(
            state,
            pow_chain,
            fee_recipient=fee_recipient,
            execution_engine=spec.EXECUTION_ENGINE,
        )

    with_mock_engine_prepare_payload(
        spec,
        parent_hash=pow_block.parent_hash,
        timestamp=spec.compute_timestamp_at_slot(state, state.slot),
        random=spec.get_randao_mix(state, spec.get_current_epoch(state)),
        fee_recipient=fee_recipient,
        payload_id=payload_id,
        func=run_prepare_execution_payload,
        test_steps=test_steps,
    )

    block = build_empty_block_for_next_slot(spec, state)
    block.body.execution_payload.parent_hash = pow_block.block_hash
    signed_block = state_transition_and_sign_block(spec, state, block)

    # For on_block
    def run_tick_and_add_block():
        yield from tick_and_add_block(spec, store, signed_block, test_steps, merge_block=True)
        # valid
        assert spec.get_head(store) == signed_block.message.hash_tree_root()

    yield from with_pow_blocks_and_execute_payload(
        spec,
        pow_chain=pow_chain,
        # FIXME: use `get_execution_payload` in validator guide and mock execution_engine.get_payload(payload_id)
        status=StatusCode.VALID,
        payload=build_empty_execution_payload(spec, state),
        func=run_tick_and_add_block,
        test_steps=test_steps,
    )

    yield 'steps', test_steps
