from eth2spec.test.context import (
    with_presets,
    spec_state_test,
    with_fulu_and_later,
)
from eth2spec.test.helpers.block import (
    build_empty_block_for_next_slot,
)
from eth2spec.test.helpers.state import (
    state_transition_and_sign_block,
    next_slot,
)
from eth2spec.test.helpers.fork_choice import (
    get_genesis_forkchoice_store_and_block,
    on_tick_and_append_step,
    tick_and_add_block,
    apply_next_slots_with_attestations,
)
from eth2spec.test.helpers.blob import (
    get_sample_blob_tx,
    get_max_blob_count,
    get_sample_blob,
)


def setup_das_test(spec, state, num_blobs=None):
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)

    if num_blobs is None:
        num_blobs = get_max_blob_count(spec)

    # Create block with blob data
    _, blobs, blob_kzg_commitments, _ = get_sample_blob_tx(spec, blob_count=num_blobs)
    block = build_empty_block_for_next_slot(spec, state)
    block.body.blob_kzg_commitments = blob_kzg_commitments
    signed_block = state_transition_and_sign_block(spec, state, block)

    # Compute cells and proofs for each blob individually
    all_cells = []
    all_kzg_proofs = []
    for blob in blobs:
        cells, kzg_proofs = spec.compute_cells_and_kzg_proofs(blob)
        cells_bytes = [cell if isinstance(cell, bytes) else bytes(cell) for cell in cells]
        proofs_bytes = [proof if isinstance(proof, bytes) else bytes(proof) for proof in kzg_proofs]
        all_cells.append(cells_bytes)
        all_kzg_proofs.append(proofs_bytes)

    return store, anchor_block, signed_block, blobs, all_cells, all_kzg_proofs


@with_fulu_and_later
@spec_state_test
def test_das_basic_sampling(spec, state):
    """Test basic DAS functionality with maximum number of blobs."""
    # Setup test
    store, anchor_block, signed_block, blobs, cells, kzg_proofs = setup_das_test(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block

    test_steps = []
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    assert store.time == current_time

    # Verify blob commitments match computed ones
    computed_commitments = [spec.blob_to_kzg_commitment(blob) for blob in blobs]
    assert signed_block.message.body.blob_kzg_commitments == computed_commitments

    # Verify data availability by checking cells and proofs
    for col_idx in range(spec.config.NUMBER_OF_COLUMNS):
        col_cells = [cells[row_idx][col_idx] for row_idx in range(len(blobs))]
        col_proofs = [kzg_proofs[row_idx][col_idx] for row_idx in range(len(blobs))]

        # Verify each cell's KZG proof
        assert spec.verify_cell_kzg_proof_batch(
            commitments_bytes=computed_commitments,  # All commitments
            cell_indices=[col_idx] * len(blobs),  # Same column index for all blobs
            cells=col_cells,  # All cells in this column
            proofs_bytes=col_proofs,  # All proofs in this column
        )

    # Add block to fork choice
    yield from tick_and_add_block(spec, store, signed_block, test_steps)

    # Process attestations to finalize the block
    slots = 4 * spec.SLOTS_PER_EPOCH - state.slot
    post_state, _, _ = yield from apply_next_slots_with_attestations(
        spec, state, store, slots, True, True, test_steps
    )

    yield "steps", test_steps


@with_fulu_and_later
@spec_state_test
def test_das_minimal_blobs(spec, state):
    """Test DAS functionality with minimum number of blobs (1)."""
    # Setup test with single blob
    store, anchor_block, signed_block, blobs, cells, kzg_proofs = setup_das_test(
        spec, state, num_blobs=1
    )
    yield "anchor_state", state
    yield "anchor_block", anchor_block

    test_steps = []
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    assert store.time == current_time

    # Verify single blob commitment
    assert len(signed_block.message.body.blob_kzg_commitments) == 1
    assert signed_block.message.body.blob_kzg_commitments[0] == spec.blob_to_kzg_commitment(
        blobs[0]
    )

    # Verify data availability
    for col_idx in range(spec.config.NUMBER_OF_COLUMNS):
        cell = cells[0][col_idx]
        proof = kzg_proofs[0][col_idx]
        assert spec.verify_cell_kzg_proof_batch(
            commitments_bytes=[spec.blob_to_kzg_commitment(blobs[0])],  # Single commitment
            cell_indices=[col_idx],  # Single column index
            cells=[cell],  # Single cell
            proofs_bytes=[proof],  # Single proof
        )

    # Add block to fork choice
    yield from tick_and_add_block(spec, store, signed_block, test_steps)

    # Process attestations to finalize the block
    slots = 4 * spec.SLOTS_PER_EPOCH - state.slot
    post_state, _, _ = yield from apply_next_slots_with_attestations(
        spec, state, store, slots, True, True, test_steps
    )

    yield "steps", test_steps


@with_fulu_and_later
@spec_state_test
def test_das_reconstruction(spec, state):
    """Test DAS reconstruction with different column counts."""
    # Setup test
    store, anchor_block, signed_block, blobs, cells, kzg_proofs = setup_das_test(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block

    test_steps = []
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    assert store.time == current_time

    # Ensure we have at least 50% of cells for reconstruction
    required_columns = spec.CELLS_PER_EXT_BLOB // 2
    available_cells = []
    available_indices = []

    for col_idx in range(required_columns):
        available_cells.append(cells[0][col_idx])
        available_indices.append(col_idx)

    # Verify we can reconstruct the full data from partial columns
    reconstructed_cells, reconstructed_proofs = spec.recover_cells_and_kzg_proofs(
        available_indices, available_cells
    )

    # Verify reconstructed data matches original
    assert len(reconstructed_cells) == spec.CELLS_PER_EXT_BLOB
    assert len(reconstructed_proofs) == spec.CELLS_PER_EXT_BLOB
    for col_idx in range(spec.CELLS_PER_EXT_BLOB):
        assert reconstructed_cells[col_idx] == cells[0][col_idx]
        assert reconstructed_proofs[col_idx] == kzg_proofs[0][col_idx]

    # Add block to fork choice
    yield from tick_and_add_block(spec, store, signed_block, test_steps)

    # Process attestations to finalize the block
    slots = 4 * spec.SLOTS_PER_EPOCH - state.slot
    post_state, _, _ = yield from apply_next_slots_with_attestations(
        spec, state, store, slots, True, True, test_steps
    )

    yield "steps", test_steps


@with_fulu_and_later
@spec_state_test
def test_das_invalid_proofs(spec, state):
    """Test DAS with various invalid proof scenarios."""
    # Setup test
    store, anchor_block, signed_block, blobs, cells, kzg_proofs = setup_das_test(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block

    test_steps = []
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    assert store.time == current_time

    valid_point = spec.G1_POINT_AT_INFINITY
    invalid_proof = spec.KZGProof(valid_point)

    # 1. Invalid proof in first cell
    modified_proofs = list(kzg_proofs[0])
    modified_proofs[0] = invalid_proof
    assert not spec.verify_cell_kzg_proof_batch(
        commitments_bytes=[spec.blob_to_kzg_commitment(blobs[0])],  # Single commitment
        cell_indices=[0],  # First column
        cells=[cells[0][0]],  # First cell
        proofs_bytes=[modified_proofs[0]],  # Modified proof
    )

    # 2. Invalid proof in last cell
    modified_proofs = list(kzg_proofs[-1])
    modified_proofs[-1] = invalid_proof
    assert not spec.verify_cell_kzg_proof_batch(
        commitments_bytes=[spec.blob_to_kzg_commitment(blobs[-1])],  # Single commitment
        cell_indices=[spec.config.NUMBER_OF_COLUMNS - 1],  # Last column
        cells=[cells[-1][-1]],  # Last cell
        proofs_bytes=[modified_proofs[-1]],  # Modified proof
    )

    # 3. Invalid proof in middle cell
    mid_col = spec.config.NUMBER_OF_COLUMNS // 2
    mid_row = len(blobs) // 2
    modified_proofs = list(kzg_proofs[mid_row])
    modified_proofs[mid_col] = invalid_proof
    assert not spec.verify_cell_kzg_proof_batch(
        commitments_bytes=[spec.blob_to_kzg_commitment(blobs[mid_row])],  # Single commitment
        cell_indices=[mid_col],  # Middle column
        cells=[cells[mid_row][mid_col]],  # Middle cell
        proofs_bytes=[modified_proofs[mid_col]],  # Modified proof
    )

    # Add block to fork choice
    yield from tick_and_add_block(spec, store, signed_block, test_steps)

    # Process attestations to finalize the block
    slots = 4 * spec.SLOTS_PER_EPOCH - state.slot
    post_state, _, _ = yield from apply_next_slots_with_attestations(
        spec, state, store, slots, True, True, test_steps
    )

    yield "steps", test_steps


@with_fulu_and_later
@spec_state_test
def test_das_invalid_blob_data(spec, state):
    """Test DAS with invalid blob data."""
    # Setup test with invalid blob
    store, anchor_block, signed_block, blobs, cells, kzg_proofs = setup_das_test(
        spec, state, num_blobs=1
    )
    yield "anchor_state", state
    yield "anchor_block", anchor_block

    test_steps = []
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    assert store.time == current_time

    # Create an invalid blob (outside BLS field)
    invalid_blob = get_sample_blob(spec, is_valid_blob=False)

    # Verify that invalid blob data is detected
    try:
        spec.compute_cells_and_kzg_proofs([invalid_blob])
        assert False, "Should have raised an exception for invalid blob data"
    except Exception:
        pass

    # Add block to fork choice
    yield from tick_and_add_block(spec, store, signed_block, test_steps)

    # Process attestations to finalize the block
    slots = 4 * spec.SLOTS_PER_EPOCH - state.slot
    post_state, _, _ = yield from apply_next_slots_with_attestations(
        spec, state, store, slots, True, True, test_steps
    )

    yield "steps", test_steps
