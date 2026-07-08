from eth_consensus_specs.test.context import (
    spec_state_test,
    with_gloas_and_later,
)
from eth_consensus_specs.test.helpers.block import build_empty_block_for_next_slot
from eth_consensus_specs.test.helpers.execution_payload import (
    build_signed_execution_payload_envelope,
)
from eth_consensus_specs.test.helpers.fork_choice import (
    get_genesis_forkchoice_store_and_block,
)
from eth_consensus_specs.test.helpers.gossip import (
    get_filename,
    get_seen,
    run_validate_gossip,
    setup_store_with_failed_block,
    wrap_genesis_block,
)
from eth_consensus_specs.test.helpers.state import state_transition_and_sign_block


def setup_store_with_block(spec, state):
    """Apply one block to the genesis store. Returns store, blocks, block_root."""
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block)
    block_root = signed_block.message.hash_tree_root()
    store.blocks[block_root] = signed_block.message
    store.block_states[block_root] = state.copy()
    return store, [signed_anchor, signed_block], signed_block, block_root


@with_gloas_and_later
@spec_state_test
def test_gossip_execution_payload_envelope__valid(spec, state):
    """A well-formed envelope for a known block passes gossip validation."""
    yield "topic", "meta", "execution_payload"

    store, blocks, signed_block, block_root = setup_store_with_block(spec, state)
    yield "state", state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    seen = get_seen(spec)
    signed_envelope = build_signed_execution_payload_envelope(spec, state, block_root, signed_block)
    yield get_filename(signed_envelope), signed_envelope

    time_ms = spec.compute_time_at_slot_ms(state, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 100
    result, reason = run_validate_gossip(
        spec, seen=seen, store=store, state=state, signed_execution_payload_envelope=signed_envelope
    )
    assert result == "valid"
    assert reason is None
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_envelope),
            "expected": result,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_execution_payload_envelope__ignore_block_unseen(spec, state):
    """An envelope referencing an unknown beacon block is ignored."""
    yield "topic", "meta", "execution_payload"

    store, blocks, signed_block, block_root = setup_store_with_block(spec, state)
    yield "state", state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    seen = get_seen(spec)
    signed_envelope = build_signed_execution_payload_envelope(spec, state, block_root, signed_block)
    # Re-target the envelope at a block root that is not in the store.
    signed_envelope.message.beacon_block_root = spec.Root(b"\xab" * 32)
    yield get_filename(signed_envelope), signed_envelope

    time_ms = spec.compute_time_at_slot_ms(state, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 100
    result, reason = run_validate_gossip(
        spec, seen=seen, store=store, state=state, signed_execution_payload_envelope=signed_envelope
    )
    assert result == "ignore"
    assert reason == "envelope's block has not been seen"
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_envelope),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_execution_payload_envelope__ignore_duplicate(spec, state):
    """The second valid envelope for the same (block_root, builder) is ignored."""
    yield "topic", "meta", "execution_payload"

    store, blocks, signed_block, block_root = setup_store_with_block(spec, state)
    yield "state", state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    seen = get_seen(spec)
    signed_envelope = build_signed_execution_payload_envelope(spec, state, block_root, signed_block)
    yield get_filename(signed_envelope), signed_envelope

    time_ms = spec.compute_time_at_slot_ms(state, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 100
    result, reason = run_validate_gossip(
        spec, seen=seen, store=store, state=state, signed_execution_payload_envelope=signed_envelope
    )
    assert result == "valid"
    assert reason is None
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_envelope),
            "expected": result,
        }
    )

    time_ms += 100
    result, reason = run_validate_gossip(
        spec, seen=seen, store=store, state=state, signed_execution_payload_envelope=signed_envelope
    )
    assert result == "ignore"
    assert reason == "already seen envelope for this block root from this builder"
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_envelope),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_execution_payload_envelope__reject_slot_mismatch(spec, state):
    """An envelope whose payload.slot_number does not match block.slot is rejected."""
    yield "topic", "meta", "execution_payload"

    store, blocks, signed_block, block_root = setup_store_with_block(spec, state)
    yield "state", state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    seen = get_seen(spec)
    signed_envelope = build_signed_execution_payload_envelope(spec, state, block_root, signed_block)
    signed_envelope.message.payload.slot_number = spec.uint64(state.slot + 1)
    yield get_filename(signed_envelope), signed_envelope

    time_ms = spec.compute_time_at_slot_ms(state, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 100
    result, reason = run_validate_gossip(
        spec, seen=seen, store=store, state=state, signed_execution_payload_envelope=signed_envelope
    )
    assert result == "reject"
    assert reason == "block's slot does not match payload's slot number"
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_envelope),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_execution_payload_envelope__reject_block_hash_mismatch(spec, state):
    """An envelope whose payload.block_hash does not match the bid is rejected."""
    yield "topic", "meta", "execution_payload"

    store, blocks, signed_block, block_root = setup_store_with_block(spec, state)
    yield "state", state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    seen = get_seen(spec)
    signed_envelope = build_signed_execution_payload_envelope(spec, state, block_root, signed_block)
    signed_envelope.message.payload.block_hash = spec.Hash32(b"\xcd" * 32)
    yield get_filename(signed_envelope), signed_envelope

    time_ms = spec.compute_time_at_slot_ms(state, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 100
    result, reason = run_validate_gossip(
        spec, seen=seen, store=store, state=state, signed_execution_payload_envelope=signed_envelope
    )
    assert result == "reject"
    assert reason == "payload's block hash does not match the bid's block hash"
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_envelope),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_execution_payload_envelope__reject_invalid_signature(spec, state):
    """An envelope with an invalid signature is rejected."""
    yield "topic", "meta", "execution_payload"

    store, blocks, signed_block, block_root = setup_store_with_block(spec, state)
    yield "state", state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    seen = get_seen(spec)
    signed_envelope = build_signed_execution_payload_envelope(spec, state, block_root, signed_block)
    signed_envelope.signature = spec.BLSSignature()
    yield get_filename(signed_envelope), signed_envelope

    time_ms = spec.compute_time_at_slot_ms(state, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 100
    result, reason = run_validate_gossip(
        spec, seen=seen, store=store, state=state, signed_execution_payload_envelope=signed_envelope
    )
    assert result == "reject"
    assert reason == "invalid envelope signature"
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_envelope),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_execution_payload_envelope__ignore_pre_finalized(spec, state):
    """An envelope whose payload slot is before the latest finalized slot is ignored."""
    yield "topic", "meta", "execution_payload"

    store, blocks, signed_block, block_root = setup_store_with_block(spec, state)
    # Advance the finalized checkpoint past the block's slot so the envelope
    # appears to be from a pre-finalized slot.
    store.finalized_checkpoint = spec.Checkpoint(
        epoch=spec.Epoch(spec.compute_epoch_at_slot(state.slot) + 2),
        root=block_root,
    )
    yield "state", state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]
    yield (
        "finalized_checkpoint",
        "meta",
        {
            "epoch": int(store.finalized_checkpoint.epoch),
            "root": "0x" + block_root.hex(),
        },
    )

    seen = get_seen(spec)
    signed_envelope = build_signed_execution_payload_envelope(spec, state, block_root, signed_block)
    yield get_filename(signed_envelope), signed_envelope

    time_ms = spec.compute_time_at_slot_ms(state, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 100
    result, reason = run_validate_gossip(
        spec, seen=seen, store=store, state=state, signed_execution_payload_envelope=signed_envelope
    )
    assert result == "ignore"
    assert reason == "envelope is from a slot before the latest finalized slot"
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_envelope),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_execution_payload_envelope__reject_block_failed_validation(spec, state):
    """An envelope whose block failed validation is rejected."""
    yield "topic", "meta", "execution_payload"

    store, signed_anchor, signed_block = setup_store_with_failed_block(spec, state)
    block_root = signed_block.message.hash_tree_root()
    yield "state", state
    yield get_filename(signed_anchor), signed_anchor
    yield get_filename(signed_block), signed_block
    yield (
        "blocks",
        "meta",
        [
            {"block": get_filename(signed_anchor)},
            {"block": get_filename(signed_block), "failed": True},
        ],
    )

    seen = get_seen(spec)
    signed_envelope = build_signed_execution_payload_envelope(spec, state, block_root, signed_block)
    yield get_filename(signed_envelope), signed_envelope

    time_ms = spec.compute_time_at_slot_ms(state, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 100
    result, reason = run_validate_gossip(
        spec, seen=seen, store=store, state=state, signed_execution_payload_envelope=signed_envelope
    )
    assert result == "reject"
    assert reason == "envelope's block failed validation"
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_envelope),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_execution_payload_envelope__reject_builder_index_mismatch(spec, state):
    """An envelope whose builder_index does not match the bid's builder_index is rejected."""
    yield "topic", "meta", "execution_payload"

    store, blocks, signed_block, block_root = setup_store_with_block(spec, state)
    yield "state", state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    seen = get_seen(spec)
    signed_envelope = build_signed_execution_payload_envelope(spec, state, block_root, signed_block)
    bid_builder_index = signed_block.message.body.signed_execution_payload_bid.message.builder_index
    # Pick any builder index that differs from the bid's. We subtract 1 instead
    # of adding so the value stays inside uint64 range when the bid uses the
    # max-value sentinel BUILDER_INDEX_SELF_BUILD.
    signed_envelope.message.builder_index = spec.BuilderIndex(int(bid_builder_index) - 1)
    yield get_filename(signed_envelope), signed_envelope

    time_ms = spec.compute_time_at_slot_ms(state, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 100
    result, reason = run_validate_gossip(
        spec, seen=seen, store=store, state=state, signed_execution_payload_envelope=signed_envelope
    )
    assert result == "reject"
    assert reason == "envelope's builder index does not match the bid's builder index"
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_envelope),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_execution_payload_envelope__reject_execution_requests_root_mismatch(spec, state):
    """An envelope whose execution_requests root does not match the bid's is rejected."""
    yield "topic", "meta", "execution_payload"

    store, blocks, signed_block, block_root = setup_store_with_block(spec, state)
    yield "state", state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    seen = get_seen(spec)
    # Use execution_requests with a non-empty deposits list so its root differs
    # from the bid's empty execution_requests_root.
    non_empty_requests = spec.ExecutionRequests(
        deposits=spec.DepositRequests(spec.DepositRequest())
    )
    signed_envelope = build_signed_execution_payload_envelope(
        spec, state, block_root, signed_block, execution_requests=non_empty_requests
    )
    yield get_filename(signed_envelope), signed_envelope

    time_ms = spec.compute_time_at_slot_ms(state, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 100
    result, reason = run_validate_gossip(
        spec, seen=seen, store=store, state=state, signed_execution_payload_envelope=signed_envelope
    )
    assert result == "reject"
    assert reason == "envelope's execution requests root does not match the bid"
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_envelope),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages
