from eth_consensus_specs.test.context import (
    expect_assertion_error,
    spec_state_test,
    with_gloas_and_later,
)
from eth_consensus_specs.test.helpers.blob import get_block_with_blob_and_sidecars
from eth_consensus_specs.test.helpers.block import sign_block
from eth_consensus_specs.test.helpers.fork_choice import (
    get_genesis_forkchoice_store_and_block,
)
from eth_consensus_specs.test.helpers.gossip import (
    get_filename,
    get_seen,
    run_validate_gossip,
    wrap_genesis_block,
)


def setup_gloas_sidecar(spec, state, block_in_store=True):
    """
    Build a signed block carrying one blob, advance the state, and return
    (store, signed_anchor, signed_block, sidecar) ready for validation. With
    ``block_in_store=False``, the block is left out of the store entirely.
    """
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    _, _, _, signed_block, sidecars, _ = get_block_with_blob_and_sidecars(spec, state, blob_count=1)
    if block_in_store:
        block_root = signed_block.message.hash_tree_root()
        store.blocks[block_root] = signed_block.message
        store.block_states[block_root] = state.copy()
    return store, signed_anchor, signed_block, sidecars[0]


def setup_gloas_failed_block_sidecar(spec, state):
    """
    Build a blob-carrying block, corrupt its state root so it fails state
    transition on import, and record it as seen: present in ``store.blocks``
    with no post-state. The sidecar is re-pointed at the failed block, whose bid
    commitments and slot are unchanged, so only the missing post-state is at
    fault. Returns (store, signed_anchor, signed_failed_block, sidecar).
    """
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    pre_state = state.copy()
    _, _, _, signed_block, sidecars, _ = get_block_with_blob_and_sidecars(spec, state, blob_count=1)

    # Corrupt the block so it genuinely fails state transition, mirroring
    # setup_store_with_failed_block but for a blob-carrying block.
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

    # Re-point the sidecar at the failed block. Corrupting the state root does
    # not change the bid's blob commitments or the block's slot, so the sidecar
    # stays otherwise valid and only the missing post-state can fail.
    sidecar = sidecars[0]
    sidecar.beacon_block_root = failed_root
    return store, signed_anchor, signed_failed_block, sidecar


@with_gloas_and_later
@spec_state_test
def test_gossip_data_column_sidecar__ignore_block_unseen(spec, state):
    """A sidecar whose beacon_block_root has no corresponding block in the store is ignored."""
    anchor_state = state.copy()
    yield "topic", "meta", "data_column_sidecar"

    store, signed_anchor, _, sidecar = setup_gloas_sidecar(spec, state, block_in_store=False)
    yield "state", anchor_state
    yield get_filename(signed_anchor), signed_anchor
    # The signed_block from setup_gloas_sidecar is not added here
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]
    yield get_filename(sidecar), sidecar

    seen = get_seen(spec)
    correct_subnet = spec.compute_subnet_for_data_column_sidecar(sidecar.index)

    time_ms = spec.compute_time_at_slot_ms(state, sidecar.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 500
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        sidecar=sidecar,
        current_time_ms=time_ms,
        subnet_id=correct_subnet,
    )
    assert result == "ignore"
    assert reason == "block for sidecar's beacon block root has not been seen"
    messages.append(
        {
            "subnet_id": int(correct_subnet),
            "current_time_ms": int(time_ms),
            "message": get_filename(sidecar),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_data_column_sidecar__reject_block_failed_validation(spec, state):
    """A sidecar whose referenced block failed state transition is rejected.

    The block is present in the store (seen) but has no post-state, so cells
    committed by a known-invalid block must not be forwarded.
    """
    anchor_state = state.copy()
    yield "topic", "meta", "data_column_sidecar"

    store, signed_anchor, signed_failed_block, sidecar = setup_gloas_failed_block_sidecar(
        spec, state
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
    yield get_filename(sidecar), sidecar

    seen = get_seen(spec)
    correct_subnet = spec.compute_subnet_for_data_column_sidecar(sidecar.index)

    time_ms = spec.compute_time_at_slot_ms(state, sidecar.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 500
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        sidecar=sidecar,
        current_time_ms=time_ms,
        subnet_id=correct_subnet,
    )
    assert result == "reject"
    assert reason == "block for sidecar's beacon block root failed validation"
    messages.append(
        {
            "subnet_id": int(correct_subnet),
            "current_time_ms": int(time_ms),
            "message": get_filename(sidecar),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_data_column_sidecar__ignore_already_seen(spec, state):
    """A sidecar already in seen.data_column_sidecar_tuples is ignored."""
    anchor_state = state.copy()
    yield "topic", "meta", "data_column_sidecar"

    store, signed_anchor, signed_block, sidecar = setup_gloas_sidecar(spec, state)
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
    yield get_filename(sidecar), sidecar

    seen = get_seen(spec)
    correct_subnet = spec.compute_subnet_for_data_column_sidecar(sidecar.index)

    time_ms = spec.compute_time_at_slot_ms(state, sidecar.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    # The first validation is fully valid and seeds the seen cache.
    time_ms += 500
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        sidecar=sidecar,
        current_time_ms=time_ms,
        subnet_id=correct_subnet,
    )
    assert result == "valid"
    assert reason is None
    messages.append(
        {
            "subnet_id": int(correct_subnet),
            "current_time_ms": int(time_ms),
            "message": get_filename(sidecar),
            "expected": result,
        }
    )

    # The same sidecar received again is ignored as already seen.
    time_ms += 100
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        sidecar=sidecar,
        current_time_ms=time_ms,
        subnet_id=correct_subnet,
    )
    assert result == "ignore"
    assert reason == "already seen sidecar for this block root and index"
    messages.append(
        {
            "subnet_id": int(correct_subnet),
            "current_time_ms": int(time_ms),
            "message": get_filename(sidecar),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_data_column_sidecar__reject_slot_mismatch(spec, state):
    """A sidecar whose slot does not match the referenced block's slot is rejected."""
    anchor_state = state.copy()
    yield "topic", "meta", "data_column_sidecar"

    store, signed_anchor, signed_block, sidecar = setup_gloas_sidecar(spec, state)
    # Corrupt the sidecar's slot so it no longer matches the block.
    sidecar.slot = spec.Slot(sidecar.slot + 1)
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
    yield get_filename(sidecar), sidecar

    seen = get_seen(spec)
    correct_subnet = spec.compute_subnet_for_data_column_sidecar(sidecar.index)

    time_ms = spec.compute_time_at_slot_ms(state, sidecar.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 500
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        sidecar=sidecar,
        current_time_ms=time_ms,
        subnet_id=correct_subnet,
    )
    assert result == "reject"
    assert reason == "sidecar's slot does not match block's slot"
    messages.append(
        {
            "subnet_id": int(correct_subnet),
            "current_time_ms": int(time_ms),
            "message": get_filename(sidecar),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_data_column_sidecar__reject_invalid_sidecar(spec, state):
    """A sidecar whose structural validation fails is rejected."""
    anchor_state = state.copy()
    yield "topic", "meta", "data_column_sidecar"

    store, signed_anchor, signed_block, sidecar = setup_gloas_sidecar(spec, state)
    # Pad the column with an extra cell so its length no longer matches the
    # bid's blob commitments, causing verify_data_column_sidecar to fail.
    sidecar.column = spec.List[spec.Cell, spec.MAX_BLOB_COMMITMENTS_PER_BLOCK](
        *sidecar.column, spec.Cell()
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
    yield get_filename(sidecar), sidecar

    seen = get_seen(spec)
    correct_subnet = spec.compute_subnet_for_data_column_sidecar(sidecar.index)

    time_ms = spec.compute_time_at_slot_ms(state, sidecar.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 500
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        sidecar=sidecar,
        current_time_ms=time_ms,
        subnet_id=correct_subnet,
    )
    assert result == "reject"
    assert reason == "invalid sidecar"
    messages.append(
        {
            "subnet_id": int(correct_subnet),
            "current_time_ms": int(time_ms),
            "message": get_filename(sidecar),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages
