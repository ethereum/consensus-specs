from eth2spec.test.context import (
    spec_state_test,
    with_bellatrix_until_eip7732,
)
from eth2spec.test.helpers.attestations import (
    state_transition_with_full_block,
)
from eth2spec.test.helpers.block import (
    build_empty_block_for_next_slot,
)
from eth2spec.test.helpers.execution_payload import (
    compute_el_block_hash,
)
from eth2spec.test.helpers.fork_choice import (
    get_genesis_forkchoice_store_and_block,
    on_tick_and_append_step,
)
from eth2spec.test.helpers.optimistic_sync import (
    MegaStore,
    PayloadStatusV1,
    PayloadStatusV1Status,
    add_optimistic_block,
    get_optimistic_store,
)
from eth2spec.test.helpers.state import (
    next_epoch,
    state_transition_and_sign_block,
)


@with_bellatrix_until_eip7732
@spec_state_test
def test_from_syncing_to_invalid(spec, state):
    test_steps = []
    # Initialization
    fc_store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    op_store = get_optimistic_store(spec, state, anchor_block)
    mega_store = MegaStore(spec, fc_store, op_store)
    block_hashes = {}
    yield "anchor_state", state
    yield "anchor_block", anchor_block

    next_epoch(spec, state)

    current_time = (
        spec.SAFE_SLOTS_TO_IMPORT_OPTIMISTICALLY * 10 + state.slot
    ) * spec.config.SECONDS_PER_SLOT + fc_store.genesis_time
    on_tick_and_append_step(spec, fc_store, current_time, test_steps)

    # Block 0
    block_0 = build_empty_block_for_next_slot(spec, state)
    block_hashes["block_0"] = block_0.body.execution_payload.block_hash
    signed_block = state_transition_and_sign_block(spec, state, block_0)
    yield from add_optimistic_block(
        spec, mega_store, signed_block, test_steps, status=PayloadStatusV1Status.VALID
    )
    assert spec.get_head(mega_store.fc_store) == mega_store.opt_store.head_block_root

    state_0 = state.copy()

    # Create VALID chain `a`
    signed_blocks_a = []
    for i in range(3):
        block = build_empty_block_for_next_slot(spec, state)
        block.body.execution_payload.parent_hash = (
            block_hashes[f"chain_a_{i - 1}"] if i != 0 else block_hashes["block_0"]
        )
        block.body.execution_payload.extra_data = spec.hash(bytes(f"chain_a_{i}", "UTF-8"))
        block.body.execution_payload.block_hash = compute_el_block_hash(
            spec, block.body.execution_payload, state
        )
        block_hashes[f"chain_a_{i}"] = block.body.execution_payload.block_hash

        signed_block = state_transition_and_sign_block(spec, state, block)
        yield from add_optimistic_block(
            spec, mega_store, signed_block, test_steps, status=PayloadStatusV1Status.VALID
        )
        assert spec.get_head(mega_store.fc_store) == mega_store.opt_store.head_block_root
        signed_blocks_a.append(signed_block.copy())

    # Create SYNCING chain `b`
    signed_blocks_b = []
    state = state_0.copy()
    for i in range(3):
        block = build_empty_block_for_next_slot(spec, state)
        block.body.execution_payload.parent_hash = (
            block_hashes[f"chain_b_{i - 1}"] if i != 0 else block_hashes["block_0"]
        )
        block.body.execution_payload.extra_data = spec.hash(bytes(f"chain_b_{i}", "UTF-8"))
        block.body.execution_payload.block_hash = compute_el_block_hash(
            spec, block.body.execution_payload, state
        )
        block_hashes[f"chain_b_{i}"] = block.body.execution_payload.block_hash

        signed_block = state_transition_with_full_block(spec, state, True, True, block=block)
        signed_blocks_b.append(signed_block.copy())
        yield from add_optimistic_block(
            spec, mega_store, signed_block, test_steps, status=PayloadStatusV1Status.SYNCING
        )
        assert spec.get_head(mega_store.fc_store) == mega_store.opt_store.head_block_root

    # Now add block 4 to chain `b` with INVALID
    block = build_empty_block_for_next_slot(spec, state)
    block.body.execution_payload.parent_hash = signed_blocks_b[
        -1
    ].message.body.execution_payload.block_hash
    block.body.execution_payload.extra_data = spec.hash(bytes(f"chain_b_{i}", "UTF-8"))
    block.body.execution_payload.block_hash = compute_el_block_hash(
        spec, block.body.execution_payload, state
    )
    block_hashes["chain_b_3"] = block.body.execution_payload.block_hash

    # Ensure that no duplicate block hashes
    assert len(block_hashes) == len(set(block_hashes.values()))

    signed_block = state_transition_and_sign_block(spec, state, block)
    payload_status = PayloadStatusV1(
        status=PayloadStatusV1Status.INVALID,
        latest_valid_hash=block_0.body.execution_payload.block_hash,
        validation_error="invalid",
    )
    yield from add_optimistic_block(
        spec, mega_store, signed_block, test_steps, payload_status=payload_status
    )
    assert mega_store.opt_store.head_block_root == signed_blocks_a[-1].message.hash_tree_root()

    yield "steps", test_steps
