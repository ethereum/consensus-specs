from eth_consensus_specs.test.context import (
    spec_state_test,
    with_gloas_and_later,
)
from eth_consensus_specs.test.helpers.blob import get_block_with_blob_and_sidecars
from eth_consensus_specs.test.helpers.fork_choice import (
    get_genesis_forkchoice_store_and_block,
)
from eth_consensus_specs.test.helpers.gossip import (
    get_filename,
    get_seen,
    run_validate_gossip,
    wrap_genesis_block,
)


def setup_gloas_partial_sidecar(spec, state, blob_indices=None):
    """
    Build a signed block carrying one blob, then derive a partial sidecar from
    the resulting data column. Returns (store, signed_anchor, signed_block,
    partial_sidecar, group_id, column_index).
    """
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    _, _, _, signed_block, sidecars, _ = get_block_with_blob_and_sidecars(spec, state, blob_count=1)
    block_root = signed_block.message.hash_tree_root()
    store.blocks[block_root] = signed_block.message
    store.block_states[block_root] = state.copy()

    sidecar = sidecars[0]
    num_blobs = len(sidecar.column)
    if blob_indices is None:
        blob_indices = list(range(num_blobs))
    bitmap = [i in blob_indices for i in range(num_blobs)]
    cells = [sidecar.column[i] for i in blob_indices]
    proofs = [sidecar.kzg_proofs[i] for i in blob_indices]

    partial = spec.PartialDataColumnSidecar(
        cells_present_bitmap=bitmap,
        partial_column=cells,
        kzg_proofs=proofs,
    )
    group_id = spec.PartialDataColumnGroupID(
        slot=sidecar.slot,
        beacon_block_root=sidecar.beacon_block_root,
    )
    return store, signed_anchor, signed_block, partial, group_id, sidecar.index


@with_gloas_and_later
@spec_state_test
def test_gossip_partial_data_column_sidecar__valid(spec, state):
    """A well-formed partial sidecar with cells matching the bid passes."""
    yield "topic", "meta", "partial_data_column_sidecar"

    store, signed_anchor, signed_block, partial, group_id, column_index = (
        setup_gloas_partial_sidecar(spec, state)
    )
    yield "state", state
    yield get_filename(signed_anchor), signed_anchor
    yield get_filename(signed_block), signed_block
    yield (
        "blocks",
        "meta",
        [
            {"block": get_filename(signed_anchor)},
            {"block": get_filename(signed_block)},
        ],
    )
    yield get_filename(partial), partial

    seen = get_seen(spec)
    time_ms = spec.compute_time_at_slot_ms(state, group_id.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 500
    result, reason = run_validate_gossip(
        spec,
        seen,
        store,
        state,
        partial,
        group_id=group_id,
        column_index=column_index,
    )
    assert result == "valid"
    assert reason is None
    messages.append(
        {
            "block_root": "0x" + group_id.beacon_block_root.hex(),
            "column_index": int(column_index),
            "current_time_ms": int(time_ms),
            "message": get_filename(partial),
            "expected": result,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_partial_data_column_sidecar__reject_empty(spec, state):
    """A partial sidecar with no cells set is rejected as semantically empty."""
    yield "topic", "meta", "partial_data_column_sidecar"

    store, signed_anchor, signed_block, partial, group_id, column_index = (
        setup_gloas_partial_sidecar(spec, state, blob_indices=[])
    )
    yield "state", state
    yield get_filename(signed_anchor), signed_anchor
    yield get_filename(signed_block), signed_block
    yield (
        "blocks",
        "meta",
        [
            {"block": get_filename(signed_anchor)},
            {"block": get_filename(signed_block)},
        ],
    )
    yield get_filename(partial), partial

    seen = get_seen(spec)
    time_ms = spec.compute_time_at_slot_ms(state, group_id.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 500
    result, reason = run_validate_gossip(
        spec,
        seen,
        store,
        state,
        partial,
        group_id=group_id,
        column_index=column_index,
    )
    assert result == "reject"
    assert reason == "partial message is semantically empty"
    messages.append(
        {
            "block_root": "0x" + group_id.beacon_block_root.hex(),
            "column_index": int(column_index),
            "current_time_ms": int(time_ms),
            "message": get_filename(partial),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_partial_data_column_sidecar__reject_slot_mismatch(spec, state):
    """A partial sidecar whose group_id.slot doesn't match the block is rejected."""
    yield "topic", "meta", "partial_data_column_sidecar"

    store, signed_anchor, signed_block, partial, group_id, column_index = (
        setup_gloas_partial_sidecar(spec, state)
    )
    # Bump the slot so it no longer matches.
    group_id.slot = spec.Slot(group_id.slot + 1)

    yield "state", state
    yield get_filename(signed_anchor), signed_anchor
    yield get_filename(signed_block), signed_block
    yield (
        "blocks",
        "meta",
        [
            {"block": get_filename(signed_anchor)},
            {"block": get_filename(signed_block)},
        ],
    )
    yield get_filename(partial), partial

    seen = get_seen(spec)
    time_ms = spec.compute_time_at_slot_ms(state, group_id.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 500
    result, reason = run_validate_gossip(
        spec,
        seen,
        store,
        state,
        partial,
        group_id=group_id,
        column_index=column_index,
    )
    assert result == "reject"
    assert reason == "group id's slot does not match the block's slot"
    messages.append(
        {
            "block_root": "0x" + group_id.beacon_block_root.hex(),
            "column_index": int(column_index),
            "current_time_ms": int(time_ms),
            "message": get_filename(partial),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_partial_data_column_sidecar__reject_cells_count_mismatch(spec, state):
    """A partial sidecar whose cell count differs from the bitmap is rejected."""
    yield "topic", "meta", "partial_data_column_sidecar"

    store, signed_anchor, signed_block, partial, group_id, column_index = (
        setup_gloas_partial_sidecar(spec, state)
    )
    partial.partial_column = spec.List[spec.Cell, spec.MAX_BLOB_COMMITMENTS_PER_BLOCK](
        *partial.partial_column, spec.Cell()
    )

    yield "state", state
    yield get_filename(signed_anchor), signed_anchor
    yield get_filename(signed_block), signed_block
    yield (
        "blocks",
        "meta",
        [
            {"block": get_filename(signed_anchor)},
            {"block": get_filename(signed_block)},
        ],
    )
    yield get_filename(partial), partial

    seen = get_seen(spec)
    time_ms = spec.compute_time_at_slot_ms(state, group_id.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 500
    result, reason = run_validate_gossip(
        spec,
        seen,
        store,
        state,
        partial,
        group_id=group_id,
        column_index=column_index,
    )
    assert result == "reject"
    assert reason == "number of cells does not match number of set bits"
    messages.append(
        {
            "block_root": "0x" + group_id.beacon_block_root.hex(),
            "column_index": int(column_index),
            "current_time_ms": int(time_ms),
            "message": get_filename(partial),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_partial_data_column_sidecar__reject_proofs_count_mismatch(spec, state):
    """A partial sidecar whose proof count differs from the bitmap is rejected."""
    yield "topic", "meta", "partial_data_column_sidecar"

    store, signed_anchor, signed_block, partial, group_id, column_index = (
        setup_gloas_partial_sidecar(spec, state)
    )
    partial.kzg_proofs = spec.List[spec.KZGProof, spec.MAX_BLOB_COMMITMENTS_PER_BLOCK](
        *partial.kzg_proofs, spec.KZGProof()
    )

    yield "state", state
    yield get_filename(signed_anchor), signed_anchor
    yield get_filename(signed_block), signed_block
    yield (
        "blocks",
        "meta",
        [
            {"block": get_filename(signed_anchor)},
            {"block": get_filename(signed_block)},
        ],
    )
    yield get_filename(partial), partial

    seen = get_seen(spec)
    time_ms = spec.compute_time_at_slot_ms(state, group_id.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 500
    result, reason = run_validate_gossip(
        spec,
        seen,
        store,
        state,
        partial,
        group_id=group_id,
        column_index=column_index,
    )
    assert result == "reject"
    assert reason == "number of proofs does not match number of set bits"
    messages.append(
        {
            "block_root": "0x" + group_id.beacon_block_root.hex(),
            "column_index": int(column_index),
            "current_time_ms": int(time_ms),
            "message": get_filename(partial),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_partial_data_column_sidecar__ignore_block_unseen(spec, state):
    """A partial sidecar whose group_id references an unknown block is ignored."""
    yield "topic", "meta", "partial_data_column_sidecar"

    store, signed_anchor, signed_block, partial, group_id, column_index = (
        setup_gloas_partial_sidecar(spec, state)
    )
    group_id.beacon_block_root = spec.Root(b"\xab" * 32)

    yield "state", state
    yield get_filename(signed_anchor), signed_anchor
    yield get_filename(signed_block), signed_block
    yield (
        "blocks",
        "meta",
        [
            {"block": get_filename(signed_anchor)},
            {"block": get_filename(signed_block)},
        ],
    )
    yield get_filename(partial), partial

    seen = get_seen(spec)
    time_ms = spec.compute_time_at_slot_ms(state, group_id.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 500
    result, reason = run_validate_gossip(
        spec,
        seen,
        store,
        state,
        partial,
        group_id=group_id,
        column_index=column_index,
    )
    assert result == "ignore"
    assert reason == "group id's beacon block has not been seen"
    messages.append(
        {
            "block_root": "0x" + group_id.beacon_block_root.hex(),
            "column_index": int(column_index),
            "current_time_ms": int(time_ms),
            "message": get_filename(partial),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_partial_data_column_sidecar__reject_bitmap_length_mismatch(spec, state):
    """A partial sidecar whose bitmap length doesn't match the bid's blob count is rejected."""
    yield "topic", "meta", "partial_data_column_sidecar"

    store, signed_anchor, signed_block, partial, group_id, column_index = (
        setup_gloas_partial_sidecar(spec, state)
    )
    # Pad bitmap, cells, and proofs in lockstep so the earlier count checks
    # pass but the bitmap-vs-bid-commitments check fails.
    partial.cells_present_bitmap = spec.List[spec.boolean, spec.MAX_BLOB_COMMITMENTS_PER_BLOCK](
        *partial.cells_present_bitmap,
        spec.boolean(True),  # noqa: FBT003
    )
    partial.partial_column = spec.List[spec.Cell, spec.MAX_BLOB_COMMITMENTS_PER_BLOCK](
        *partial.partial_column, spec.Cell()
    )
    partial.kzg_proofs = spec.List[spec.KZGProof, spec.MAX_BLOB_COMMITMENTS_PER_BLOCK](
        *partial.kzg_proofs, spec.KZGProof()
    )

    yield "state", state
    yield get_filename(signed_anchor), signed_anchor
    yield get_filename(signed_block), signed_block
    yield (
        "blocks",
        "meta",
        [
            {"block": get_filename(signed_anchor)},
            {"block": get_filename(signed_block)},
        ],
    )
    yield get_filename(partial), partial

    seen = get_seen(spec)
    time_ms = spec.compute_time_at_slot_ms(state, group_id.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 500
    result, reason = run_validate_gossip(
        spec,
        seen,
        store,
        state,
        partial,
        group_id=group_id,
        column_index=column_index,
    )
    assert result == "reject"
    assert reason == "bitmap length does not match the number of bid commitments"
    messages.append(
        {
            "block_root": "0x" + group_id.beacon_block_root.hex(),
            "column_index": int(column_index),
            "current_time_ms": int(time_ms),
            "message": get_filename(partial),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_partial_data_column_sidecar__reject_invalid_kzg_proofs(spec, state):
    """A partial sidecar whose KZG proofs fail verification is rejected."""
    yield "topic", "meta", "partial_data_column_sidecar"

    # Use two blobs so we can swap proofs to produce verifiable-format but
    # incorrect proofs (verify returns False rather than raising).
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    _, _, _, signed_block, sidecars, _ = get_block_with_blob_and_sidecars(spec, state, blob_count=2)
    block_root = signed_block.message.hash_tree_root()
    store.blocks[block_root] = signed_block.message
    store.block_states[block_root] = state.copy()

    sidecar = sidecars[0]
    bitmap = [True, True]
    cells = [sidecar.column[0], sidecar.column[1]]
    # Swap proofs so each cell carries the other cell's proof.
    proofs = [sidecar.kzg_proofs[1], sidecar.kzg_proofs[0]]
    partial = spec.PartialDataColumnSidecar(
        cells_present_bitmap=bitmap,
        partial_column=cells,
        kzg_proofs=proofs,
    )
    group_id = spec.PartialDataColumnGroupID(
        slot=sidecar.slot,
        beacon_block_root=sidecar.beacon_block_root,
    )
    column_index = sidecar.index

    yield "state", state
    yield get_filename(signed_anchor), signed_anchor
    yield get_filename(signed_block), signed_block
    yield (
        "blocks",
        "meta",
        [
            {"block": get_filename(signed_anchor)},
            {"block": get_filename(signed_block)},
        ],
    )
    yield get_filename(partial), partial

    seen = get_seen(spec)
    time_ms = spec.compute_time_at_slot_ms(state, group_id.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 500
    result, reason = run_validate_gossip(
        spec,
        seen,
        store,
        state,
        partial,
        group_id=group_id,
        column_index=column_index,
    )
    assert result == "reject"
    assert reason == "invalid sidecar kzg proofs"
    messages.append(
        {
            "block_root": "0x" + group_id.beacon_block_root.hex(),
            "column_index": int(column_index),
            "current_time_ms": int(time_ms),
            "message": get_filename(partial),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages
