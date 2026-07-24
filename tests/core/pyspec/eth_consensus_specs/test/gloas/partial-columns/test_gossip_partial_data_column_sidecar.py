from eth_consensus_specs.test.context import (
    expect_assertion_error,
    spec_state_test,
    with_gloas_and_later,
)
from eth_consensus_specs.test.helpers.blob import (
    get_block_with_blob_and_sidecars,
    make_partial_data_column_group_id,
    make_partial_sidecar,
)
from eth_consensus_specs.test.helpers.block import sign_block
from eth_consensus_specs.test.helpers.fork_choice import (
    get_genesis_forkchoice_store_and_block,
)
from eth_consensus_specs.test.helpers.gossip import (
    get_filename,
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
    partial = make_partial_sidecar(spec, sidecar, blob_indices=blob_indices)
    group_id = make_partial_data_column_group_id(spec, sidecar)
    return store, signed_anchor, signed_block, partial, group_id, sidecar.index


def setup_gloas_partial_failed_block_sidecar(spec, state):
    """
    Like setup_gloas_partial_sidecar, but the referenced block fails state
    transition: it is present in store.blocks with no post-state. The group ID
    is re-pointed at the failed block, whose bid commitments and slot are
    unchanged, so only the missing post-state is at fault. Returns
    (store, signed_anchor, signed_failed_block, partial, group_id, column_index).
    """
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    pre_state = state.copy()
    _, _, _, signed_block, sidecars, _ = get_block_with_blob_and_sidecars(spec, state, blob_count=1)

    # Corrupt the block so it genuinely fails state transition.
    failed_block = signed_block.message.copy()
    failed_block.state_root = spec.Root(b"\xab" * 32)
    signed_failed_block = sign_block(
        spec, state, failed_block, proposer_index=failed_block.proposer_index
    )
    expect_assertion_error(
        lambda: spec.state_transition(pre_state.copy(), signed_failed_block, validate_result=True)
    )
    failed_root = signed_failed_block.message.hash_tree_root()
    store.blocks[failed_root] = signed_failed_block.message

    sidecar = sidecars[0]
    partial = make_partial_sidecar(spec, sidecar)
    group_id = make_partial_data_column_group_id(spec, sidecar)
    group_id.beacon_block_root = failed_root
    return store, signed_anchor, signed_failed_block, partial, group_id, sidecar.index


@with_gloas_and_later
@spec_state_test
def test_gossip_partial_data_column_sidecar__valid(spec, state):
    """A well-formed partial sidecar with cells matching the bid passes."""
    yield "topic", "meta", "partial_data_column_sidecar"

    # Capture the genesis anchor state before the setup helper advances it, so
    # the yielded anchor state matches the first (anchor) block for replay.
    anchor_state = state.copy()
    store, signed_anchor, signed_block, partial, group_id, column_index = (
        setup_gloas_partial_sidecar(spec, state)
    )
    yield "state", anchor_state
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
    yield get_filename(group_id), group_id
    yield get_filename(partial), partial

    time_ms = spec.compute_time_at_slot_ms(state, signed_block.message.slot)
    yield "current_time_ms", "meta", int(time_ms)

    result, reason = run_validate_gossip(
        spec,
        store=store,
        sidecar=partial,
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
                "expected": result,
            }
        ],
    )


@with_gloas_and_later
@spec_state_test
def test_gossip_partial_data_column_sidecar__reject_slot_mismatch(spec, state):
    """A partial sidecar whose group_id.slot doesn't match the block is rejected."""
    yield "topic", "meta", "partial_data_column_sidecar"

    # Capture the genesis anchor state before the setup helper advances it, so
    # the yielded anchor state matches the first (anchor) block for replay.
    anchor_state = state.copy()
    store, signed_anchor, signed_block, partial, group_id, column_index = (
        setup_gloas_partial_sidecar(spec, state)
    )
    # Bump the slot so it no longer matches.
    group_id.slot = spec.Slot(group_id.slot + 1)

    yield "state", anchor_state
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
    yield get_filename(group_id), group_id
    yield get_filename(partial), partial

    time_ms = spec.compute_time_at_slot_ms(state, signed_block.message.slot)
    yield "current_time_ms", "meta", int(time_ms)

    result, reason = run_validate_gossip(
        spec,
        store=store,
        sidecar=partial,
        group_id=group_id,
        column_index=column_index,
    )
    assert result == "reject"
    assert reason == "group id's slot does not match the block's slot"

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


@with_gloas_and_later
@spec_state_test
def test_gossip_partial_data_column_sidecar__ignore_block_unseen(spec, state):
    """A partial sidecar whose group_id references an unknown block is ignored."""
    yield "topic", "meta", "partial_data_column_sidecar"

    # Capture the genesis anchor state before the setup helper advances it, so
    # the yielded anchor state matches the first (anchor) block for replay.
    anchor_state = state.copy()
    store, signed_anchor, signed_block, partial, group_id, column_index = (
        setup_gloas_partial_sidecar(spec, state)
    )
    group_id.beacon_block_root = spec.Root(b"\xab" * 32)

    yield "state", anchor_state
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
    yield get_filename(group_id), group_id
    yield get_filename(partial), partial

    time_ms = spec.compute_time_at_slot_ms(state, signed_block.message.slot)
    yield "current_time_ms", "meta", int(time_ms)

    result, reason = run_validate_gossip(
        spec,
        store=store,
        sidecar=partial,
        group_id=group_id,
        column_index=column_index,
    )
    assert result == "ignore"
    assert reason == "group id's block has not been seen"

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


@with_gloas_and_later
@spec_state_test
def test_gossip_partial_data_column_sidecar__reject_block_failed_validation(spec, state):
    """A partial sidecar whose referenced block failed state transition is rejected.

    The block is present in the store (seen) but has no post-state, so cells
    committed by a known-invalid block must not be forwarded.
    """
    yield "topic", "meta", "partial_data_column_sidecar"

    # Capture the genesis anchor state before the setup helper advances it, so
    # the yielded anchor state matches the first (anchor) block for replay.
    anchor_state = state.copy()
    store, signed_anchor, signed_failed_block, partial, group_id, column_index = (
        setup_gloas_partial_failed_block_sidecar(spec, state)
    )

    yield "state", anchor_state
    yield get_filename(signed_anchor), signed_anchor
    yield get_filename(signed_failed_block), signed_failed_block
    yield (
        "blocks",
        "meta",
        [
            {"block": get_filename(signed_anchor)},
            {"block": get_filename(signed_failed_block), "failed": True},
        ],
    )
    yield get_filename(group_id), group_id
    yield get_filename(partial), partial

    time_ms = spec.compute_time_at_slot_ms(state, signed_failed_block.message.slot)
    yield "current_time_ms", "meta", int(time_ms)

    result, reason = run_validate_gossip(
        spec,
        store=store,
        sidecar=partial,
        group_id=group_id,
        column_index=column_index,
    )
    assert result == "reject"
    assert reason == "group id's block failed validation"

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
