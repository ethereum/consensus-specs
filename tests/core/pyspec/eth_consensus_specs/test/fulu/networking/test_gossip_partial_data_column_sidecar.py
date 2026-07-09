from frozendict import frozendict

from eth_consensus_specs.test.context import (
    always_bls,
    spec_configured_state_test,
    spec_state_test,
    with_all_phases_from_to,
    with_fulu_and_later,
)
from eth_consensus_specs.test.helpers.blob import (
    get_block_with_blob_and_sidecars,
    get_max_blob_count,
    make_partial_data_column_group_id,
    make_partial_header,
    make_partial_sidecar,
)
from eth_consensus_specs.test.helpers.block import build_empty_block_for_next_slot
from eth_consensus_specs.test.helpers.constants import FULU, GLOAS
from eth_consensus_specs.test.helpers.execution_payload import (
    build_state_with_complete_transition,
)
from eth_consensus_specs.test.helpers.fork_choice import (
    get_genesis_forkchoice_store_and_block,
)
from eth_consensus_specs.test.helpers.forks import is_post_gloas
from eth_consensus_specs.test.helpers.gossip import (
    get_filename,
    get_seen,
    run_validate_gossip,
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


def resign_header(spec, state, header):
    proposer_index = header.signed_block_header.message.proposer_index
    domain = spec.get_domain(
        state,
        spec.DOMAIN_BEACON_PROPOSER,
        spec.compute_epoch_at_slot(header.signed_block_header.message.slot),
    )
    signing_root = spec.compute_signing_root(header.signed_block_header.message, domain)
    header.signed_block_header.signature = spec.bls.Sign(privkeys[proposer_index], signing_root)


@with_all_phases_from_to(FULU, GLOAS)
@spec_state_test
def test_gossip_partial_data_column_sidecar__valid_header_only(spec, state):
    """Test that a header-only partial sidecar passes gossip validation."""
    yield "topic", "meta", "partial_data_column_sidecar"

    state = build_state_with_complete_transition(spec, state)
    anchor_state = state.copy()
    yield "state", anchor_state

    seen = get_seen(spec)
    store, anchor_block = setup_store_with_anchor(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    _, sidecars = build_signed_block_and_sidecars(spec, state, blob_count=1)
    sidecar = sidecars[0]
    partial = make_partial_sidecar(spec, sidecar, blob_indices=[], include_header=True)
    group_id = make_partial_data_column_group_id(spec, sidecar)
    yield get_filename(group_id), group_id

    yield get_filename(partial), partial

    block_time_ms = spec.compute_time_at_slot_ms(state, sidecar.signed_block_header.message.slot)
    yield "current_time_ms", "meta", int(block_time_ms)

    column_index = sidecar.index
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        sidecar=partial,
        current_time_ms=block_time_ms + 500,
        group_id=group_id,
        column_index=column_index,
    )
    assert result == "valid"
    assert reason is None

    yield (
        "messages",
        "meta",
        [
            {
                "group_id": get_filename(group_id),
                "column_index": int(column_index),
                "offset_ms": 500,
                "message": get_filename(partial),
                "expected": "valid",
            }
        ],
    )


@with_all_phases_from_to(FULU, GLOAS)
@spec_configured_state_test(
    {
        "BLOB_SCHEDULE": (frozendict({"EPOCH": 0, "MAX_BLOBS_PER_BLOCK": 12}),),
    },
    activate_at_genesis=True,
)
def test_gossip_partial_data_column_sidecar__valid_header_and_cells(spec, state):
    """Test that a partial sidecar carrying both header and cells passes gossip validation."""
    yield "topic", "meta", "partial_data_column_sidecar"

    state = build_state_with_complete_transition(spec, state)
    anchor_state = state.copy()
    yield "state", anchor_state

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
    group_id = make_partial_data_column_group_id(spec, sidecar)
    yield get_filename(group_id), group_id

    yield get_filename(partial), partial

    block_time_ms = spec.compute_time_at_slot_ms(state, sidecar.signed_block_header.message.slot)
    yield "current_time_ms", "meta", int(block_time_ms)

    column_index = sidecar.index
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        sidecar=partial,
        current_time_ms=block_time_ms + 500,
        group_id=group_id,
        column_index=column_index,
    )
    assert result == "valid"
    assert reason is None

    yield (
        "messages",
        "meta",
        [
            {
                "group_id": get_filename(group_id),
                "column_index": int(column_index),
                "offset_ms": 500,
                "message": get_filename(partial),
                "expected": "valid",
            }
        ],
    )


@with_all_phases_from_to(FULU, GLOAS)
@spec_state_test
def test_gossip_partial_data_column_sidecar__valid_cells_only_with_cached_header(spec, state):
    """Test that a cells-only partial sidecar passes when a header was cached previously."""
    yield "topic", "meta", "partial_data_column_sidecar"

    state = build_state_with_complete_transition(spec, state)
    anchor_state = state.copy()
    yield "state", anchor_state

    seen = get_seen(spec)
    store, anchor_block = setup_store_with_anchor(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    _, sidecars = build_signed_block_and_sidecars(spec, state, blob_count=2)
    sidecar = sidecars[0]
    group_id = make_partial_data_column_group_id(spec, sidecar)
    yield get_filename(group_id), group_id

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
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        sidecar=header_msg,
        current_time_ms=block_time_ms + 500,
        group_id=group_id,
        column_index=column_index,
    )
    assert result == "valid"
    messages.append(
        {
            "group_id": get_filename(group_id),
            "column_index": int(column_index),
            "offset_ms": 500,
            "message": get_filename(header_msg),
            "expected": "valid",
        }
    )

    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        sidecar=cells_msg,
        current_time_ms=block_time_ms + 600,
        group_id=group_id,
        column_index=column_index,
    )
    assert result == "valid"
    assert reason is None
    messages.append(
        {
            "group_id": get_filename(group_id),
            "column_index": int(column_index),
            "offset_ms": 600,
            "message": get_filename(cells_msg),
            "expected": "valid",
        }
    )

    yield "messages", "meta", messages


@with_fulu_and_later
@spec_state_test
def test_gossip_partial_data_column_sidecar__reject_empty(spec, state):
    """A partial sidecar with no header and no cells is rejected as semantically empty."""
    yield "topic", "meta", "partial_data_column_sidecar"

    if not is_post_gloas(spec):
        state = build_state_with_complete_transition(spec, state)
    anchor_state = state.copy()
    yield "state", anchor_state

    store, anchor_block = setup_store_with_anchor(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    signed_block, sidecars = build_signed_block_and_sidecars(spec, state, blob_count=1)
    sidecar = sidecars[0]
    column_index = sidecar.index

    group_id = make_partial_data_column_group_id(spec, sidecar)
    yield get_filename(group_id), group_id

    partial = make_partial_sidecar(spec, sidecar, blob_indices=[], include_header=False)
    yield get_filename(partial), partial

    yield get_filename(signed_anchor), signed_anchor
    blocks_meta = [{"block": get_filename(signed_anchor)}]
    if is_post_gloas(spec):
        store.blocks[sidecar.beacon_block_root] = signed_block.message
        store.block_states[sidecar.beacon_block_root] = state.copy()
        yield get_filename(signed_block), signed_block
        blocks_meta.append({"block": get_filename(signed_block)})
    yield "blocks", "meta", blocks_meta

    block_time_ms = spec.compute_time_at_slot_ms(state, signed_block.message.slot)
    yield "current_time_ms", "meta", int(block_time_ms)

    kwargs = {}
    if not is_post_gloas(spec):
        kwargs["seen"] = get_seen(spec)
        kwargs["state"] = state
        kwargs["current_time_ms"] = block_time_ms + 500
    result, reason = run_validate_gossip(
        spec,
        store=store,
        sidecar=partial,
        group_id=group_id,
        column_index=column_index,
        **kwargs,
    )
    assert result == "reject"
    assert reason == "partial message is semantically empty"

    yield (
        "messages",
        "meta",
        [
            {
                "group_id": get_filename(group_id),
                "column_index": int(column_index),
                "offset_ms": 500,
                "message": get_filename(partial),
                "expected": result,
                "reason": reason,
            }
        ],
    )


@with_fulu_and_later
@spec_state_test
def test_gossip_partial_data_column_sidecar__reject_cell_count_mismatch(spec, state):
    """A partial sidecar whose cell count does not match the set bits is rejected."""
    yield "topic", "meta", "partial_data_column_sidecar"

    if not is_post_gloas(spec):
        state = build_state_with_complete_transition(spec, state)
    anchor_state = state.copy()
    yield "state", anchor_state

    store, anchor_block = setup_store_with_anchor(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    signed_block, sidecars = build_signed_block_and_sidecars(spec, state, blob_count=1)
    sidecar = sidecars[0]
    column_index = sidecar.index

    group_id = make_partial_data_column_group_id(spec, sidecar)
    yield get_filename(group_id), group_id

    # Append an extra cell so the count no longer matches the set bits.
    partial = make_partial_sidecar(spec, sidecar)
    cells_type = type(partial.partial_column)
    partial.partial_column = cells_type(list(partial.partial_column) + [spec.Cell()])
    yield get_filename(partial), partial

    yield get_filename(signed_anchor), signed_anchor
    blocks_meta = [{"block": get_filename(signed_anchor)}]
    if is_post_gloas(spec):
        store.blocks[sidecar.beacon_block_root] = signed_block.message
        store.block_states[sidecar.beacon_block_root] = state.copy()
        yield get_filename(signed_block), signed_block
        blocks_meta.append({"block": get_filename(signed_block)})
    yield "blocks", "meta", blocks_meta

    block_time_ms = spec.compute_time_at_slot_ms(state, signed_block.message.slot)
    yield "current_time_ms", "meta", int(block_time_ms)

    kwargs = {}
    if not is_post_gloas(spec):
        kwargs["seen"] = get_seen(spec)
        kwargs["state"] = state
        kwargs["current_time_ms"] = block_time_ms + 500
    result, reason = run_validate_gossip(
        spec,
        store=store,
        sidecar=partial,
        group_id=group_id,
        column_index=column_index,
        **kwargs,
    )
    assert result == "reject"
    assert reason == "number of cells does not match number of set bits"

    yield (
        "messages",
        "meta",
        [
            {
                "group_id": get_filename(group_id),
                "column_index": int(column_index),
                "offset_ms": 500,
                "message": get_filename(partial),
                "expected": result,
                "reason": reason,
            }
        ],
    )


@with_fulu_and_later
@spec_state_test
def test_gossip_partial_data_column_sidecar__reject_proof_count_mismatch(spec, state):
    """A partial sidecar whose proof count does not match the set bits is rejected."""
    yield "topic", "meta", "partial_data_column_sidecar"

    if not is_post_gloas(spec):
        state = build_state_with_complete_transition(spec, state)
    anchor_state = state.copy()
    yield "state", anchor_state

    store, anchor_block = setup_store_with_anchor(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    signed_block, sidecars = build_signed_block_and_sidecars(spec, state, blob_count=1)
    sidecar = sidecars[0]
    column_index = sidecar.index

    group_id = make_partial_data_column_group_id(spec, sidecar)
    yield get_filename(group_id), group_id

    # Append an extra proof so the count no longer matches the set bits.
    partial = make_partial_sidecar(spec, sidecar)
    proofs_type = type(partial.kzg_proofs)
    partial.kzg_proofs = proofs_type(list(partial.kzg_proofs) + [spec.KZGProof()])
    yield get_filename(partial), partial

    yield get_filename(signed_anchor), signed_anchor
    blocks_meta = [{"block": get_filename(signed_anchor)}]
    if is_post_gloas(spec):
        store.blocks[sidecar.beacon_block_root] = signed_block.message
        store.block_states[sidecar.beacon_block_root] = state.copy()
        yield get_filename(signed_block), signed_block
        blocks_meta.append({"block": get_filename(signed_block)})
    yield "blocks", "meta", blocks_meta

    block_time_ms = spec.compute_time_at_slot_ms(state, signed_block.message.slot)
    yield "current_time_ms", "meta", int(block_time_ms)

    kwargs = {}
    if not is_post_gloas(spec):
        kwargs["seen"] = get_seen(spec)
        kwargs["state"] = state
        kwargs["current_time_ms"] = block_time_ms + 500
    result, reason = run_validate_gossip(
        spec,
        store=store,
        sidecar=partial,
        group_id=group_id,
        column_index=column_index,
        **kwargs,
    )
    assert result == "reject"
    assert reason == "number of proofs does not match number of set bits"

    yield (
        "messages",
        "meta",
        [
            {
                "group_id": get_filename(group_id),
                "column_index": int(column_index),
                "offset_ms": 500,
                "message": get_filename(partial),
                "expected": result,
                "reason": reason,
            }
        ],
    )


@with_all_phases_from_to(FULU, GLOAS)
@spec_state_test
def test_gossip_partial_data_column_sidecar__reject_prior_header_differs(spec, state):
    """Test that a header differing from a previously cached one is rejected."""
    yield "topic", "meta", "partial_data_column_sidecar"

    state = build_state_with_complete_transition(spec, state)
    anchor_state = state.copy()
    yield "state", anchor_state

    seen = get_seen(spec)
    store, anchor_block = setup_store_with_anchor(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    _, sidecars = build_signed_block_and_sidecars(spec, state, blob_count=1)
    sidecar = sidecars[0]
    group_id = make_partial_data_column_group_id(spec, sidecar)
    yield get_filename(group_id), group_id

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
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        sidecar=good,
        current_time_ms=block_time_ms + 500,
        group_id=group_id,
        column_index=column_index,
    )
    assert result == "valid"
    messages.append(
        {
            "group_id": get_filename(group_id),
            "column_index": int(column_index),
            "offset_ms": 500,
            "message": get_filename(good),
            "expected": "valid",
        }
    )

    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        sidecar=diverging,
        current_time_ms=block_time_ms + 600,
        group_id=group_id,
        column_index=column_index,
    )
    assert result == "reject"
    assert reason == "header differs from previously validated header"
    messages.append(
        {
            "group_id": get_filename(group_id),
            "column_index": int(column_index),
            "offset_ms": 600,
            "message": get_filename(diverging),
            "expected": "reject",
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_all_phases_from_to(FULU, GLOAS)
@spec_state_test
def test_gossip_partial_data_column_sidecar__reject_block_root_mismatch(spec, state):
    """Test that a header whose block root differs from the group id is rejected."""
    yield "topic", "meta", "partial_data_column_sidecar"

    state = build_state_with_complete_transition(spec, state)
    anchor_state = state.copy()
    yield "state", anchor_state

    seen = get_seen(spec)
    store, anchor_block = setup_store_with_anchor(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    _, sidecars = build_signed_block_and_sidecars(spec, state, blob_count=1)
    sidecar = sidecars[0]
    partial = make_partial_sidecar(spec, sidecar, blob_indices=[], include_header=True)
    block_root = spec.Root(b"\xab" * 32)
    group_id = spec.PartialDataColumnGroupID(beacon_block_root=block_root)
    yield get_filename(group_id), group_id

    yield get_filename(partial), partial

    block_time_ms = spec.compute_time_at_slot_ms(state, sidecar.signed_block_header.message.slot)
    yield "current_time_ms", "meta", int(block_time_ms)

    column_index = sidecar.index
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        sidecar=partial,
        current_time_ms=block_time_ms + 500,
        group_id=group_id,
        column_index=column_index,
    )
    assert result == "reject"
    assert reason == "header's block root does not match group id's block root"

    yield (
        "messages",
        "meta",
        [
            {
                "group_id": get_filename(group_id),
                "column_index": int(column_index),
                "offset_ms": 500,
                "message": get_filename(partial),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_all_phases_from_to(FULU, GLOAS)
@spec_state_test
def test_gossip_partial_data_column_sidecar__reject_empty_commitments(spec, state):
    """Test that a header with empty kzg_commitments is rejected."""
    yield "topic", "meta", "partial_data_column_sidecar"

    state = build_state_with_complete_transition(spec, state)
    anchor_state = state.copy()
    yield "state", anchor_state

    seen = get_seen(spec)
    store, anchor_block = setup_store_with_anchor(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    _, sidecars = build_signed_block_and_sidecars(spec, state, blob_count=1)
    sidecar = sidecars[0]
    partial = make_partial_sidecar(spec, sidecar, blob_indices=[], include_header=True)
    partial.header[0].kzg_commitments = []
    group_id = make_partial_data_column_group_id(spec, sidecar)
    yield get_filename(group_id), group_id

    yield get_filename(partial), partial

    block_time_ms = spec.compute_time_at_slot_ms(state, sidecar.signed_block_header.message.slot)
    yield "current_time_ms", "meta", int(block_time_ms)

    column_index = sidecar.index
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        sidecar=partial,
        current_time_ms=block_time_ms + 500,
        group_id=group_id,
        column_index=column_index,
    )
    assert result == "reject"
    assert reason == "header's kzg_commitments is empty"

    yield (
        "messages",
        "meta",
        [
            {
                "group_id": get_filename(group_id),
                "column_index": int(column_index),
                "offset_ms": 500,
                "message": get_filename(partial),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_all_phases_from_to(FULU, GLOAS)
@spec_state_test
def test_gossip_partial_data_column_sidecar__ignore_future_slot(spec, state):
    """Test that a header from a future slot is ignored."""
    yield "topic", "meta", "partial_data_column_sidecar"

    state = build_state_with_complete_transition(spec, state)
    anchor_state = state.copy()
    yield "state", anchor_state

    seen = get_seen(spec)
    store, anchor_block = setup_store_with_anchor(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    _, sidecars = build_signed_block_and_sidecars(spec, state, blob_count=1)
    sidecar = sidecars[0]
    partial = make_partial_sidecar(spec, sidecar, blob_indices=[], include_header=True)
    group_id = make_partial_data_column_group_id(spec, sidecar)
    yield get_filename(group_id), group_id

    yield get_filename(partial), partial

    slot_time_ms = spec.compute_time_at_slot_ms(state, sidecar.signed_block_header.message.slot)
    current_time_ms = slot_time_ms - spec.config.MAXIMUM_GOSSIP_CLOCK_DISPARITY - 1
    yield "current_time_ms", "meta", int(current_time_ms)

    column_index = sidecar.index
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        sidecar=partial,
        current_time_ms=current_time_ms,
        group_id=group_id,
        column_index=column_index,
    )
    assert result == "ignore"
    assert reason == "header is from a future slot"

    yield (
        "messages",
        "meta",
        [
            {
                "group_id": get_filename(group_id),
                "column_index": int(column_index),
                "offset_ms": 0,
                "message": get_filename(partial),
                "expected": "ignore",
                "reason": reason,
            }
        ],
    )


@with_all_phases_from_to(FULU, GLOAS)
@spec_state_test
def test_gossip_partial_data_column_sidecar__ignore_not_later_than_finalized_slot(spec, state):
    """Test that a header at the latest finalized slot is ignored."""
    yield "topic", "meta", "partial_data_column_sidecar"

    state = build_state_with_complete_transition(spec, state)
    anchor_state = state.copy()
    seen = get_seen(spec)
    store, anchor_block = setup_store_with_anchor(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    transition_to(spec, state, spec.Slot(spec.SLOTS_PER_EPOCH - 1))
    yield "state", anchor_state

    _, sidecars = build_signed_block_and_sidecars(spec, state, blob_count=1)
    sidecar = sidecars[0]
    partial = make_partial_sidecar(spec, sidecar, blob_indices=[], include_header=True)
    group_id = make_partial_data_column_group_id(spec, sidecar)
    yield get_filename(group_id), group_id

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
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        sidecar=partial,
        current_time_ms=block_time_ms + 500,
        group_id=group_id,
        column_index=column_index,
    )
    assert result == "ignore"
    assert reason == "header is not from a slot greater than the latest finalized slot"

    yield (
        "messages",
        "meta",
        [
            {
                "group_id": get_filename(group_id),
                "column_index": int(column_index),
                "offset_ms": 500,
                "message": get_filename(partial),
                "expected": "ignore",
                "reason": reason,
            }
        ],
    )


@with_all_phases_from_to(FULU, GLOAS)
@spec_state_test
def test_gossip_partial_data_column_sidecar__reject_proposer_index_out_of_range(spec, state):
    """Test that a header with proposer_index out of range is rejected."""
    yield "topic", "meta", "partial_data_column_sidecar"

    state = build_state_with_complete_transition(spec, state)
    anchor_state = state.copy()
    yield "state", anchor_state

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
    group_id = spec.PartialDataColumnGroupID(beacon_block_root=block_root)
    yield get_filename(group_id), group_id

    yield get_filename(partial), partial

    block_time_ms = spec.compute_time_at_slot_ms(state, sidecar.signed_block_header.message.slot)
    yield "current_time_ms", "meta", int(block_time_ms)

    column_index = sidecar.index
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        sidecar=partial,
        current_time_ms=block_time_ms + 500,
        group_id=group_id,
        column_index=column_index,
    )
    assert result == "reject"
    assert reason == "proposer index out of range"

    yield (
        "messages",
        "meta",
        [
            {
                "group_id": get_filename(group_id),
                "column_index": int(column_index),
                "offset_ms": 500,
                "message": get_filename(partial),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_all_phases_from_to(FULU, GLOAS)
@spec_state_test
@always_bls
def test_gossip_partial_data_column_sidecar__reject_invalid_proposer_signature(spec, state):
    """Test that a header with an invalid proposer signature is rejected."""
    yield "topic", "meta", "partial_data_column_sidecar"

    state = build_state_with_complete_transition(spec, state)
    anchor_state = state.copy()
    yield "state", anchor_state

    seen = get_seen(spec)
    store, anchor_block = setup_store_with_anchor(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    _, sidecars = build_signed_block_and_sidecars(spec, state, blob_count=1)
    sidecar = sidecars[0]
    partial = make_partial_sidecar(spec, sidecar, blob_indices=[], include_header=True)
    partial.header[0].signed_block_header.signature = spec.BLSSignature(b"\x00" * 96)
    group_id = make_partial_data_column_group_id(spec, sidecar)
    yield get_filename(group_id), group_id

    yield get_filename(partial), partial

    block_time_ms = spec.compute_time_at_slot_ms(state, sidecar.signed_block_header.message.slot)
    yield "current_time_ms", "meta", int(block_time_ms)

    column_index = sidecar.index
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        sidecar=partial,
        current_time_ms=block_time_ms + 500,
        group_id=group_id,
        column_index=column_index,
    )
    assert result == "reject"
    assert reason == "invalid proposer signature on header"

    yield (
        "messages",
        "meta",
        [
            {
                "group_id": get_filename(group_id),
                "column_index": int(column_index),
                "offset_ms": 500,
                "message": get_filename(partial),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_all_phases_from_to(FULU, GLOAS)
@spec_state_test
def test_gossip_partial_data_column_sidecar__ignore_parent_not_seen(spec, state):
    """Test that a header whose parent is unknown to the store is ignored."""
    yield "topic", "meta", "partial_data_column_sidecar"

    state = build_state_with_complete_transition(spec, state)
    anchor_state = state.copy()
    yield "state", anchor_state

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
    group_id = spec.PartialDataColumnGroupID(beacon_block_root=block_root)
    yield get_filename(group_id), group_id

    yield get_filename(partial), partial

    block_time_ms = spec.compute_time_at_slot_ms(state, sidecar.signed_block_header.message.slot)
    yield "current_time_ms", "meta", int(block_time_ms)

    column_index = sidecar.index
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        sidecar=partial,
        current_time_ms=block_time_ms + 500,
        group_id=group_id,
        column_index=column_index,
    )
    assert result == "ignore"
    assert reason == "header's parent has not been seen"

    yield (
        "messages",
        "meta",
        [
            {
                "group_id": get_filename(group_id),
                "column_index": int(column_index),
                "offset_ms": 500,
                "message": get_filename(partial),
                "expected": "ignore",
                "reason": reason,
            }
        ],
    )


@with_all_phases_from_to(FULU, GLOAS)
@spec_state_test
def test_gossip_partial_data_column_sidecar__reject_parent_failed_validation(spec, state):
    """Test that a header whose parent failed validation is rejected."""
    yield "topic", "meta", "partial_data_column_sidecar"

    state = build_state_with_complete_transition(spec, state)
    anchor_state = state.copy()
    yield "state", anchor_state

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
    group_id = make_partial_data_column_group_id(spec, sidecar)
    yield get_filename(group_id), group_id

    yield get_filename(partial), partial

    block_time_ms = spec.compute_time_at_slot_ms(state, sidecar.signed_block_header.message.slot)
    yield "current_time_ms", "meta", int(block_time_ms)

    column_index = sidecar.index
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        sidecar=partial,
        current_time_ms=block_time_ms + 500,
        group_id=group_id,
        column_index=column_index,
    )
    assert result == "reject"
    assert reason == "header's parent failed validation"

    yield (
        "messages",
        "meta",
        [
            {
                "group_id": get_filename(group_id),
                "column_index": int(column_index),
                "offset_ms": 500,
                "message": get_filename(partial),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_all_phases_from_to(FULU, GLOAS)
@spec_state_test
def test_gossip_partial_data_column_sidecar__reject_slot_not_higher_than_parent(spec, state):
    """Test that a header whose slot is not greater than its parent's is rejected."""
    yield "topic", "meta", "partial_data_column_sidecar"

    state = build_state_with_complete_transition(spec, state)
    anchor_state = state.copy()
    yield "state", anchor_state

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
    group_id = spec.PartialDataColumnGroupID(beacon_block_root=block_root)
    yield get_filename(group_id), group_id

    yield get_filename(partial), partial

    block_time_ms = spec.compute_time_at_slot_ms(
        state, partial.header[0].signed_block_header.message.slot
    )
    yield "current_time_ms", "meta", int(block_time_ms)

    column_index = sidecar.index
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        sidecar=partial,
        current_time_ms=block_time_ms + 500,
        group_id=group_id,
        column_index=column_index,
    )
    assert result == "reject"
    assert reason == "header is not from a higher slot than its parent"

    yield (
        "messages",
        "meta",
        [
            {
                "group_id": get_filename(group_id),
                "column_index": int(column_index),
                "offset_ms": 500,
                "message": get_filename(partial),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_all_phases_from_to(FULU, GLOAS)
@spec_state_test
def test_gossip_partial_data_column_sidecar__reject_non_ancestor_finalized_checkpoint(spec, state):
    """Test that a header is rejected if the finalized checkpoint is not an ancestor."""
    yield "topic", "meta", "partial_data_column_sidecar"

    state = build_state_with_complete_transition(spec, state)
    anchor_state = state.copy()
    yield "state", anchor_state

    seen = get_seen(spec)
    store, anchor_block = setup_store_with_anchor(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    _, sidecars = build_signed_block_and_sidecars(spec, state, blob_count=1)
    sidecar = sidecars[0]
    partial = make_partial_sidecar(spec, sidecar, blob_indices=[], include_header=True)
    group_id = make_partial_data_column_group_id(spec, sidecar)
    yield get_filename(group_id), group_id

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
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        sidecar=partial,
        current_time_ms=block_time_ms + 500,
        group_id=group_id,
        column_index=column_index,
    )
    assert result == "reject"
    assert reason == "finalized checkpoint is not an ancestor of header's block"

    yield (
        "messages",
        "meta",
        [
            {
                "group_id": get_filename(group_id),
                "column_index": int(column_index),
                "offset_ms": 500,
                "message": get_filename(partial),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_all_phases_from_to(FULU, GLOAS)
@spec_state_test
def test_gossip_partial_data_column_sidecar__reject_invalid_inclusion_proof(spec, state):
    """Test that a header with a broken inclusion proof is rejected."""
    yield "topic", "meta", "partial_data_column_sidecar"

    state = build_state_with_complete_transition(spec, state)
    anchor_state = state.copy()
    yield "state", anchor_state

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
    group_id = make_partial_data_column_group_id(spec, sidecar)
    yield get_filename(group_id), group_id

    yield get_filename(partial), partial

    block_time_ms = spec.compute_time_at_slot_ms(state, sidecar.signed_block_header.message.slot)
    yield "current_time_ms", "meta", int(block_time_ms)

    column_index = sidecar.index
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        sidecar=partial,
        current_time_ms=block_time_ms + 500,
        group_id=group_id,
        column_index=column_index,
    )
    assert result == "reject"
    assert reason == "invalid header inclusion proof"

    yield (
        "messages",
        "meta",
        [
            {
                "group_id": get_filename(group_id),
                "column_index": int(column_index),
                "offset_ms": 500,
                "message": get_filename(partial),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_all_phases_from_to(FULU, GLOAS)
@spec_state_test
def test_gossip_partial_data_column_sidecar__reject_wrong_proposer_index(spec, state):
    """Test that a header with the wrong proposer_index is rejected."""
    yield "topic", "meta", "partial_data_column_sidecar"

    state = build_state_with_complete_transition(spec, state)
    anchor_state = state.copy()
    yield "state", anchor_state

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
    group_id = spec.PartialDataColumnGroupID(beacon_block_root=block_root)
    yield get_filename(group_id), group_id

    yield get_filename(partial), partial

    block_time_ms = spec.compute_time_at_slot_ms(state, sidecar.signed_block_header.message.slot)
    yield "current_time_ms", "meta", int(block_time_ms)

    column_index = sidecar.index
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        sidecar=partial,
        current_time_ms=block_time_ms + 500,
        group_id=group_id,
        column_index=column_index,
    )
    assert result == "reject"
    assert reason == "header proposer_index does not match expected proposer"

    yield (
        "messages",
        "meta",
        [
            {
                "group_id": get_filename(group_id),
                "column_index": int(column_index),
                "offset_ms": 500,
                "message": get_filename(partial),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_all_phases_from_to(FULU, GLOAS)
@spec_state_test
def test_gossip_partial_data_column_sidecar__ignore_cells_without_cached_header(spec, state):
    """Test that a cells-only partial sidecar is ignored when no header is cached."""
    yield "topic", "meta", "partial_data_column_sidecar"

    state = build_state_with_complete_transition(spec, state)
    anchor_state = state.copy()
    yield "state", anchor_state

    seen = get_seen(spec)
    store, anchor_block = setup_store_with_anchor(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    _, sidecars = build_signed_block_and_sidecars(spec, state, blob_count=1)
    sidecar = sidecars[0]
    partial = make_partial_sidecar(spec, sidecar, include_header=False)
    group_id = make_partial_data_column_group_id(spec, sidecar)
    yield get_filename(group_id), group_id

    yield get_filename(partial), partial

    block_time_ms = spec.compute_time_at_slot_ms(state, sidecar.signed_block_header.message.slot)
    yield "current_time_ms", "meta", int(block_time_ms)

    column_index = sidecar.index
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        sidecar=partial,
        current_time_ms=block_time_ms + 500,
        group_id=group_id,
        column_index=column_index,
    )
    assert result == "ignore"
    assert reason == "valid corresponding header has not been seen"

    yield (
        "messages",
        "meta",
        [
            {
                "group_id": get_filename(group_id),
                "column_index": int(column_index),
                "offset_ms": 500,
                "message": get_filename(partial),
                "expected": "ignore",
                "reason": reason,
            }
        ],
    )


@with_all_phases_from_to(FULU, GLOAS)
@spec_state_test
def test_gossip_partial_data_column_sidecar__ignore_cells_with_cached_header_future_slot(
    spec, state
):
    """Test that a cached-header cells-only sidecar is ignored if it is from a future slot."""
    yield "topic", "meta", "partial_data_column_sidecar"

    state = build_state_with_complete_transition(spec, state)
    anchor_state = state.copy()
    yield "state", anchor_state

    seen = get_seen(spec)
    store, anchor_block = setup_store_with_anchor(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    _, sidecars = build_signed_block_and_sidecars(spec, state, blob_count=1)
    sidecar = sidecars[0]
    group_id = make_partial_data_column_group_id(spec, sidecar)
    yield get_filename(group_id), group_id

    header_msg = make_partial_sidecar(spec, sidecar, blob_indices=[], include_header=True)
    cells_msg = make_partial_sidecar(spec, sidecar, include_header=False)

    yield get_filename(header_msg), header_msg
    yield get_filename(cells_msg), cells_msg

    slot_time_ms = spec.compute_time_at_slot_ms(state, sidecar.signed_block_header.message.slot)
    current_time_ms = slot_time_ms - spec.config.MAXIMUM_GOSSIP_CLOCK_DISPARITY - 1
    yield "current_time_ms", "meta", int(current_time_ms)

    column_index = sidecar.index

    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        sidecar=header_msg,
        current_time_ms=current_time_ms + 1,
        group_id=group_id,
        column_index=column_index,
    )
    assert result == "valid"
    assert reason is None

    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        sidecar=cells_msg,
        current_time_ms=current_time_ms,
        group_id=group_id,
        column_index=column_index,
    )
    assert result == "ignore"
    assert reason == "corresponding header is from a future slot"

    yield (
        "messages",
        "meta",
        [
            {
                "group_id": get_filename(group_id),
                "column_index": int(column_index),
                "offset_ms": 1,
                "message": get_filename(header_msg),
                "expected": "valid",
            },
            {
                "group_id": get_filename(group_id),
                "column_index": int(column_index),
                "offset_ms": 0,
                "message": get_filename(cells_msg),
                "expected": "ignore",
                "reason": reason,
            },
        ],
    )


@with_all_phases_from_to(FULU, GLOAS)
@spec_state_test
def test_gossip_partial_data_column_sidecar__ignore_cells_with_cached_header_not_later_than_finalized_slot(
    spec, state
):
    """Test that a cached-header cells-only sidecar is ignored once finalization advances."""
    yield "topic", "meta", "partial_data_column_sidecar"

    state = build_state_with_complete_transition(spec, state)
    anchor_state = state.copy()
    seen = get_seen(spec)
    store, anchor_block = setup_store_with_anchor(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    transition_to(spec, state, spec.Slot(spec.SLOTS_PER_EPOCH - 1))
    yield "state", anchor_state

    _, sidecars = build_signed_block_and_sidecars(spec, state, blob_count=1)
    sidecar = sidecars[0]
    group_id = make_partial_data_column_group_id(spec, sidecar)
    yield get_filename(group_id), group_id

    header = make_partial_header(spec, sidecar)
    cells_msg = make_partial_sidecar(spec, sidecar, include_header=False)

    yield get_filename(header), header
    yield get_filename(cells_msg), cells_msg

    block_header = sidecar.signed_block_header.message
    sidecar_epoch = spec.compute_epoch_at_slot(block_header.slot)
    block_time_ms = spec.compute_time_at_slot_ms(state, block_header.slot)
    yield "current_time_ms", "meta", int(block_time_ms)

    block_root = group_id.beacon_block_root
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
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        sidecar=cells_msg,
        current_time_ms=block_time_ms + 500,
        group_id=group_id,
        column_index=column_index,
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
                "group_id": get_filename(group_id),
                "column_index": int(column_index),
                "offset_ms": 500,
                "message": get_filename(cells_msg),
                "expected": "ignore",
                "reason": reason,
            },
        ],
    )


@with_fulu_and_later
@spec_state_test
def test_gossip_partial_data_column_sidecar__reject_bitmap_length_mismatch(spec, state):
    """A partial sidecar whose bitmap length does not match the commitment count is rejected."""
    yield "topic", "meta", "partial_data_column_sidecar"

    if not is_post_gloas(spec):
        state = build_state_with_complete_transition(spec, state)
    anchor_state = state.copy()
    yield "state", anchor_state

    store, anchor_block = setup_store_with_anchor(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    signed_block, sidecars = build_signed_block_and_sidecars(spec, state, blob_count=1)
    sidecar = sidecars[0]
    column_index = sidecar.index

    group_id = make_partial_data_column_group_id(spec, sidecar)
    yield get_filename(group_id), group_id

    # Pad bitmap, cells, and proofs in lockstep so the count checks pass but the
    # bitmap length no longer matches the commitment count.
    partial = make_partial_sidecar(spec, sidecar)
    bitmap_type = type(partial.cells_present_bitmap)
    cells_type = type(partial.partial_column)
    proofs_type = type(partial.kzg_proofs)
    partial.cells_present_bitmap = bitmap_type(list(partial.cells_present_bitmap) + [True])
    partial.partial_column = cells_type(list(partial.partial_column) + [spec.Cell()])
    partial.kzg_proofs = proofs_type(list(partial.kzg_proofs) + [spec.KZGProof()])
    yield get_filename(partial), partial

    yield get_filename(signed_anchor), signed_anchor
    blocks_meta = [{"block": get_filename(signed_anchor)}]
    if is_post_gloas(spec):
        store.blocks[sidecar.beacon_block_root] = signed_block.message
        store.block_states[sidecar.beacon_block_root] = state.copy()
        yield get_filename(signed_block), signed_block
        blocks_meta.append({"block": get_filename(signed_block)})
    yield "blocks", "meta", blocks_meta

    block_time_ms = spec.compute_time_at_slot_ms(state, signed_block.message.slot)
    yield "current_time_ms", "meta", int(block_time_ms)

    kwargs = {}
    if not is_post_gloas(spec):
        kwargs["seen"] = get_seen(spec)
        kwargs["state"] = state
        kwargs["current_time_ms"] = block_time_ms + 500
    result, reason = run_validate_gossip(
        spec,
        store=store,
        sidecar=partial,
        group_id=group_id,
        column_index=column_index,
        **kwargs,
    )
    assert result == "reject"
    if is_post_gloas(spec):
        assert reason == "bitmap length does not match the number of bid commitments"
    else:
        assert reason == "bitmap length does not match commitments length"

    yield (
        "messages",
        "meta",
        [
            {
                "group_id": get_filename(group_id),
                "column_index": int(column_index),
                "offset_ms": 500,
                "message": get_filename(partial),
                "expected": result,
                "reason": reason,
            }
        ],
    )


@with_fulu_and_later
@spec_state_test
def test_gossip_partial_data_column_sidecar__reject_invalid_kzg_proofs(spec, state):
    """A partial sidecar whose KZG proofs fail verification is rejected."""
    yield "topic", "meta", "partial_data_column_sidecar"

    if not is_post_gloas(spec):
        state = build_state_with_complete_transition(spec, state)
    anchor_state = state.copy()
    yield "state", anchor_state

    store, anchor_block = setup_store_with_anchor(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    signed_block, sidecars = build_signed_block_and_sidecars(spec, state, blob_count=2)
    sidecar = sidecars[0]
    column_index = sidecar.index

    group_id = make_partial_data_column_group_id(spec, sidecar)
    yield get_filename(group_id), group_id

    # Swap the two proofs so each cell carries the other's proof: still
    # well-formed, but verification returns False rather than raising.
    partial = make_partial_sidecar(spec, sidecar)
    proofs_type = type(partial.kzg_proofs)
    first, second = partial.kzg_proofs[0], partial.kzg_proofs[1]
    partial.kzg_proofs = proofs_type([second, first])
    yield get_filename(partial), partial

    yield get_filename(signed_anchor), signed_anchor
    blocks_meta = [{"block": get_filename(signed_anchor)}]
    if is_post_gloas(spec):
        store.blocks[sidecar.beacon_block_root] = signed_block.message
        store.block_states[sidecar.beacon_block_root] = state.copy()
        yield get_filename(signed_block), signed_block
        blocks_meta.append({"block": get_filename(signed_block)})
    yield "blocks", "meta", blocks_meta

    block_time_ms = spec.compute_time_at_slot_ms(state, signed_block.message.slot)
    yield "current_time_ms", "meta", int(block_time_ms)

    kwargs = {}
    if not is_post_gloas(spec):
        kwargs["seen"] = get_seen(spec)
        kwargs["state"] = state
        kwargs["current_time_ms"] = block_time_ms + 500
    result, reason = run_validate_gossip(
        spec,
        store=store,
        sidecar=partial,
        group_id=group_id,
        column_index=column_index,
        **kwargs,
    )
    assert result == "reject"
    assert reason == "invalid sidecar kzg proofs"

    yield (
        "messages",
        "meta",
        [
            {
                "group_id": get_filename(group_id),
                "column_index": int(column_index),
                "offset_ms": 500,
                "message": get_filename(partial),
                "expected": result,
                "reason": reason,
            }
        ],
    )
