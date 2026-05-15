from frozendict import frozendict

from eth_consensus_specs.test.context import (
    always_bls,
    spec_configured_state_test,
    spec_state_test,
    with_phases,
)
from eth_consensus_specs.test.helpers.blob import (
    get_block_with_blob_and_sidecars,
    get_max_blob_count,
)
from eth_consensus_specs.test.helpers.block import build_empty_block_for_next_slot
from eth_consensus_specs.test.helpers.constants import FULU
from eth_consensus_specs.test.helpers.execution_payload import (
    build_state_with_complete_transition,
)
from eth_consensus_specs.test.helpers.fork_choice import (
    get_genesis_forkchoice_store_and_block,
)
from eth_consensus_specs.test.helpers.gossip import (
    get_filename,
    get_seen,
    run_validate_partial_data_column_sidecar_gossip,
    wrap_genesis_block,
)
from eth_consensus_specs.test.helpers.keys import privkeys
from eth_consensus_specs.test.helpers.state import (
    state_transition_and_sign_block,
    transition_to,
)


def build_signed_block_and_sidecars(spec, state, blob_count=1):
    """
    Build a signed block carrying ``blob_count`` blobs (applying the state
    transition) and return its (signed_block, data_column_sidecars).
    """
    _, _, _, signed_block, sidecars, _ = get_block_with_blob_and_sidecars(
        spec, state, blob_count=blob_count
    )
    return signed_block, list(sidecars)


def setup_store_with_anchor(spec, state):
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    return store, anchor_block


def make_partial_header(spec, sidecar):
    """Build a PartialDataColumnHeader from a DataColumnSidecar."""
    return spec.PartialDataColumnHeader(
        kzg_commitments=sidecar.kzg_commitments,
        signed_block_header=sidecar.signed_block_header,
        kzg_commitments_inclusion_proof=sidecar.kzg_commitments_inclusion_proof,
    )


def make_partial_sidecar(spec, sidecar, blob_indices=None, include_header=True):
    """
    Build a PartialDataColumnSidecar from a DataColumnSidecar.
    ``blob_indices`` controls which blob indices are present (default: all).
    """
    num_blobs = len(sidecar.kzg_commitments)
    if blob_indices is None:
        blob_indices = list(range(num_blobs))

    bitmap = [i in blob_indices for i in range(num_blobs)]
    cells = [sidecar.column[i] for i in blob_indices]
    proofs = [sidecar.kzg_proofs[i] for i in blob_indices]

    header = [make_partial_header(spec, sidecar)] if include_header else []

    return spec.PartialDataColumnSidecar(
        cells_present_bitmap=bitmap,
        partial_column=cells,
        kzg_proofs=proofs,
        header=header,
    )


def block_root_of(spec, sidecar):
    return spec.hash_tree_root(sidecar.signed_block_header.message)


def resign_header(spec, state, header):
    proposer_index = header.signed_block_header.message.proposer_index
    domain = spec.get_domain(
        state,
        spec.DOMAIN_BEACON_PROPOSER,
        spec.compute_epoch_at_slot(header.signed_block_header.message.slot),
    )
    signing_root = spec.compute_signing_root(header.signed_block_header.message, domain)
    header.signed_block_header.signature = spec.bls.Sign(privkeys[proposer_index], signing_root)


@with_phases([FULU])
@spec_state_test
def test_gossip_partial_data_column_sidecar__valid_header_only(spec, state):
    """Test that a header-only partial sidecar passes gossip validation."""
    yield "topic", "meta", "partial_data_column_sidecar"

    state = build_state_with_complete_transition(spec, state)
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = setup_store_with_anchor(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    _, sidecars = build_signed_block_and_sidecars(spec, state, blob_count=1)
    sidecar = sidecars[0]
    partial = make_partial_sidecar(spec, sidecar, blob_indices=[], include_header=True)
    block_root = block_root_of(spec, sidecar)

    yield get_filename(partial), partial

    block_time_ms = spec.compute_time_at_slot_ms(state, sidecar.signed_block_header.message.slot)
    yield "current_time_ms", "meta", int(block_time_ms)

    column_index = sidecar.index
    result, reason = run_validate_partial_data_column_sidecar_gossip(
        spec, seen, store, state, partial, block_root, column_index, block_time_ms + 500
    )
    assert result == "valid"
    assert reason is None

    yield (
        "messages",
        "meta",
        [
            {
                "block_root": "0x" + block_root.hex(),
                "column_index": int(column_index),
                "offset_ms": 500,
                "message": get_filename(partial),
                "expected": "valid",
            }
        ],
    )


@with_phases([FULU])
@spec_configured_state_test(
    {
        "BLOB_SCHEDULE": (frozendict({"EPOCH": 0, "MAX_BLOBS_PER_BLOCK": 12}),),
    }
)
def test_gossip_partial_data_column_sidecar__valid_header_and_cells(spec, state):
    """Test that a partial sidecar carrying both header and cells passes gossip validation."""
    yield "topic", "meta", "partial_data_column_sidecar"

    state = build_state_with_complete_transition(spec, state)
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = setup_store_with_anchor(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    max_blobs = get_max_blob_count(spec, state)
    # Sanity check: the BLOB_SCHEDULE override should be exercising the Fulu
    # code path (`get_blob_parameters`), not the Electra fallback. A client that
    # forgets EIP-7892 and uses MAX_BLOBS_PER_BLOCK_ELECTRA would reject this sidecar.
    assert max_blobs > spec.config.MAX_BLOBS_PER_BLOCK_ELECTRA
    _, sidecars = build_signed_block_and_sidecars(spec, state, blob_count=max_blobs)
    sidecar = sidecars[0]
    partial = make_partial_sidecar(spec, sidecar, include_header=True)
    block_root = block_root_of(spec, sidecar)

    yield get_filename(partial), partial

    block_time_ms = spec.compute_time_at_slot_ms(state, sidecar.signed_block_header.message.slot)
    yield "current_time_ms", "meta", int(block_time_ms)

    column_index = sidecar.index
    result, reason = run_validate_partial_data_column_sidecar_gossip(
        spec, seen, store, state, partial, block_root, column_index, block_time_ms + 500
    )
    assert result == "valid"
    assert reason is None

    yield (
        "messages",
        "meta",
        [
            {
                "block_root": "0x" + block_root.hex(),
                "column_index": int(column_index),
                "offset_ms": 500,
                "message": get_filename(partial),
                "expected": "valid",
            }
        ],
    )


@with_phases([FULU])
@spec_state_test
def test_gossip_partial_data_column_sidecar__valid_cells_only_with_cached_header(spec, state):
    """Test that a cells-only partial sidecar passes when a header was cached previously."""
    yield "topic", "meta", "partial_data_column_sidecar"

    state = build_state_with_complete_transition(spec, state)
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = setup_store_with_anchor(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    _, sidecars = build_signed_block_and_sidecars(spec, state, blob_count=2)
    sidecar = sidecars[0]
    block_root = block_root_of(spec, sidecar)

    # First message: header only, populates the cache.
    header_msg = make_partial_sidecar(spec, sidecar, blob_indices=[], include_header=True)
    # Second message: cells only.
    cells_msg = make_partial_sidecar(spec, sidecar, include_header=False)

    yield get_filename(header_msg), header_msg
    yield get_filename(cells_msg), cells_msg

    block_time_ms = spec.compute_time_at_slot_ms(state, sidecar.signed_block_header.message.slot)
    yield "current_time_ms", "meta", int(block_time_ms)

    column_index = sidecar.index

    messages = []
    result, reason = run_validate_partial_data_column_sidecar_gossip(
        spec, seen, store, state, header_msg, block_root, column_index, block_time_ms + 500
    )
    assert result == "valid"
    messages.append(
        {
            "block_root": "0x" + block_root.hex(),
            "column_index": int(column_index),
            "offset_ms": 500,
            "message": get_filename(header_msg),
            "expected": "valid",
        }
    )

    result, reason = run_validate_partial_data_column_sidecar_gossip(
        spec, seen, store, state, cells_msg, block_root, column_index, block_time_ms + 600
    )
    assert result == "valid"
    assert reason is None
    messages.append(
        {
            "block_root": "0x" + block_root.hex(),
            "column_index": int(column_index),
            "offset_ms": 600,
            "message": get_filename(cells_msg),
            "expected": "valid",
        }
    )

    yield "messages", "meta", messages


@with_phases([FULU])
@spec_state_test
def test_gossip_partial_data_column_sidecar__reject_semantically_empty(spec, state):
    """Test that a partial sidecar with no header and no cells is rejected."""
    yield "topic", "meta", "partial_data_column_sidecar"

    state = build_state_with_complete_transition(spec, state)
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = setup_store_with_anchor(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    _, sidecars = build_signed_block_and_sidecars(spec, state, blob_count=1)
    sidecar = sidecars[0]
    partial = make_partial_sidecar(spec, sidecar, blob_indices=[], include_header=False)
    block_root = block_root_of(spec, sidecar)

    yield get_filename(partial), partial

    block_time_ms = spec.compute_time_at_slot_ms(state, sidecar.signed_block_header.message.slot)
    yield "current_time_ms", "meta", int(block_time_ms)

    column_index = sidecar.index
    result, reason = run_validate_partial_data_column_sidecar_gossip(
        spec, seen, store, state, partial, block_root, column_index, block_time_ms + 500
    )
    assert result == "reject"
    assert reason == "partial message is semantically empty"

    yield (
        "messages",
        "meta",
        [
            {
                "block_root": "0x" + block_root.hex(),
                "column_index": int(column_index),
                "offset_ms": 500,
                "message": get_filename(partial),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_phases([FULU])
@spec_state_test
def test_gossip_partial_data_column_sidecar__reject_cell_count_mismatch(spec, state):
    """Test that a partial sidecar with cell count != set bits is rejected."""
    yield "topic", "meta", "partial_data_column_sidecar"

    state = build_state_with_complete_transition(spec, state)
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = setup_store_with_anchor(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    _, sidecars = build_signed_block_and_sidecars(spec, state, blob_count=2)
    sidecar = sidecars[0]
    partial = make_partial_sidecar(spec, sidecar, include_header=True)
    # Drop a cell so the count no longer matches the bitmap.
    partial.partial_column = list(partial.partial_column)[:-1]
    block_root = block_root_of(spec, sidecar)

    yield get_filename(partial), partial

    block_time_ms = spec.compute_time_at_slot_ms(state, sidecar.signed_block_header.message.slot)
    yield "current_time_ms", "meta", int(block_time_ms)

    column_index = sidecar.index
    result, reason = run_validate_partial_data_column_sidecar_gossip(
        spec, seen, store, state, partial, block_root, column_index, block_time_ms + 500
    )
    assert result == "reject"
    assert reason == "number of cells does not match number of set bits"

    yield (
        "messages",
        "meta",
        [
            {
                "block_root": "0x" + block_root.hex(),
                "column_index": int(column_index),
                "offset_ms": 500,
                "message": get_filename(partial),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_phases([FULU])
@spec_state_test
def test_gossip_partial_data_column_sidecar__reject_proof_count_mismatch(spec, state):
    """Test that a partial sidecar with proof count != set bits is rejected."""
    yield "topic", "meta", "partial_data_column_sidecar"

    state = build_state_with_complete_transition(spec, state)
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = setup_store_with_anchor(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    _, sidecars = build_signed_block_and_sidecars(spec, state, blob_count=2)
    sidecar = sidecars[0]
    partial = make_partial_sidecar(spec, sidecar, include_header=True)
    # Drop a proof so the count no longer matches the bitmap.
    partial.kzg_proofs = list(partial.kzg_proofs)[:-1]
    block_root = block_root_of(spec, sidecar)

    yield get_filename(partial), partial

    block_time_ms = spec.compute_time_at_slot_ms(state, sidecar.signed_block_header.message.slot)
    yield "current_time_ms", "meta", int(block_time_ms)

    column_index = sidecar.index
    result, reason = run_validate_partial_data_column_sidecar_gossip(
        spec, seen, store, state, partial, block_root, column_index, block_time_ms + 500
    )
    assert result == "reject"
    assert reason == "number of proofs does not match number of set bits"

    yield (
        "messages",
        "meta",
        [
            {
                "block_root": "0x" + block_root.hex(),
                "column_index": int(column_index),
                "offset_ms": 500,
                "message": get_filename(partial),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_phases([FULU])
@spec_state_test
def test_gossip_partial_data_column_sidecar__reject_prior_header_differs(spec, state):
    """Test that a header differing from a previously cached one is rejected."""
    yield "topic", "meta", "partial_data_column_sidecar"

    state = build_state_with_complete_transition(spec, state)
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = setup_store_with_anchor(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    _, sidecars = build_signed_block_and_sidecars(spec, state, blob_count=1)
    sidecar = sidecars[0]
    block_root = block_root_of(spec, sidecar)

    good = make_partial_sidecar(spec, sidecar, blob_indices=[], include_header=True)

    # Build a second partial message whose header has a different inclusion
    # proof, with the cache populated by `good` so the equality check fires.
    diverging = make_partial_sidecar(spec, sidecar, blob_indices=[], include_header=True)
    diverging.header[0].kzg_commitments_inclusion_proof = spec.compute_merkle_proof(
        spec.BeaconBlockBody(), 0
    )

    yield get_filename(good), good
    yield get_filename(diverging), diverging

    block_time_ms = spec.compute_time_at_slot_ms(state, sidecar.signed_block_header.message.slot)
    yield "current_time_ms", "meta", int(block_time_ms)

    column_index = sidecar.index

    messages = []
    result, reason = run_validate_partial_data_column_sidecar_gossip(
        spec, seen, store, state, good, block_root, column_index, block_time_ms + 500
    )
    assert result == "valid"
    messages.append(
        {
            "block_root": "0x" + block_root.hex(),
            "column_index": int(column_index),
            "offset_ms": 500,
            "message": get_filename(good),
            "expected": "valid",
        }
    )

    result, reason = run_validate_partial_data_column_sidecar_gossip(
        spec, seen, store, state, diverging, block_root, column_index, block_time_ms + 600
    )
    assert result == "reject"
    assert reason == "header differs from previously validated header"
    messages.append(
        {
            "block_root": "0x" + block_root.hex(),
            "column_index": int(column_index),
            "offset_ms": 600,
            "message": get_filename(diverging),
            "expected": "reject",
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_phases([FULU])
@spec_state_test
def test_gossip_partial_data_column_sidecar__reject_block_root_mismatch(spec, state):
    """Test that a header whose block root differs from the group id is rejected."""
    yield "topic", "meta", "partial_data_column_sidecar"

    state = build_state_with_complete_transition(spec, state)
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = setup_store_with_anchor(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    _, sidecars = build_signed_block_and_sidecars(spec, state, blob_count=1)
    sidecar = sidecars[0]
    partial = make_partial_sidecar(spec, sidecar, blob_indices=[], include_header=True)
    block_root = spec.Root(b"\xab" * 32)

    yield get_filename(partial), partial

    block_time_ms = spec.compute_time_at_slot_ms(state, sidecar.signed_block_header.message.slot)
    yield "current_time_ms", "meta", int(block_time_ms)

    column_index = sidecar.index
    result, reason = run_validate_partial_data_column_sidecar_gossip(
        spec, seen, store, state, partial, block_root, column_index, block_time_ms + 500
    )
    assert result == "reject"
    assert reason == "header's block root does not match partial message group id"

    yield (
        "messages",
        "meta",
        [
            {
                "block_root": "0x" + block_root.hex(),
                "column_index": int(column_index),
                "offset_ms": 500,
                "message": get_filename(partial),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_phases([FULU])
@spec_state_test
def test_gossip_partial_data_column_sidecar__reject_empty_commitments(spec, state):
    """Test that a header with empty kzg_commitments is rejected."""
    yield "topic", "meta", "partial_data_column_sidecar"

    state = build_state_with_complete_transition(spec, state)
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = setup_store_with_anchor(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    _, sidecars = build_signed_block_and_sidecars(spec, state, blob_count=1)
    sidecar = sidecars[0]
    partial = make_partial_sidecar(spec, sidecar, blob_indices=[], include_header=True)
    partial.header[0].kzg_commitments = []
    block_root = block_root_of(spec, sidecar)

    yield get_filename(partial), partial

    block_time_ms = spec.compute_time_at_slot_ms(state, sidecar.signed_block_header.message.slot)
    yield "current_time_ms", "meta", int(block_time_ms)

    column_index = sidecar.index
    result, reason = run_validate_partial_data_column_sidecar_gossip(
        spec, seen, store, state, partial, block_root, column_index, block_time_ms + 500
    )
    assert result == "reject"
    assert reason == "header's kzg_commitments is empty"

    yield (
        "messages",
        "meta",
        [
            {
                "block_root": "0x" + block_root.hex(),
                "column_index": int(column_index),
                "offset_ms": 500,
                "message": get_filename(partial),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_phases([FULU])
@spec_state_test
def test_gossip_partial_data_column_sidecar__ignore_future_slot(spec, state):
    """Test that a header from a future slot is ignored."""
    yield "topic", "meta", "partial_data_column_sidecar"

    state = build_state_with_complete_transition(spec, state)
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = setup_store_with_anchor(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    _, sidecars = build_signed_block_and_sidecars(spec, state, blob_count=1)
    sidecar = sidecars[0]
    partial = make_partial_sidecar(spec, sidecar, blob_indices=[], include_header=True)
    block_root = block_root_of(spec, sidecar)

    yield get_filename(partial), partial

    slot_time_ms = spec.compute_time_at_slot_ms(state, sidecar.signed_block_header.message.slot)
    current_time_ms = slot_time_ms - spec.config.MAXIMUM_GOSSIP_CLOCK_DISPARITY - 1
    yield "current_time_ms", "meta", int(current_time_ms)

    column_index = sidecar.index
    result, reason = run_validate_partial_data_column_sidecar_gossip(
        spec, seen, store, state, partial, block_root, column_index, current_time_ms
    )
    assert result == "ignore"
    assert reason == "header is from a future slot"

    yield (
        "messages",
        "meta",
        [
            {
                "block_root": "0x" + block_root.hex(),
                "column_index": int(column_index),
                "offset_ms": 0,
                "message": get_filename(partial),
                "expected": "ignore",
                "reason": reason,
            }
        ],
    )


@with_phases([FULU])
@spec_state_test
def test_gossip_partial_data_column_sidecar__ignore_not_later_than_finalized_slot(spec, state):
    """Test that a header at the latest finalized slot is ignored."""
    yield "topic", "meta", "partial_data_column_sidecar"

    state = build_state_with_complete_transition(spec, state)
    seen = get_seen(spec)
    store, anchor_block = setup_store_with_anchor(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    transition_to(spec, state, spec.Slot(spec.SLOTS_PER_EPOCH - 1))
    yield "state", state

    _, sidecars = build_signed_block_and_sidecars(spec, state, blob_count=1)
    sidecar = sidecars[0]
    partial = make_partial_sidecar(spec, sidecar, blob_indices=[], include_header=True)
    block_root = block_root_of(spec, sidecar)

    block_header = sidecar.signed_block_header.message
    sidecar_epoch = spec.compute_epoch_at_slot(block_header.slot)
    store.finalized_checkpoint = spec.Checkpoint(
        epoch=sidecar_epoch,
        root=store.finalized_checkpoint.root,
    )
    yield (
        "finalized_checkpoint",
        "meta",
        {"epoch": int(sidecar_epoch), "block": get_filename(signed_anchor)},
    )

    yield get_filename(partial), partial

    block_time_ms = spec.compute_time_at_slot_ms(state, block_header.slot)
    yield "current_time_ms", "meta", int(block_time_ms)

    column_index = sidecar.index
    result, reason = run_validate_partial_data_column_sidecar_gossip(
        spec, seen, store, state, partial, block_root, column_index, block_time_ms + 500
    )
    assert result == "ignore"
    assert reason == "header is not from a slot greater than the latest finalized slot"

    yield (
        "messages",
        "meta",
        [
            {
                "block_root": "0x" + block_root.hex(),
                "column_index": int(column_index),
                "offset_ms": 500,
                "message": get_filename(partial),
                "expected": "ignore",
                "reason": reason,
            }
        ],
    )


@with_phases([FULU])
@spec_state_test
def test_gossip_partial_data_column_sidecar__reject_proposer_index_out_of_range(spec, state):
    """Test that a header with proposer_index out of range is rejected."""
    yield "topic", "meta", "partial_data_column_sidecar"

    state = build_state_with_complete_transition(spec, state)
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = setup_store_with_anchor(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    _, sidecars = build_signed_block_and_sidecars(spec, state, blob_count=1)
    sidecar = sidecars[0]
    partial = make_partial_sidecar(spec, sidecar, blob_indices=[], include_header=True)
    partial.header[0].signed_block_header.message.proposer_index = spec.ValidatorIndex(
        len(state.validators)
    )
    block_root = spec.hash_tree_root(partial.header[0].signed_block_header.message)

    yield get_filename(partial), partial

    block_time_ms = spec.compute_time_at_slot_ms(state, sidecar.signed_block_header.message.slot)
    yield "current_time_ms", "meta", int(block_time_ms)

    column_index = sidecar.index
    result, reason = run_validate_partial_data_column_sidecar_gossip(
        spec, seen, store, state, partial, block_root, column_index, block_time_ms + 500
    )
    assert result == "reject"
    assert reason == "proposer index out of range"

    yield (
        "messages",
        "meta",
        [
            {
                "block_root": "0x" + block_root.hex(),
                "column_index": int(column_index),
                "offset_ms": 500,
                "message": get_filename(partial),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_phases([FULU])
@spec_state_test
@always_bls
def test_gossip_partial_data_column_sidecar__reject_invalid_proposer_signature(spec, state):
    """Test that a header with an invalid proposer signature is rejected."""
    yield "topic", "meta", "partial_data_column_sidecar"

    state = build_state_with_complete_transition(spec, state)
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = setup_store_with_anchor(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    _, sidecars = build_signed_block_and_sidecars(spec, state, blob_count=1)
    sidecar = sidecars[0]
    partial = make_partial_sidecar(spec, sidecar, blob_indices=[], include_header=True)
    partial.header[0].signed_block_header.signature = spec.BLSSignature(b"\x00" * 96)
    block_root = block_root_of(spec, sidecar)

    yield get_filename(partial), partial

    block_time_ms = spec.compute_time_at_slot_ms(state, sidecar.signed_block_header.message.slot)
    yield "current_time_ms", "meta", int(block_time_ms)

    column_index = sidecar.index
    result, reason = run_validate_partial_data_column_sidecar_gossip(
        spec, seen, store, state, partial, block_root, column_index, block_time_ms + 500
    )
    assert result == "reject"
    assert reason == "invalid proposer signature on header"

    yield (
        "messages",
        "meta",
        [
            {
                "block_root": "0x" + block_root.hex(),
                "column_index": int(column_index),
                "offset_ms": 500,
                "message": get_filename(partial),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_phases([FULU])
@spec_state_test
def test_gossip_partial_data_column_sidecar__ignore_parent_not_seen(spec, state):
    """Test that a header whose parent is unknown to the store is ignored."""
    yield "topic", "meta", "partial_data_column_sidecar"

    state = build_state_with_complete_transition(spec, state)
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = setup_store_with_anchor(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    _, sidecars = build_signed_block_and_sidecars(spec, state, blob_count=1)
    sidecar = sidecars[0]
    partial = make_partial_sidecar(spec, sidecar, blob_indices=[], include_header=True)
    partial.header[0].signed_block_header.message.parent_root = b"\x12" * 32
    resign_header(spec, state, partial.header[0])
    block_root = spec.hash_tree_root(partial.header[0].signed_block_header.message)

    yield get_filename(partial), partial

    block_time_ms = spec.compute_time_at_slot_ms(state, sidecar.signed_block_header.message.slot)
    yield "current_time_ms", "meta", int(block_time_ms)

    column_index = sidecar.index
    result, reason = run_validate_partial_data_column_sidecar_gossip(
        spec, seen, store, state, partial, block_root, column_index, block_time_ms + 500
    )
    assert result == "ignore"
    assert reason == "header's parent has not been seen"

    yield (
        "messages",
        "meta",
        [
            {
                "block_root": "0x" + block_root.hex(),
                "column_index": int(column_index),
                "offset_ms": 500,
                "message": get_filename(partial),
                "expected": "ignore",
                "reason": reason,
            }
        ],
    )


@with_phases([FULU])
@spec_state_test
def test_gossip_partial_data_column_sidecar__reject_parent_failed_validation(spec, state):
    """Test that a header whose parent failed validation is rejected."""
    yield "topic", "meta", "partial_data_column_sidecar"

    state = build_state_with_complete_transition(spec, state)
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = setup_store_with_anchor(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    yield get_filename(signed_anchor), signed_anchor

    parent_state = state.copy()
    parent_block = build_empty_block_for_next_slot(spec, parent_state)
    signed_parent = state_transition_and_sign_block(spec, parent_state, parent_block)

    yield get_filename(signed_parent), signed_parent

    store.blocks[signed_parent.message.hash_tree_root()] = signed_parent.message

    yield (
        "blocks",
        "meta",
        [
            {"block": get_filename(signed_anchor)},
            {"block": get_filename(signed_parent), "failed": True},
        ],
    )

    _, sidecars = build_signed_block_and_sidecars(spec, parent_state.copy(), blob_count=1)
    sidecar = sidecars[0]
    partial = make_partial_sidecar(spec, sidecar, blob_indices=[], include_header=True)
    block_root = block_root_of(spec, sidecar)

    yield get_filename(partial), partial

    block_time_ms = spec.compute_time_at_slot_ms(state, sidecar.signed_block_header.message.slot)
    yield "current_time_ms", "meta", int(block_time_ms)

    column_index = sidecar.index
    result, reason = run_validate_partial_data_column_sidecar_gossip(
        spec, seen, store, state, partial, block_root, column_index, block_time_ms + 500
    )
    assert result == "reject"
    assert reason == "header's parent failed validation"

    yield (
        "messages",
        "meta",
        [
            {
                "block_root": "0x" + block_root.hex(),
                "column_index": int(column_index),
                "offset_ms": 500,
                "message": get_filename(partial),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_phases([FULU])
@spec_state_test
def test_gossip_partial_data_column_sidecar__reject_slot_not_higher_than_parent(spec, state):
    """Test that a header whose slot is not greater than its parent's is rejected."""
    yield "topic", "meta", "partial_data_column_sidecar"

    state = build_state_with_complete_transition(spec, state)
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = setup_store_with_anchor(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    yield get_filename(signed_anchor), signed_anchor

    parent_state = state.copy()
    parent_block = build_empty_block_for_next_slot(spec, parent_state)
    signed_parent = state_transition_and_sign_block(spec, parent_state, parent_block)

    yield get_filename(signed_parent), signed_parent
    parent_root = signed_parent.message.hash_tree_root()
    store.blocks[parent_root] = signed_parent.message
    store.block_states[parent_root] = parent_state.copy()
    yield (
        "blocks",
        "meta",
        [
            {"block": get_filename(signed_anchor)},
            {"block": get_filename(signed_parent)},
        ],
    )

    _, sidecars = build_signed_block_and_sidecars(spec, parent_state.copy(), blob_count=1)
    sidecar = sidecars[0]
    partial = make_partial_sidecar(spec, sidecar, blob_indices=[], include_header=True)
    partial.header[0].signed_block_header.message.slot = signed_parent.message.slot
    resign_header(spec, parent_state, partial.header[0])
    block_root = spec.hash_tree_root(partial.header[0].signed_block_header.message)

    yield get_filename(partial), partial

    block_time_ms = spec.compute_time_at_slot_ms(
        state, partial.header[0].signed_block_header.message.slot
    )
    yield "current_time_ms", "meta", int(block_time_ms)

    column_index = sidecar.index
    result, reason = run_validate_partial_data_column_sidecar_gossip(
        spec, seen, store, state, partial, block_root, column_index, block_time_ms + 500
    )
    assert result == "reject"
    assert reason == "header is not from a higher slot than its parent"

    yield (
        "messages",
        "meta",
        [
            {
                "block_root": "0x" + block_root.hex(),
                "column_index": int(column_index),
                "offset_ms": 500,
                "message": get_filename(partial),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_phases([FULU])
@spec_state_test
def test_gossip_partial_data_column_sidecar__reject_non_ancestor_finalized_checkpoint(spec, state):
    """Test that a header is rejected if the finalized checkpoint is not an ancestor."""
    yield "topic", "meta", "partial_data_column_sidecar"

    state = build_state_with_complete_transition(spec, state)
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = setup_store_with_anchor(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    _, sidecars = build_signed_block_and_sidecars(spec, state, blob_count=1)
    sidecar = sidecars[0]
    partial = make_partial_sidecar(spec, sidecar, blob_indices=[], include_header=True)
    block_root = block_root_of(spec, sidecar)

    fake_finalized_root = spec.Root(b"\xab" * 32)
    store.finalized_checkpoint = spec.Checkpoint(
        epoch=spec.Epoch(0),
        root=fake_finalized_root,
    )

    yield "finalized_checkpoint", "meta", {"epoch": 0, "root": "0x" + "ab" * 32}
    yield get_filename(partial), partial

    block_time_ms = spec.compute_time_at_slot_ms(state, sidecar.signed_block_header.message.slot)
    yield "current_time_ms", "meta", int(block_time_ms)

    column_index = sidecar.index
    result, reason = run_validate_partial_data_column_sidecar_gossip(
        spec, seen, store, state, partial, block_root, column_index, block_time_ms + 500
    )
    assert result == "reject"
    assert reason == "finalized checkpoint is not an ancestor of header's block"

    yield (
        "messages",
        "meta",
        [
            {
                "block_root": "0x" + block_root.hex(),
                "column_index": int(column_index),
                "offset_ms": 500,
                "message": get_filename(partial),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_phases([FULU])
@spec_state_test
def test_gossip_partial_data_column_sidecar__reject_invalid_inclusion_proof(spec, state):
    """Test that a header with a broken inclusion proof is rejected."""
    yield "topic", "meta", "partial_data_column_sidecar"

    state = build_state_with_complete_transition(spec, state)
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = setup_store_with_anchor(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    _, sidecars = build_signed_block_and_sidecars(spec, state, blob_count=1)
    sidecar = sidecars[0]
    partial = make_partial_sidecar(spec, sidecar, blob_indices=[], include_header=True)
    partial.header[0].kzg_commitments_inclusion_proof = spec.compute_merkle_proof(
        spec.BeaconBlockBody(), 0
    )
    block_root = block_root_of(spec, sidecar)

    yield get_filename(partial), partial

    block_time_ms = spec.compute_time_at_slot_ms(state, sidecar.signed_block_header.message.slot)
    yield "current_time_ms", "meta", int(block_time_ms)

    column_index = sidecar.index
    result, reason = run_validate_partial_data_column_sidecar_gossip(
        spec, seen, store, state, partial, block_root, column_index, block_time_ms + 500
    )
    assert result == "reject"
    assert reason == "invalid header inclusion proof"

    yield (
        "messages",
        "meta",
        [
            {
                "block_root": "0x" + block_root.hex(),
                "column_index": int(column_index),
                "offset_ms": 500,
                "message": get_filename(partial),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_phases([FULU])
@spec_state_test
def test_gossip_partial_data_column_sidecar__reject_wrong_proposer_index(spec, state):
    """Test that a header with the wrong proposer_index is rejected."""
    yield "topic", "meta", "partial_data_column_sidecar"

    state = build_state_with_complete_transition(spec, state)
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = setup_store_with_anchor(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    _, sidecars = build_signed_block_and_sidecars(spec, state, blob_count=1)
    sidecar = sidecars[0]
    partial = make_partial_sidecar(spec, sidecar, blob_indices=[], include_header=True)

    correct_proposer = partial.header[0].signed_block_header.message.proposer_index
    wrong_proposer = spec.ValidatorIndex((int(correct_proposer) + 1) % len(state.validators))
    partial.header[0].signed_block_header.message.proposer_index = wrong_proposer
    resign_header(spec, state, partial.header[0])
    block_root = spec.hash_tree_root(partial.header[0].signed_block_header.message)

    yield get_filename(partial), partial

    block_time_ms = spec.compute_time_at_slot_ms(state, sidecar.signed_block_header.message.slot)
    yield "current_time_ms", "meta", int(block_time_ms)

    column_index = sidecar.index
    result, reason = run_validate_partial_data_column_sidecar_gossip(
        spec, seen, store, state, partial, block_root, column_index, block_time_ms + 500
    )
    assert result == "reject"
    assert reason == "header proposer_index does not match expected proposer"

    yield (
        "messages",
        "meta",
        [
            {
                "block_root": "0x" + block_root.hex(),
                "column_index": int(column_index),
                "offset_ms": 500,
                "message": get_filename(partial),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_phases([FULU])
@spec_state_test
def test_gossip_partial_data_column_sidecar__ignore_cells_without_cached_header(spec, state):
    """Test that a cells-only partial sidecar is ignored when no header is cached."""
    yield "topic", "meta", "partial_data_column_sidecar"

    state = build_state_with_complete_transition(spec, state)
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = setup_store_with_anchor(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    _, sidecars = build_signed_block_and_sidecars(spec, state, blob_count=1)
    sidecar = sidecars[0]
    partial = make_partial_sidecar(spec, sidecar, include_header=False)
    block_root = block_root_of(spec, sidecar)

    yield get_filename(partial), partial

    block_time_ms = spec.compute_time_at_slot_ms(state, sidecar.signed_block_header.message.slot)
    yield "current_time_ms", "meta", int(block_time_ms)

    column_index = sidecar.index
    result, reason = run_validate_partial_data_column_sidecar_gossip(
        spec, seen, store, state, partial, block_root, column_index, block_time_ms + 500
    )
    assert result == "ignore"
    assert reason == "valid corresponding header has not been seen"

    yield (
        "messages",
        "meta",
        [
            {
                "block_root": "0x" + block_root.hex(),
                "column_index": int(column_index),
                "offset_ms": 500,
                "message": get_filename(partial),
                "expected": "ignore",
                "reason": reason,
            }
        ],
    )


@with_phases([FULU])
@spec_state_test
def test_gossip_partial_data_column_sidecar__ignore_cells_with_cached_header_future_slot(
    spec, state
):
    """Test that a cached-header cells-only sidecar is ignored if it is from a future slot."""
    yield "topic", "meta", "partial_data_column_sidecar"

    state = build_state_with_complete_transition(spec, state)
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = setup_store_with_anchor(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    _, sidecars = build_signed_block_and_sidecars(spec, state, blob_count=1)
    sidecar = sidecars[0]
    block_root = block_root_of(spec, sidecar)

    header_msg = make_partial_sidecar(spec, sidecar, blob_indices=[], include_header=True)
    cells_msg = make_partial_sidecar(spec, sidecar, include_header=False)

    yield get_filename(header_msg), header_msg
    yield get_filename(cells_msg), cells_msg

    slot_time_ms = spec.compute_time_at_slot_ms(state, sidecar.signed_block_header.message.slot)
    current_time_ms = slot_time_ms - spec.config.MAXIMUM_GOSSIP_CLOCK_DISPARITY - 1
    yield "current_time_ms", "meta", int(current_time_ms)

    column_index = sidecar.index

    result, reason = run_validate_partial_data_column_sidecar_gossip(
        spec, seen, store, state, header_msg, block_root, column_index, current_time_ms + 1
    )
    assert result == "valid"
    assert reason is None

    result, reason = run_validate_partial_data_column_sidecar_gossip(
        spec, seen, store, state, cells_msg, block_root, column_index, current_time_ms
    )
    assert result == "ignore"
    assert reason == "corresponding header is from a future slot"

    yield (
        "messages",
        "meta",
        [
            {
                "block_root": "0x" + block_root.hex(),
                "column_index": int(column_index),
                "offset_ms": 1,
                "message": get_filename(header_msg),
                "expected": "valid",
            },
            {
                "block_root": "0x" + block_root.hex(),
                "column_index": int(column_index),
                "offset_ms": 0,
                "message": get_filename(cells_msg),
                "expected": "ignore",
                "reason": reason,
            },
        ],
    )


@with_phases([FULU])
@spec_state_test
def test_gossip_partial_data_column_sidecar__ignore_cells_with_cached_header_not_later_than_finalized_slot(  # noqa: E501
    spec, state
):
    """Test that a cached-header cells-only sidecar is ignored once finalization advances."""
    yield "topic", "meta", "partial_data_column_sidecar"

    state = build_state_with_complete_transition(spec, state)
    seen = get_seen(spec)
    store, anchor_block = setup_store_with_anchor(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    transition_to(spec, state, spec.Slot(spec.SLOTS_PER_EPOCH - 1))
    yield "state", state

    _, sidecars = build_signed_block_and_sidecars(spec, state, blob_count=1)
    sidecar = sidecars[0]
    block_root = block_root_of(spec, sidecar)

    header = make_partial_header(spec, sidecar)
    cells_msg = make_partial_sidecar(spec, sidecar, include_header=False)

    yield get_filename(header), header
    yield get_filename(cells_msg), cells_msg

    block_header = sidecar.signed_block_header.message
    sidecar_epoch = spec.compute_epoch_at_slot(block_header.slot)
    block_time_ms = spec.compute_time_at_slot_ms(state, block_header.slot)
    yield "current_time_ms", "meta", int(block_time_ms)

    seen.partial_data_column_headers[block_root] = header

    yield (
        "seen_partial_data_column_headers",
        "meta",
        [
            {
                "block_root": "0x" + block_root.hex(),
                "header": get_filename(header),
            }
        ],
    )

    store.finalized_checkpoint = spec.Checkpoint(
        epoch=sidecar_epoch,
        root=store.finalized_checkpoint.root,
    )

    yield (
        "finalized_checkpoint",
        "meta",
        {"epoch": int(sidecar_epoch), "block": get_filename(signed_anchor)},
    )

    column_index = sidecar.index
    result, reason = run_validate_partial_data_column_sidecar_gossip(
        spec, seen, store, state, cells_msg, block_root, column_index, block_time_ms + 500
    )
    assert result == "ignore"
    assert (
        reason == "corresponding header is not from a slot greater than the latest finalized slot"
    )

    yield (
        "messages",
        "meta",
        [
            {
                "block_root": "0x" + block_root.hex(),
                "column_index": int(column_index),
                "offset_ms": 500,
                "message": get_filename(cells_msg),
                "expected": "ignore",
                "reason": reason,
            },
        ],
    )


@with_phases([FULU])
@spec_state_test
def test_gossip_partial_data_column_sidecar__reject_bitmap_length_mismatch(spec, state):
    """
    Test that a cells-bearing partial sidecar whose bitmap length does not match
    the corresponding header's commitment count is rejected.
    """
    yield "topic", "meta", "partial_data_column_sidecar"

    state = build_state_with_complete_transition(spec, state)
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = setup_store_with_anchor(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    _, sidecars = build_signed_block_and_sidecars(spec, state, blob_count=2)
    sidecar = sidecars[0]
    block_root = block_root_of(spec, sidecar)

    # Seed the cache with a valid header for `block_root`.
    header_msg = make_partial_sidecar(spec, sidecar, blob_indices=[], include_header=True)
    cells_msg = make_partial_sidecar(spec, sidecar, blob_indices=[0], include_header=False)
    # Stretch the bitmap so its length exceeds the corresponding header's commitments.
    Bitlist = type(cells_msg.cells_present_bitmap)
    cells_msg.cells_present_bitmap = Bitlist(list(cells_msg.cells_present_bitmap) + [False, False])

    yield get_filename(header_msg), header_msg
    yield get_filename(cells_msg), cells_msg

    block_time_ms = spec.compute_time_at_slot_ms(state, sidecar.signed_block_header.message.slot)
    yield "current_time_ms", "meta", int(block_time_ms)

    column_index = sidecar.index

    messages = []
    result, reason = run_validate_partial_data_column_sidecar_gossip(
        spec, seen, store, state, header_msg, block_root, column_index, block_time_ms + 500
    )
    assert result == "valid"
    messages.append(
        {
            "block_root": "0x" + block_root.hex(),
            "column_index": int(column_index),
            "offset_ms": 500,
            "message": get_filename(header_msg),
            "expected": "valid",
        }
    )

    result, reason = run_validate_partial_data_column_sidecar_gossip(
        spec, seen, store, state, cells_msg, block_root, column_index, block_time_ms + 600
    )
    assert result == "reject"
    assert reason == "bitmap length does not match commitments length"
    messages.append(
        {
            "block_root": "0x" + block_root.hex(),
            "column_index": int(column_index),
            "offset_ms": 600,
            "message": get_filename(cells_msg),
            "expected": "reject",
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_phases([FULU])
@spec_state_test
def test_gossip_partial_data_column_sidecar__reject_invalid_kzg_proofs(spec, state):
    """Test that cells with invalid KZG proofs are rejected."""
    yield "topic", "meta", "partial_data_column_sidecar"

    state = build_state_with_complete_transition(spec, state)
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = setup_store_with_anchor(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    _, sidecars = build_signed_block_and_sidecars(spec, state, blob_count=1)
    sidecar = sidecars[0]
    partial = make_partial_sidecar(spec, sidecar, include_header=True)
    # Corrupt every KZG proof to the point at infinity, which won't verify
    # against the real commitments.
    bad_proof = spec.KZGProof(b"\xc0" + b"\x00" * 47)
    partial.kzg_proofs = [bad_proof for _ in partial.kzg_proofs]
    block_root = block_root_of(spec, sidecar)

    yield get_filename(partial), partial

    block_time_ms = spec.compute_time_at_slot_ms(state, sidecar.signed_block_header.message.slot)
    yield "current_time_ms", "meta", int(block_time_ms)

    column_index = sidecar.index
    result, reason = run_validate_partial_data_column_sidecar_gossip(
        spec, seen, store, state, partial, block_root, column_index, block_time_ms + 500
    )
    assert result == "reject"
    assert reason == "invalid sidecar kzg proofs"

    yield (
        "messages",
        "meta",
        [
            {
                "block_root": "0x" + block_root.hex(),
                "column_index": int(column_index),
                "offset_ms": 500,
                "message": get_filename(partial),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )
