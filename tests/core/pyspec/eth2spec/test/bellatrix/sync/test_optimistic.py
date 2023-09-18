from collections import defaultdict

from eth2spec.test.context import (
    spec_state_test,
    with_bellatrix_and_later,
)
from eth2spec.test.helpers.attestations import (
    build_attestation_data,
    sign_attestation,
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
    PayloadStatusV1,
    PayloadStatusV1Status,
    MegaStore,
    add_optimistic_block,
    get_optimistic_store,
)
from eth2spec.test.helpers.state import (
    next_epoch,
    state_transition_and_sign_block,
)


@with_bellatrix_and_later
@spec_state_test
def test_from_syncing_to_invalid(spec, state):
    test_steps = []
    # Initialization
    fc_store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    op_store = get_optimistic_store(spec, state, anchor_block)
    mega_store = MegaStore(spec, fc_store, op_store)
    block_hashes = {}
    yield 'anchor_state', state
    yield 'anchor_block', anchor_block

    next_epoch(spec, state)

    current_time = (
        (spec.SAFE_SLOTS_TO_IMPORT_OPTIMISTICALLY * 10 + state.slot) * spec.config.SECONDS_PER_SLOT
        + fc_store.genesis_time
    )
    on_tick_and_append_step(spec, fc_store, current_time, test_steps)

    # Block 0
    block_0 = build_empty_block_for_next_slot(spec, state)
    block_hashes['block_0'] = block_0.body.execution_payload.block_hash
    signed_block = state_transition_and_sign_block(spec, state, block_0)
    yield from add_optimistic_block(spec, mega_store, signed_block, test_steps, status=PayloadStatusV1Status.VALID)
    assert spec.get_head(mega_store.fc_store) == mega_store.opt_store.head_block_root

    state_0 = state.copy()

    # Create VALID chain `a`
    signed_blocks_a = []
    for i in range(3):
        block = build_empty_block_for_next_slot(spec, state)
        block.body.execution_payload.parent_hash = (
            block_hashes[f'chain_a_{i - 1}'] if i != 0 else block_hashes['block_0']
        )
        block.body.execution_payload.extra_data = spec.hash(bytes(f'chain_a_{i}', 'UTF-8'))
        block.body.execution_payload.block_hash = compute_el_block_hash(spec, block.body.execution_payload)
        block_hashes[f'chain_a_{i}'] = block.body.execution_payload.block_hash

        signed_block = state_transition_and_sign_block(spec, state, block)
        yield from add_optimistic_block(spec, mega_store, signed_block, test_steps, status=PayloadStatusV1Status.VALID)
        assert spec.get_head(mega_store.fc_store) == mega_store.opt_store.head_block_root
        signed_blocks_a.append(signed_block.copy())

    # Create SYNCING chain `b`
    signed_blocks_b = []
    state = state_0.copy()
    for i in range(3):
        block = build_empty_block_for_next_slot(spec, state)
        block.body.execution_payload.parent_hash = (
            block_hashes[f'chain_b_{i - 1}'] if i != 0 else block_hashes['block_0']
        )
        block.body.execution_payload.extra_data = spec.hash(bytes(f'chain_b_{i}', 'UTF-8'))
        block.body.execution_payload.block_hash = compute_el_block_hash(spec, block.body.execution_payload)
        block_hashes[f'chain_b_{i}'] = block.body.execution_payload.block_hash

        signed_block = state_transition_with_full_block(spec, state, True, True, block=block)
        signed_blocks_b.append(signed_block.copy())
        yield from add_optimistic_block(spec, mega_store, signed_block, test_steps,
                                        status=PayloadStatusV1Status.SYNCING)
        assert spec.get_head(mega_store.fc_store) == mega_store.opt_store.head_block_root

    # Now add block 4 to chain `b` with INVALID
    block = build_empty_block_for_next_slot(spec, state)
    block.body.execution_payload.parent_hash = signed_blocks_b[-1].message.body.execution_payload.block_hash
    block.body.execution_payload.extra_data = spec.hash(bytes(f'chain_b_{i}', 'UTF-8'))
    block.body.execution_payload.block_hash = compute_el_block_hash(spec, block.body.execution_payload)
    block_hashes['chain_b_3'] = block.body.execution_payload.block_hash

    # Ensure that no duplicate block hashes
    assert len(block_hashes) == len(set(block_hashes.values()))

    signed_block = state_transition_and_sign_block(spec, state, block)
    payload_status = PayloadStatusV1(
        status=PayloadStatusV1Status.INVALID,
        latest_valid_hash=block_0.body.execution_payload.block_hash,
        validation_error="invalid",
    )
    yield from add_optimistic_block(spec, mega_store, signed_block, test_steps,
                                    payload_status=payload_status)
    assert mega_store.opt_store.head_block_root == signed_blocks_a[-1].message.hash_tree_root()

    yield 'steps', test_steps


def sign_block_with_aggregation_bit_list(spec, state, block, index, aggregation_bit_list):
    attestation_data = build_attestation_data(
        spec, state, slot=state.slot, index=index
    )
    committee = spec.get_beacon_committee(state, attestation_data.slot, attestation_data.index)
    number_empty_aggregation = len(committee) - len(aggregation_bit_list)
    attestation = spec.Attestation(
        aggregation_bits=spec.Bitlist[spec.MAX_VALIDATORS_PER_COMMITTEE](
            *(*(aggregation_bit_list), *([0] * number_empty_aggregation))
        ),
        data=attestation_data,
    )
    sign_attestation(spec, state, attestation)

    block.body.attestations.append(attestation)

    return state_transition_and_sign_block(spec, state, block)


@with_bellatrix_and_later
@spec_state_test
def test_multiple_branches_sync_all_invalidated_but_one(spec, state):
    test_steps = []
    # Initialization
    fc_store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    op_store = get_optimistic_store(spec, state, anchor_block)
    mega_store = MegaStore(spec, fc_store, op_store)
    block_hashes, signed_blocks, state_store = {}, {}, {}
    yield 'anchor_state', state
    yield 'anchor_block', anchor_block

    next_epoch(spec, state)

    current_slot = spec.SAFE_SLOTS_TO_IMPORT_OPTIMISTICALLY * 10 + state.slot
    current_time = (
        current_slot * spec.config.SECONDS_PER_SLOT
        + fc_store.genesis_time
    )
    on_tick_and_append_step(spec, fc_store, current_time, test_steps)

    # Block 0
    block_0 = build_empty_block_for_next_slot(spec, state)
    block_hashes['block_0'] = block_0.body.execution_payload.block_hash
    signed_block = state_transition_and_sign_block(spec, state, block_0)
    yield from add_optimistic_block(spec, mega_store, signed_block, test_steps, status=PayloadStatusV1Status.VALID)
    assert spec.get_head(mega_store.fc_store) == mega_store.opt_store.head_block_root

    # Create SYNC chains
    state_0 = state.copy()
    # Branch A has 4 attestations, B 1 attestation and C 2 attestation
    # A >> C >> B
    aggregation_bit_lists = [[1, 1, 1, 0], [1, 0, 0, 0], [0, 0, 1, 1]]
    for j, level in enumerate(["a", "b", "c"]):
        state = state_0.copy()
        for i in range(3):
            block = build_empty_block_for_next_slot(spec, state)
            block.body.execution_payload.parent_hash = (
                block_hashes[f'chain_{level}_{i - 1}'] if i != 0 else block_hashes['block_0']
            )
            block.body.execution_payload.extra_data = spec.hash(bytes(f'chain_{level}_{i}', 'UTF-8'))
            block.body.execution_payload.block_hash = compute_el_block_hash(spec, block.body.execution_payload)
            block_hashes[f'chain_{level}_{i}'] = block.body.execution_payload.block_hash

            max_committee_index = spec.get_committee_count_per_slot(state, current_slot)
            committee_index = min(j, max_committee_index - 1)
            signed_block = sign_block_with_aggregation_bit_list(
                spec, state, block, committee_index, aggregation_bit_lists[j]
            )
            signed_blocks[f'chain_{level}_{i}'] = signed_block.copy()

            yield from add_optimistic_block(spec, mega_store, signed_block, test_steps,
                                            status=PayloadStatusV1Status.SYNCING)
            assert spec.get_head(mega_store.fc_store) == mega_store.opt_store.head_block_root
        state_store[level] = state.copy()

    # Check chain A is the optimistic head
    assert mega_store.opt_store.head_block_root == spec.Root(signed_blocks['chain_a_2'].message.hash_tree_root())

    latest_valid_hash = block_0.body.execution_payload.block_hash

    # Add an invalid block to chain A
    block = build_empty_block_for_next_slot(spec, state_store["a"])
    block.body.execution_payload.parent_hash = signed_blocks['chain_a_2'].message.body.execution_payload.block_hash
    block.body.execution_payload.extra_data = spec.hash(bytes('chain_a_3', 'UTF-8'))
    block.body.execution_payload.block_hash = compute_el_block_hash(spec, block.body.execution_payload)
    signed_block = state_transition_and_sign_block(spec, state_store["a"], block)
    payload_status = PayloadStatusV1(
        status=PayloadStatusV1Status.INVALID,
        latest_valid_hash=latest_valid_hash,
        validation_error="invalid",
    )
    yield from add_optimistic_block(spec, mega_store, signed_block, test_steps,
                                    payload_status=payload_status)
    # Check chain C became the optimistic head
    assert mega_store.opt_store.head_block_root == spec.Root(signed_blocks['chain_c_2'].message.hash_tree_root())

    # Add an invalid block to chain C
    block = build_empty_block_for_next_slot(spec, state_store["c"])
    block.body.execution_payload.parent_hash = signed_blocks['chain_c_2'].message.body.execution_payload.block_hash
    block.body.execution_payload.extra_data = spec.hash(bytes('chain_c_3', 'UTF-8'))
    block.body.execution_payload.block_hash = compute_el_block_hash(spec, block.body.execution_payload)
    signed_block = state_transition_and_sign_block(spec, state_store["c"], block)
    payload_status = PayloadStatusV1(
        status=PayloadStatusV1Status.INVALID,
        latest_valid_hash=latest_valid_hash,
        validation_error="invalid",
    )
    yield from add_optimistic_block(spec, mega_store, signed_block, test_steps,
                                    payload_status=payload_status)
    # Check chain B became the optimistic head
    assert mega_store.opt_store.head_block_root == spec.Root(signed_blocks['chain_b_2'].message.hash_tree_root())


@with_bellatrix_and_later
@spec_state_test
def test_multiple_branches_sync_all_invalidated_but_one_equal_weight(spec, state):
    test_steps = []
    # Initialization
    fc_store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    op_store = get_optimistic_store(spec, state, anchor_block)
    mega_store = MegaStore(spec, fc_store, op_store)
    block_hashes, signed_blocks, state_store, signed_blocks_message_hash = (
        {},
        {},
        {},
        defaultdict(list),
    )
    yield "anchor_state", state
    yield "anchor_block", anchor_block

    next_epoch(spec, state)

    current_slot = spec.SAFE_SLOTS_TO_IMPORT_OPTIMISTICALLY * 10 + state.slot
    current_time = current_slot * spec.config.SECONDS_PER_SLOT + fc_store.genesis_time
    on_tick_and_append_step(spec, fc_store, current_time, test_steps)

    # Block 0
    block_0 = build_empty_block_for_next_slot(spec, state)
    block_hashes["block_0"] = block_0.body.execution_payload.block_hash
    signed_block = state_transition_and_sign_block(spec, state, block_0)
    yield from add_optimistic_block(
        spec, mega_store, signed_block, test_steps, status=PayloadStatusV1Status.VALID
    )
    assert spec.get_head(mega_store.fc_store) == mega_store.opt_store.head_block_root

    # Create SYNC chains
    state_0 = state.copy()
    aggregation_bit_lists = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0]]
    branch_levels = ["a", "b", "c"]
    for j, level in enumerate(branch_levels):
        state = state_0.copy()
        for i in range(3):
            block = build_empty_block_for_next_slot(spec, state)
            block.body.execution_payload.parent_hash = (
                block_hashes[f"chain_{level}_{i - 1}"]
                if i != 0
                else block_hashes["block_0"]
            )
            block.body.execution_payload.extra_data = spec.hash(
                bytes(f"chain_{level}_{i}", "UTF-8")
            )
            block.body.execution_payload.block_hash = compute_el_block_hash(
                spec, block.body.execution_payload
            )
            block_hashes[f"chain_{level}_{i}"] = block.body.execution_payload.block_hash

            max_committee_index = spec.get_committee_count_per_slot(state, current_slot)
            committee_index = min(j, max_committee_index - 1)
            signed_block = sign_block_with_aggregation_bit_list(
                spec, state, block, committee_index, aggregation_bit_lists[j]
            )
            signed_blocks[f"chain_{level}_{i}"] = signed_block.copy()
            signed_blocks_message_hash[i].append(
                spec.Root(signed_block.message.hash_tree_root())
            )

            yield from add_optimistic_block(
                spec,
                mega_store,
                signed_block,
                test_steps,
                status=PayloadStatusV1Status.SYNCING,
            )
            assert (
                spec.get_head(mega_store.fc_store)
                == mega_store.opt_store.head_block_root
            )
        state_store[level] = state.copy()

    # Since there is a weight equality, the fork head decision is done regarding the hash value
    # of a signed block.
    # Also, since each fork/preset can lead to a different hash, we need to know which branch has the
    # highest root value to make the below assertion.
    first_hash_levels = signed_blocks_message_hash[0]
    optimistic_head_level = first_hash_levels.index(max(first_hash_levels))
    optimistic_head_branch = branch_levels[optimistic_head_level]
    assert mega_store.opt_store.head_block_root == spec.Root(
        signed_blocks[f"chain_{optimistic_head_branch}_2"].message.hash_tree_root()
    )
    first_hash_levels[optimistic_head_level] = spec.Root()

    latest_valid_hash = block_0.body.execution_payload.block_hash

    # Add an invalid block to head chain
    block = build_empty_block_for_next_slot(spec, state_store[optimistic_head_branch])
    block.body.execution_payload.parent_hash = signed_blocks[
        f"chain_{optimistic_head_branch}_2"
    ].message.body.execution_payload.block_hash
    block.body.execution_payload.extra_data = spec.hash(
        bytes(f"chain_{optimistic_head_branch}_3", "UTF-8")
    )
    block.body.execution_payload.block_hash = compute_el_block_hash(
        spec, block.body.execution_payload
    )
    signed_block = state_transition_and_sign_block(
        spec, state_store[optimistic_head_branch], block
    )
    payload_status = PayloadStatusV1(
        status=PayloadStatusV1Status.INVALID,
        latest_valid_hash=latest_valid_hash,
        validation_error="invalid",
    )
    yield from add_optimistic_block(
        spec, mega_store, signed_block, test_steps, payload_status=payload_status
    )

    optimistic_head_level = first_hash_levels.index(max(first_hash_levels))
    optimistic_head_branch = branch_levels[optimistic_head_level]
    assert mega_store.opt_store.head_block_root == spec.Root(
        signed_blocks[f"chain_{optimistic_head_branch}_2"].message.hash_tree_root()
    )
    first_hash_levels[optimistic_head_level] = spec.Root()

    # Add an invalid block to head chain
    block = build_empty_block_for_next_slot(spec, state_store[optimistic_head_branch])
    block.body.execution_payload.parent_hash = signed_blocks[
        f"chain_{optimistic_head_branch}_2"
    ].message.body.execution_payload.block_hash
    block.body.execution_payload.extra_data = spec.hash(
        bytes(f"chain_{optimistic_head_branch}_3", "UTF-8")
    )
    block.body.execution_payload.block_hash = compute_el_block_hash(
        spec, block.body.execution_payload
    )
    signed_block = state_transition_and_sign_block(
        spec, state_store[optimistic_head_branch], block
    )
    payload_status = PayloadStatusV1(
        status=PayloadStatusV1Status.INVALID,
        latest_valid_hash=latest_valid_hash,
        validation_error="invalid",
    )
    yield from add_optimistic_block(
        spec, mega_store, signed_block, test_steps, payload_status=payload_status
    )

    optimistic_head_level = first_hash_levels.index(max(first_hash_levels))
    assert mega_store.opt_store.head_block_root == spec.Root(
        signed_blocks[
            f"chain_{branch_levels[optimistic_head_level]}_2"
        ].message.hash_tree_root()
    )
