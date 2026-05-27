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
from eth_consensus_specs.test.helpers.gloas.proposer_preferences import (
    build_signed_proposer_preferences,
    find_upcoming_proposal_slot,
)
from eth_consensus_specs.test.helpers.gossip import (
    get_filename,
    get_seen,
    run_validate_gossip,
    wrap_genesis_block,
)
from eth_consensus_specs.test.helpers.keys import builder_privkeys
from eth_consensus_specs.test.helpers.state import (
    state_transition_and_sign_block,
)


def setup_store_with_block(spec, state):
    """Build the genesis store and apply one block. Returns (store, blocks, parent_block_root)."""
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block)
    block_root = signed_block.message.hash_tree_root()
    store.blocks[block_root] = signed_block.message
    store.block_states[block_root] = state.copy()
    return store, [signed_anchor, signed_block], block_root


def activate_builders(spec, state):
    """
    Make every builder active by ensuring deposit_epoch < finalized_checkpoint.epoch.
    Genesis sets both to 0, so bumping the finalized epoch by one activates them.
    """
    state.finalized_checkpoint.epoch = spec.Epoch(1)


def setup_store_advanced_for_bid(spec, state):
    """
    Advance ``state`` to at least the (MIN_SEED_LOOKAHEAD + 1)-th epoch so
    bid validation's dependent_root lookup doesn't underflow, then build a
    genesis store containing every produced block and its state.
    Returns (store, blocks, parent_block_root).
    """
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    blocks = [signed_anchor]
    target_slot = spec.compute_start_slot_at_epoch(spec.Epoch(spec.MIN_SEED_LOOKAHEAD + 1))
    while state.slot < target_slot:
        block = build_empty_block_for_next_slot(spec, state)
        signed_block = state_transition_and_sign_block(spec, state, block)
        block_root = signed_block.message.hash_tree_root()
        store.blocks[block_root] = signed_block.message
        store.block_states[block_root] = state.copy()
        blocks.append(signed_block)
    return store, blocks, blocks[-1].message.hash_tree_root()


def build_signed_bid(
    spec,
    state,
    builder_index,
    slot,
    parent_block_hash,
    parent_block_root,
    fee_recipient=None,
    gas_limit=None,
    value=None,
    execution_payment=None,
    valid_signature=True,
):
    """Construct a SignedExecutionPayloadBid."""
    bid = spec.ExecutionPayloadBid(
        parent_block_hash=parent_block_hash,
        parent_block_root=parent_block_root,
        block_hash=spec.Hash32(b"\x02" + b"\x00" * 31),
        prev_randao=spec.get_randao_mix(state, spec.get_current_epoch(state)),
        fee_recipient=fee_recipient
        if fee_recipient is not None
        else spec.ExecutionAddress(b"\x11" * 20),
        gas_limit=gas_limit if gas_limit is not None else spec.uint64(30_000_000),
        builder_index=builder_index,
        slot=slot,
        value=value if value is not None else spec.Gwei(0),
        execution_payment=execution_payment if execution_payment is not None else spec.Gwei(0),
        blob_kzg_commitments=spec.List[spec.KZGCommitment, spec.MAX_BLOB_COMMITMENTS_PER_BLOCK](),
        execution_requests_root=spec.hash_tree_root(spec.ExecutionRequests()),
    )
    if valid_signature and builder_index < len(builder_privkeys):
        privkey = builder_privkeys[builder_index]
        signature = spec.get_execution_payload_bid_signature(state, bid, privkey)
    else:
        signature = spec.BLSSignature()
    return spec.SignedExecutionPayloadBid(message=bid, signature=signature)


@with_gloas_and_later
@spec_state_test
def test_gossip_execution_payload_bid__valid(spec, state):
    """A bid for the next slot from an active builder with matching preferences is valid."""
    yield "topic", "meta", "execution_payload_bid"

    store, blocks, parent_root = setup_store_advanced_for_bid(spec, state)
    activate_builders(spec, state)
    parent_signed_block = blocks[-1]
    yield "state", state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    seen = get_seen(spec)
    time_ms = spec.compute_time_at_slot_ms(state, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    common_fee = spec.ExecutionAddress(b"\x11" * 20)
    # Choose a target_gas_limit equal to the parent's payload gas_limit so the
    # is_gas_limit_target_compatible check accepts bid.gas_limit == target.
    parent_gas_limit = state.latest_execution_payload_bid.gas_limit
    time_ms += 50
    proposal_slot, validator_index = find_upcoming_proposal_slot(spec, state)
    signed_prefs = build_signed_proposer_preferences(
        spec,
        state,
        proposal_slot=proposal_slot,
        validator_index=validator_index,
        fee_recipient=common_fee,
        target_gas_limit=parent_gas_limit,
    )
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        signed_proposer_preferences=signed_prefs,
        current_time_ms=time_ms,
    )
    assert result == "valid"
    assert reason is None
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_prefs),
            "expected": result,
        }
    )

    time_ms += 10
    parent_block_root = parent_signed_block.message.hash_tree_root()
    signed_envelope = build_signed_execution_payload_envelope(
        spec, state, parent_block_root, parent_signed_block
    )
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
    yield get_filename(signed_prefs), signed_prefs
    yield get_filename(signed_envelope), signed_envelope

    signed_bid = build_signed_bid(
        spec,
        state,
        builder_index=spec.BuilderIndex(0),
        slot=proposal_slot,
        parent_block_hash=signed_envelope.message.payload.block_hash,
        parent_block_root=parent_root,
        fee_recipient=common_fee,
        gas_limit=parent_gas_limit,
        value=spec.Gwei(1),
    )
    yield get_filename(signed_bid), signed_bid

    time_ms += 40
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        signed_execution_payload_bid=signed_bid,
        current_time_ms=time_ms,
    )
    assert result == "valid"
    assert reason is None
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_bid),
            "expected": result,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_execution_payload_bid__ignore_slot_too_far_future(spec, state):
    """A bid whose slot is far in the future is ignored."""
    yield "topic", "meta", "execution_payload_bid"

    store, blocks, parent_root = setup_store_with_block(spec, state)
    yield "state", state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    seen = get_seen(spec)
    far_slot = spec.Slot(state.slot + 100)
    signed_bid = build_signed_bid(
        spec,
        state,
        builder_index=spec.BuilderIndex(0),
        slot=far_slot,
        parent_block_hash=state.latest_block_hash,
        parent_block_root=parent_root,
        valid_signature=False,
    )
    yield get_filename(signed_bid), signed_bid

    time_ms = spec.compute_time_at_slot_ms(state, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 100
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        signed_execution_payload_bid=signed_bid,
        current_time_ms=time_ms,
    )
    assert result == "ignore"
    assert reason == "bid slot is not the current or next slot"
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_bid),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_execution_payload_bid__ignore_slot_outside_lower_disparity(spec, state):
    """A bid whose slot is 1ms before the lower clock-disparity edge is ignored."""
    yield "topic", "meta", "execution_payload_bid"

    store, blocks, parent_root = setup_store_with_block(spec, state)
    yield "state", state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    seen = get_seen(spec)
    bid_slot = spec.Slot(state.slot + 1)
    signed_bid = build_signed_bid(
        spec,
        state,
        builder_index=spec.BuilderIndex(0),
        slot=bid_slot,
        parent_block_hash=state.latest_block_hash,
        parent_block_root=parent_root,
        valid_signature=False,
    )
    yield get_filename(signed_bid), signed_bid

    # Lower edge: state.slot's start - MAXIMUM_GOSSIP_CLOCK_DISPARITY. One ms
    # before that places the bid outside the disparity window.
    time_ms = (
        spec.compute_time_at_slot_ms(state, spec.Slot(bid_slot - 1))
        - spec.config.MAXIMUM_GOSSIP_CLOCK_DISPARITY
        - 1
    )
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        signed_execution_payload_bid=signed_bid,
        current_time_ms=time_ms,
    )
    assert result == "ignore"
    assert reason == "bid slot is not the current or next slot"
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_bid),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_execution_payload_bid__valid_slot_at_lower_disparity(spec, state):
    """A bid whose slot lands exactly on the lower clock-disparity edge is valid."""
    yield "topic", "meta", "execution_payload_bid"

    store, blocks, parent_root = setup_store_advanced_for_bid(spec, state)
    activate_builders(spec, state)
    parent_signed_block = blocks[-1]
    yield "state", state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    seen = get_seen(spec)
    common_fee = spec.ExecutionAddress(b"\x11" * 20)
    parent_gas_limit = state.latest_execution_payload_bid.gas_limit
    bid_slot = spec.Slot(state.slot + 1)
    # Lower edge of the disparity window: (bid_slot - 1)'s start minus disparity.
    time_ms = (
        spec.compute_time_at_slot_ms(state, spec.Slot(bid_slot - 1))
        - spec.config.MAXIMUM_GOSSIP_CLOCK_DISPARITY
    )
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    proposal_slot, validator_index = find_upcoming_proposal_slot(spec, state)
    signed_prefs = build_signed_proposer_preferences(
        spec,
        state,
        proposal_slot=proposal_slot,
        validator_index=validator_index,
        fee_recipient=common_fee,
        target_gas_limit=parent_gas_limit,
    )
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        signed_proposer_preferences=signed_prefs,
        current_time_ms=time_ms,
    )
    assert result == "valid"
    assert reason is None
    yield get_filename(signed_prefs), signed_prefs
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_prefs),
            "expected": result,
        }
    )

    time_ms += 10
    parent_block_root = parent_signed_block.message.hash_tree_root()
    signed_envelope = build_signed_execution_payload_envelope(
        spec, state, parent_block_root, parent_signed_block
    )
    result, reason = run_validate_gossip(
        spec, seen=seen, store=store, state=state, signed_execution_payload_envelope=signed_envelope
    )
    assert result == "valid"
    assert reason is None
    yield get_filename(signed_envelope), signed_envelope
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_envelope),
            "expected": result,
        }
    )

    signed_bid = build_signed_bid(
        spec,
        state,
        builder_index=spec.BuilderIndex(0),
        slot=proposal_slot,
        parent_block_hash=signed_envelope.message.payload.block_hash,
        parent_block_root=parent_root,
        fee_recipient=common_fee,
        gas_limit=parent_gas_limit,
        value=spec.Gwei(1),
    )
    yield get_filename(signed_bid), signed_bid

    # Validate the bid exactly at the lower edge of the disparity window.
    time_ms = (
        spec.compute_time_at_slot_ms(state, spec.Slot(proposal_slot - 1))
        - spec.config.MAXIMUM_GOSSIP_CLOCK_DISPARITY
    )
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        signed_execution_payload_bid=signed_bid,
        current_time_ms=time_ms,
    )
    assert result == "valid"
    assert reason is None
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_bid),
            "expected": result,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_execution_payload_bid__valid_slot_at_upper_disparity(spec, state):
    """A bid whose slot lands exactly on the upper clock-disparity edge is valid."""
    yield "topic", "meta", "execution_payload_bid"

    store, blocks, parent_root = setup_store_advanced_for_bid(spec, state)
    activate_builders(spec, state)
    parent_signed_block = blocks[-1]
    yield "state", state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    seen = get_seen(spec)
    common_fee = spec.ExecutionAddress(b"\x11" * 20)
    parent_gas_limit = state.latest_execution_payload_bid.gas_limit
    time_ms = spec.compute_time_at_slot_ms(state, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    proposal_slot, validator_index = find_upcoming_proposal_slot(spec, state)
    signed_prefs = build_signed_proposer_preferences(
        spec,
        state,
        proposal_slot=proposal_slot,
        validator_index=validator_index,
        fee_recipient=common_fee,
        target_gas_limit=parent_gas_limit,
    )
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        signed_proposer_preferences=signed_prefs,
        current_time_ms=time_ms,
    )
    assert result == "valid"
    assert reason is None
    yield get_filename(signed_prefs), signed_prefs
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_prefs),
            "expected": result,
        }
    )

    time_ms += 10
    parent_block_root = parent_signed_block.message.hash_tree_root()
    signed_envelope = build_signed_execution_payload_envelope(
        spec, state, parent_block_root, parent_signed_block
    )
    result, reason = run_validate_gossip(
        spec, seen=seen, store=store, state=state, signed_execution_payload_envelope=signed_envelope
    )
    assert result == "valid"
    assert reason is None
    yield get_filename(signed_envelope), signed_envelope
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_envelope),
            "expected": result,
        }
    )

    signed_bid = build_signed_bid(
        spec,
        state,
        builder_index=spec.BuilderIndex(0),
        slot=proposal_slot,
        parent_block_hash=signed_envelope.message.payload.block_hash,
        parent_block_root=parent_root,
        fee_recipient=common_fee,
        gas_limit=parent_gas_limit,
        value=spec.Gwei(1),
    )
    yield get_filename(signed_bid), signed_bid

    # Validate the bid exactly at the upper edge of the disparity window.
    time_ms = (
        spec.compute_time_at_slot_ms(state, spec.Slot(proposal_slot + 1))
        + spec.config.MAXIMUM_GOSSIP_CLOCK_DISPARITY
    )
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        signed_execution_payload_bid=signed_bid,
        current_time_ms=time_ms,
    )
    assert result == "valid"
    assert reason is None
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_bid),
            "expected": result,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_execution_payload_bid__ignore_slot_outside_upper_disparity(spec, state):
    """A bid whose slot is 1ms past the upper clock-disparity edge is ignored."""
    yield "topic", "meta", "execution_payload_bid"

    store, blocks, parent_root = setup_store_with_block(spec, state)
    yield "state", state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    seen = get_seen(spec)
    bid_slot = spec.Slot(state.slot + 1)
    signed_bid = build_signed_bid(
        spec,
        state,
        builder_index=spec.BuilderIndex(0),
        slot=bid_slot,
        parent_block_hash=state.latest_block_hash,
        parent_block_root=parent_root,
        valid_signature=False,
    )
    yield get_filename(signed_bid), signed_bid

    # Upper edge: (bid_slot + 1)'s start + MAXIMUM_GOSSIP_CLOCK_DISPARITY. One
    # ms past that places the bid outside the disparity window.
    time_ms = (
        spec.compute_time_at_slot_ms(state, spec.Slot(bid_slot + 1))
        + spec.config.MAXIMUM_GOSSIP_CLOCK_DISPARITY
        + 1
    )
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        signed_execution_payload_bid=signed_bid,
        current_time_ms=time_ms,
    )
    assert result == "ignore"
    assert reason == "bid slot is not the current or next slot"
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_bid),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_execution_payload_bid__ignore_duplicate_from_builder(spec, state):
    """A second bid from the same builder for the same slot is ignored."""
    yield "topic", "meta", "execution_payload_bid"

    store, blocks, parent_root = setup_store_with_block(spec, state)
    yield "state", state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    seen = get_seen(spec)
    next_slot_value = spec.Slot(state.slot + 1)
    builder_index = spec.BuilderIndex(0)
    signed_bid = build_signed_bid(
        spec,
        state,
        builder_index=builder_index,
        slot=next_slot_value,
        parent_block_hash=state.latest_block_hash,
        parent_block_root=parent_root,
        valid_signature=False,
    )
    # Prepopulate seen so the bid is treated as a duplicate.
    seen.execution_payload_bids.add((builder_index, next_slot_value))

    yield get_filename(signed_bid), signed_bid

    time_ms = spec.compute_time_at_slot_ms(state, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 100
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        signed_execution_payload_bid=signed_bid,
        current_time_ms=time_ms,
    )
    assert result == "ignore"
    assert reason == "already seen valid bid from this builder for this slot"
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_bid),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_execution_payload_bid__ignore_not_highest_value(spec, state):
    """A bid whose value does not exceed the best bid for this slot/parent is ignored."""
    yield "topic", "meta", "execution_payload_bid"

    store, blocks, parent_root = setup_store_with_block(spec, state)
    yield "state", state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    seen = get_seen(spec)
    next_slot_value = spec.Slot(state.slot + 1)
    builder_index = spec.BuilderIndex(0)
    parent_hash = state.latest_block_hash
    signed_bid = build_signed_bid(
        spec,
        state,
        builder_index=builder_index,
        slot=next_slot_value,
        parent_block_hash=parent_hash,
        parent_block_root=parent_root,
        value=spec.Gwei(10),
        valid_signature=False,
    )
    # Prepopulate the best-bid cache with a higher value.
    seen.best_execution_payload_bid[(next_slot_value, parent_hash, parent_root)] = spec.Gwei(100)

    yield get_filename(signed_bid), signed_bid

    time_ms = spec.compute_time_at_slot_ms(state, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 100
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        signed_execution_payload_bid=signed_bid,
        current_time_ms=time_ms,
    )
    assert result == "ignore"
    assert reason == "bid is not the highest value bid seen for this slot and parent"
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_bid),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_execution_payload_bid__reject_builder_index_out_of_range(spec, state):
    """A bid whose builder_index is past the builder registry is rejected."""
    yield "topic", "meta", "execution_payload_bid"

    store, blocks, parent_root = setup_store_with_block(spec, state)
    yield "state", state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    seen = get_seen(spec)
    next_slot_value = spec.Slot(state.slot + 1)
    out_of_range_index = spec.BuilderIndex(len(state.builders))
    signed_bid = build_signed_bid(
        spec,
        state,
        builder_index=out_of_range_index,
        slot=next_slot_value,
        parent_block_hash=state.latest_block_hash,
        parent_block_root=parent_root,
        value=spec.Gwei(1),
        valid_signature=False,
    )
    yield get_filename(signed_bid), signed_bid

    time_ms = spec.compute_time_at_slot_ms(state, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 100
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        signed_execution_payload_bid=signed_bid,
        current_time_ms=time_ms,
    )
    assert result == "reject"
    assert reason == "builder index out of range"
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_bid),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_execution_payload_bid__ignore_builder_cannot_cover(spec, state):
    """A bid whose value exceeds what the builder can cover is ignored."""
    yield "topic", "meta", "execution_payload_bid"

    store, blocks, parent_root = setup_store_with_block(spec, state)
    yield "state", state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    seen = get_seen(spec)
    next_slot_value = spec.Slot(state.slot + 1)
    builder_index = spec.BuilderIndex(0)
    # Zero out the builder's balance so it cannot cover even a tiny bid.
    state.builders[builder_index].balance = spec.Gwei(0)
    signed_bid = build_signed_bid(
        spec,
        state,
        builder_index=builder_index,
        slot=next_slot_value,
        parent_block_hash=state.latest_block_hash,
        parent_block_root=parent_root,
        value=spec.Gwei(1),
        valid_signature=False,
    )
    yield get_filename(signed_bid), signed_bid

    time_ms = spec.compute_time_at_slot_ms(state, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 100
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        signed_execution_payload_bid=signed_bid,
        current_time_ms=time_ms,
    )
    assert result == "ignore"
    assert reason == "builder cannot cover bid value"
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_bid),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_execution_payload_bid__reject_execution_payment_nonzero(spec, state):
    """A bid whose execution_payment is non-zero is rejected."""
    yield "topic", "meta", "execution_payload_bid"

    store, blocks, parent_root = setup_store_with_block(spec, state)
    yield "state", state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    seen = get_seen(spec)
    next_slot_value = spec.Slot(state.slot + 1)
    builder_index = spec.BuilderIndex(0)
    signed_bid = build_signed_bid(
        spec,
        state,
        builder_index=builder_index,
        slot=next_slot_value,
        parent_block_hash=state.latest_block_hash,
        parent_block_root=parent_root,
        value=spec.Gwei(1),
        execution_payment=spec.Gwei(1),
        valid_signature=False,
    )
    yield get_filename(signed_bid), signed_bid

    time_ms = spec.compute_time_at_slot_ms(state, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 100
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        signed_execution_payload_bid=signed_bid,
        current_time_ms=time_ms,
    )
    assert result == "reject"
    assert reason == "bid's execution payment must be zero"
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_bid),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_execution_payload_bid__reject_builder_not_active(spec, state):
    """A bid from an inactive builder is rejected."""
    yield "topic", "meta", "execution_payload_bid"

    store, blocks, parent_root = setup_store_with_block(spec, state)
    yield "state", state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    seen = get_seen(spec)
    next_slot_value = spec.Slot(state.slot + 1)
    builder_index = spec.BuilderIndex(0)
    # At genesis builder.deposit_epoch (0) is not less than the finalized epoch (0),
    # so is_active_builder returns False.
    assert not spec.is_active_builder(state, builder_index)
    signed_bid = build_signed_bid(
        spec,
        state,
        builder_index=builder_index,
        slot=next_slot_value,
        parent_block_hash=state.latest_block_hash,
        parent_block_root=parent_root,
        value=spec.Gwei(1),
        valid_signature=False,
    )
    yield get_filename(signed_bid), signed_bid

    time_ms = spec.compute_time_at_slot_ms(state, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 100
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        signed_execution_payload_bid=signed_bid,
        current_time_ms=time_ms,
    )
    assert result == "reject"
    assert reason == "builder is not active"
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_bid),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_execution_payload_bid__reject_too_many_blobs(spec, state):
    """A bid whose blob KZG commitment count exceeds the per-epoch limit is rejected."""
    yield "topic", "meta", "execution_payload_bid"

    store, blocks, parent_root = setup_store_with_block(spec, state)
    activate_builders(spec, state)
    yield "state", state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    seen = get_seen(spec)
    next_slot_value = spec.Slot(state.slot + 1)
    builder_index = spec.BuilderIndex(0)
    signed_bid = build_signed_bid(
        spec,
        state,
        builder_index=builder_index,
        slot=next_slot_value,
        parent_block_hash=state.latest_block_hash,
        parent_block_root=parent_root,
        value=spec.Gwei(1),
        valid_signature=False,
    )
    # Overfill blob commitments above the per-epoch limit.
    max_blobs = spec.get_blob_parameters(
        spec.compute_epoch_at_slot(next_slot_value)
    ).max_blobs_per_block
    over_limit = int(max_blobs) + 1
    signed_bid.message.blob_kzg_commitments = spec.List[
        spec.KZGCommitment, spec.MAX_BLOB_COMMITMENTS_PER_BLOCK
    ](*([spec.KZGCommitment()] * over_limit))
    yield get_filename(signed_bid), signed_bid

    time_ms = spec.compute_time_at_slot_ms(state, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 100
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        signed_execution_payload_bid=signed_bid,
        current_time_ms=time_ms,
    )
    assert result == "reject"
    assert reason == "too many blob kzg commitments"
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_bid),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_execution_payload_bid__ignore_parent_block_unknown(spec, state):
    """A bid whose parent_block_root is not in store.blocks is ignored."""
    yield "topic", "meta", "execution_payload_bid"

    store, blocks, _ = setup_store_with_block(spec, state)
    activate_builders(spec, state)
    yield "state", state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    seen = get_seen(spec)
    next_slot_value = spec.Slot(state.slot + 1)
    builder_index = spec.BuilderIndex(0)
    unknown_root = spec.Root(b"\xab" * 32)
    signed_bid = build_signed_bid(
        spec,
        state,
        builder_index=builder_index,
        slot=next_slot_value,
        parent_block_hash=state.latest_block_hash,
        parent_block_root=unknown_root,
        value=spec.Gwei(1),
        valid_signature=False,
    )
    yield get_filename(signed_bid), signed_bid

    time_ms = spec.compute_time_at_slot_ms(state, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 100
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        signed_execution_payload_bid=signed_bid,
        current_time_ms=time_ms,
    )
    assert result == "ignore"
    assert reason == "bid's parent block root is not a known beacon block"
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_bid),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_execution_payload_bid__ignore_parent_block_hash_unknown(spec, state):
    """A bid whose parent_block_hash is not in seen.execution_payloads is ignored."""
    yield "topic", "meta", "execution_payload_bid"

    store, blocks, parent_root = setup_store_with_block(spec, state)
    activate_builders(spec, state)
    yield "state", state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    seen = get_seen(spec)
    next_slot_value = spec.Slot(state.slot + 1)
    builder_index = spec.BuilderIndex(0)
    unknown_hash = spec.Hash32(b"\xcd" * 32)
    signed_bid = build_signed_bid(
        spec,
        state,
        builder_index=builder_index,
        slot=next_slot_value,
        parent_block_hash=unknown_hash,
        parent_block_root=parent_root,
        value=spec.Gwei(1),
        valid_signature=False,
    )
    yield get_filename(signed_bid), signed_bid

    time_ms = spec.compute_time_at_slot_ms(state, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 100
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        signed_execution_payload_bid=signed_bid,
        current_time_ms=time_ms,
    )
    assert result == "ignore"
    assert reason == "bid's parent block hash is not a known execution payload"
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_bid),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_execution_payload_bid__ignore_parent_state_unavailable(spec, state):
    """A bid whose parent block's state is missing from the store is ignored."""
    yield "topic", "meta", "execution_payload_bid"

    store, blocks, parent_root = setup_store_with_block(spec, state)
    activate_builders(spec, state)
    yield "state", state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    seen = get_seen(spec)
    # Mark the parent block's payload as known but drop its state.
    seen.execution_payloads[state.latest_block_hash] = state.latest_execution_payload_bid
    del store.block_states[parent_root]

    next_slot_value = spec.Slot(state.slot + 1)
    builder_index = spec.BuilderIndex(0)
    signed_bid = build_signed_bid(
        spec,
        state,
        builder_index=builder_index,
        slot=next_slot_value,
        parent_block_hash=state.latest_block_hash,
        parent_block_root=parent_root,
        value=spec.Gwei(1),
        valid_signature=False,
    )
    yield get_filename(signed_bid), signed_bid

    time_ms = spec.compute_time_at_slot_ms(state, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 100
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        signed_execution_payload_bid=signed_bid,
        current_time_ms=time_ms,
    )
    assert result == "ignore"
    assert reason == "bid's parent block state is unavailable"
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_bid),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_execution_payload_bid__ignore_preferences_not_seen(spec, state):
    """A bid whose matching proposer preferences have not been seen is ignored."""
    yield "topic", "meta", "execution_payload_bid"

    # get_proposer_dependent_root subtracts MIN_SEED_LOOKAHEAD from the epoch,
    # so the parent state must already be at least MIN_SEED_LOOKAHEAD + 1 epochs
    # in for the lookup to land on a non-underflowing slot.
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    blocks = [signed_anchor]
    target_slot = spec.compute_start_slot_at_epoch(spec.Epoch(spec.MIN_SEED_LOOKAHEAD + 1))
    while state.slot < target_slot:
        block = build_empty_block_for_next_slot(spec, state)
        signed_block = state_transition_and_sign_block(spec, state, block)
        block_root = signed_block.message.hash_tree_root()
        store.blocks[block_root] = signed_block.message
        store.block_states[block_root] = state.copy()
        blocks.append(signed_block)
    parent_root = blocks[-1].message.hash_tree_root()
    activate_builders(spec, state)
    yield "state", state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    seen = get_seen(spec)
    # Seed the parent payload, but leave seen.proposer_preferences empty.
    seen.execution_payloads[state.latest_block_hash] = state.latest_execution_payload_bid

    next_slot_value = spec.Slot(state.slot + 1)
    builder_index = spec.BuilderIndex(0)
    signed_bid = build_signed_bid(
        spec,
        state,
        builder_index=builder_index,
        slot=next_slot_value,
        parent_block_hash=state.latest_block_hash,
        parent_block_root=parent_root,
        value=spec.Gwei(1),
        valid_signature=False,
    )
    yield get_filename(signed_bid), signed_bid

    time_ms = spec.compute_time_at_slot_ms(state, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 100
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        signed_execution_payload_bid=signed_bid,
        current_time_ms=time_ms,
    )
    assert result == "ignore"
    assert reason == "matching proposer preferences have not been seen"
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_bid),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_execution_payload_bid__reject_fee_recipient_mismatch(spec, state):
    """A bid whose fee_recipient does not match the proposer's preference is rejected."""
    yield "topic", "meta", "execution_payload_bid"

    store, blocks, parent_root = setup_store_advanced_for_bid(spec, state)
    activate_builders(spec, state)
    parent_signed_block = blocks[-1]
    yield "state", state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    seen = get_seen(spec)
    time_ms = spec.compute_time_at_slot_ms(state, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    bid_fee = spec.ExecutionAddress(b"\xaa" * 20)
    prefs_fee = spec.ExecutionAddress(b"\xbb" * 20)
    parent_gas_limit = state.latest_execution_payload_bid.gas_limit
    time_ms += 50
    proposal_slot, validator_index = find_upcoming_proposal_slot(spec, state)
    signed_prefs = build_signed_proposer_preferences(
        spec,
        state,
        proposal_slot=proposal_slot,
        validator_index=validator_index,
        fee_recipient=prefs_fee,
        target_gas_limit=parent_gas_limit,
    )
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        signed_proposer_preferences=signed_prefs,
        current_time_ms=time_ms,
    )
    assert result == "valid"
    assert reason is None
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_prefs),
            "expected": result,
        }
    )

    time_ms += 10
    parent_block_root = parent_signed_block.message.hash_tree_root()
    signed_envelope = build_signed_execution_payload_envelope(
        spec, state, parent_block_root, parent_signed_block
    )
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
    yield get_filename(signed_prefs), signed_prefs
    yield get_filename(signed_envelope), signed_envelope

    signed_bid = build_signed_bid(
        spec,
        state,
        builder_index=spec.BuilderIndex(0),
        slot=proposal_slot,
        parent_block_hash=signed_envelope.message.payload.block_hash,
        parent_block_root=parent_root,
        fee_recipient=bid_fee,
        gas_limit=parent_gas_limit,
        value=spec.Gwei(1),
        valid_signature=False,
    )
    yield get_filename(signed_bid), signed_bid

    time_ms += 40
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        signed_execution_payload_bid=signed_bid,
        current_time_ms=time_ms,
    )
    assert result == "reject"
    assert reason == "bid's fee recipient does not match the proposer's preference"
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_bid),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_execution_payload_bid__ignore_gas_limit_incompatible(spec, state):
    """A bid whose gas_limit is incompatible with the proposer's target is ignored."""
    yield "topic", "meta", "execution_payload_bid"

    store, blocks, parent_root = setup_store_advanced_for_bid(spec, state)
    activate_builders(spec, state)
    parent_signed_block = blocks[-1]
    yield "state", state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    seen = get_seen(spec)
    time_ms = spec.compute_time_at_slot_ms(state, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    common_fee = spec.ExecutionAddress(b"\x11" * 20)
    parent_gas_limit = state.latest_execution_payload_bid.gas_limit
    time_ms += 50
    proposal_slot, validator_index = find_upcoming_proposal_slot(spec, state)
    signed_prefs = build_signed_proposer_preferences(
        spec,
        state,
        proposal_slot=proposal_slot,
        validator_index=validator_index,
        fee_recipient=common_fee,
        target_gas_limit=parent_gas_limit,
    )
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        signed_proposer_preferences=signed_prefs,
        current_time_ms=time_ms,
    )
    assert result == "valid"
    assert reason is None
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_prefs),
            "expected": result,
        }
    )

    time_ms += 10
    parent_block_root = parent_signed_block.message.hash_tree_root()
    signed_envelope = build_signed_execution_payload_envelope(
        spec, state, parent_block_root, parent_signed_block
    )
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
    yield get_filename(signed_prefs), signed_prefs
    yield get_filename(signed_envelope), signed_envelope

    # Pick a gas_limit far outside the EIP-1559 step from parent.
    incompatible_gas_limit = spec.uint64(int(parent_gas_limit) + 1_000_000)
    signed_bid = build_signed_bid(
        spec,
        state,
        builder_index=spec.BuilderIndex(0),
        slot=proposal_slot,
        parent_block_hash=signed_envelope.message.payload.block_hash,
        parent_block_root=parent_root,
        fee_recipient=common_fee,
        gas_limit=incompatible_gas_limit,
        value=spec.Gwei(1),
        valid_signature=False,
    )
    yield get_filename(signed_bid), signed_bid

    time_ms += 40
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        signed_execution_payload_bid=signed_bid,
        current_time_ms=time_ms,
    )
    assert result == "ignore"
    assert reason == "bid gas limit is not compatible with the proposer's target"
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_bid),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_execution_payload_bid__reject_invalid_signature(spec, state):
    """A bid with an invalid signature is rejected once all other checks pass."""
    yield "topic", "meta", "execution_payload_bid"

    store, blocks, parent_root = setup_store_advanced_for_bid(spec, state)
    activate_builders(spec, state)
    parent_signed_block = blocks[-1]
    yield "state", state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    seen = get_seen(spec)
    time_ms = spec.compute_time_at_slot_ms(state, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    common_fee = spec.ExecutionAddress(b"\x11" * 20)
    parent_gas_limit = state.latest_execution_payload_bid.gas_limit
    time_ms += 50
    proposal_slot, validator_index = find_upcoming_proposal_slot(spec, state)
    signed_prefs = build_signed_proposer_preferences(
        spec,
        state,
        proposal_slot=proposal_slot,
        validator_index=validator_index,
        fee_recipient=common_fee,
        target_gas_limit=parent_gas_limit,
    )
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        signed_proposer_preferences=signed_prefs,
        current_time_ms=time_ms,
    )
    assert result == "valid"
    assert reason is None
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_prefs),
            "expected": result,
        }
    )

    time_ms += 10
    parent_block_root = parent_signed_block.message.hash_tree_root()
    signed_envelope = build_signed_execution_payload_envelope(
        spec, state, parent_block_root, parent_signed_block
    )
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
    yield get_filename(signed_prefs), signed_prefs
    yield get_filename(signed_envelope), signed_envelope

    signed_bid = build_signed_bid(
        spec,
        state,
        builder_index=spec.BuilderIndex(0),
        slot=proposal_slot,
        parent_block_hash=signed_envelope.message.payload.block_hash,
        parent_block_root=parent_root,
        fee_recipient=common_fee,
        gas_limit=parent_gas_limit,
        value=spec.Gwei(1),
        valid_signature=False,
    )
    yield get_filename(signed_bid), signed_bid

    time_ms += 40
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        signed_execution_payload_bid=signed_bid,
        current_time_ms=time_ms,
    )
    assert result == "reject"
    assert reason == "invalid bid signature"
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_bid),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


def _run_bid_gas_limit_scenario(
    spec,
    state,
    parent_gas_limit,
    bid_gas_limit,
    target_gas_limit,
    expected_result,
    expected_reason,
):
    """
    Drive a full bid gossip validation with a specific (parent, bid, target)
    gas_limit triple and assert the expected outcome. Yields the standard
    bid-gossip reference fixture (state, blocks, seeded prefs + envelope,
    bid, messages).
    """
    yield "topic", "meta", "execution_payload_bid"

    store, blocks, parent_root = setup_store_advanced_for_bid(spec, state)
    activate_builders(spec, state)
    parent_signed_block = blocks[-1]
    # Override the parent's bid gas_limit so the envelope's payload.gas_limit
    # (which gets seeded into seen.execution_payloads) equals our target value.
    state.latest_execution_payload_bid.gas_limit = spec.uint64(parent_gas_limit)
    yield "state", state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    seen = get_seen(spec)
    time_ms = spec.compute_time_at_slot_ms(state, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []
    common_fee = spec.ExecutionAddress(b"\x11" * 20)

    time_ms += 50
    proposal_slot, validator_index = find_upcoming_proposal_slot(spec, state)
    signed_prefs = build_signed_proposer_preferences(
        spec,
        state,
        proposal_slot=proposal_slot,
        validator_index=validator_index,
        fee_recipient=common_fee,
        target_gas_limit=spec.uint64(target_gas_limit),
    )
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        signed_proposer_preferences=signed_prefs,
        current_time_ms=time_ms,
    )
    assert result == "valid"
    assert reason is None
    yield get_filename(signed_prefs), signed_prefs
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_prefs),
            "expected": result,
        }
    )

    time_ms += 10
    parent_block_root = parent_signed_block.message.hash_tree_root()
    signed_envelope = build_signed_execution_payload_envelope(
        spec, state, parent_block_root, parent_signed_block
    )
    assert signed_envelope.message.payload.gas_limit == parent_gas_limit
    result, reason = run_validate_gossip(
        spec, seen=seen, store=store, state=state, signed_execution_payload_envelope=signed_envelope
    )
    assert result == "valid"
    assert reason is None
    yield get_filename(signed_envelope), signed_envelope
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_envelope),
            "expected": result,
        }
    )

    signed_bid = build_signed_bid(
        spec,
        state,
        builder_index=spec.BuilderIndex(0),
        slot=proposal_slot,
        parent_block_hash=signed_envelope.message.payload.block_hash,
        parent_block_root=parent_root,
        fee_recipient=common_fee,
        gas_limit=spec.uint64(bid_gas_limit),
        value=spec.Gwei(1),
        valid_signature=(expected_result == "valid"),
    )
    yield get_filename(signed_bid), signed_bid

    time_ms += 40
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        signed_execution_payload_bid=signed_bid,
        current_time_ms=time_ms,
    )
    assert result == expected_result
    assert reason == expected_reason
    entry = {
        "current_time_ms": int(time_ms),
        "message": get_filename(signed_bid),
        "expected": result,
    }
    if reason is not None:
        entry["reason"] = reason
    messages.append(entry)

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_execution_payload_bid__valid_gas_limit_increase_within_limit(spec, state):
    """A bid with gas_limit raised within the EIP-1559 step toward target is valid."""
    yield from _run_bid_gas_limit_scenario(
        spec,
        state,
        parent_gas_limit=60_000_000,
        bid_gas_limit=60_000_100,
        target_gas_limit=60_000_100,
        expected_result="valid",
        expected_reason=None,
    )


@with_gloas_and_later
@spec_state_test
def test_gossip_execution_payload_bid__valid_gas_limit_increase_exceeding_limit(spec, state):
    """When target is above the EIP-1559 max, a bid pinned to the max value is valid."""
    # max_gas_limit_difference = 60_000_000 // 1024 - 1 = 58_592
    yield from _run_bid_gas_limit_scenario(
        spec,
        state,
        parent_gas_limit=60_000_000,
        bid_gas_limit=60_058_592,
        target_gas_limit=100_000_000,
        expected_result="valid",
        expected_reason=None,
    )


@with_gloas_and_later
@spec_state_test
def test_gossip_execution_payload_bid__ignore_gas_limit_increase_exceeding_limit_off_by_one(
    spec, state
):
    """A bid one over the EIP-1559 max (when target is above the max) is ignored."""
    yield from _run_bid_gas_limit_scenario(
        spec,
        state,
        parent_gas_limit=60_000_000,
        bid_gas_limit=60_058_593,
        target_gas_limit=100_000_000,
        expected_result="ignore",
        expected_reason="bid gas limit is not compatible with the proposer's target",
    )


@with_gloas_and_later
@spec_state_test
def test_gossip_execution_payload_bid__valid_gas_limit_decrease_within_limit(spec, state):
    """A bid with gas_limit lowered within the EIP-1559 step toward target is valid."""
    yield from _run_bid_gas_limit_scenario(
        spec,
        state,
        parent_gas_limit=60_000_000,
        bid_gas_limit=59_999_990,
        target_gas_limit=59_999_990,
        expected_result="valid",
        expected_reason=None,
    )


@with_gloas_and_later
@spec_state_test
def test_gossip_execution_payload_bid__valid_gas_limit_decrease_exceeding_limit(spec, state):
    """When target is below the EIP-1559 min, a bid pinned to the min value is valid."""
    yield from _run_bid_gas_limit_scenario(
        spec,
        state,
        parent_gas_limit=60_000_000,
        bid_gas_limit=59_941_408,
        target_gas_limit=30_000_000,
        expected_result="valid",
        expected_reason=None,
    )


@with_gloas_and_later
@spec_state_test
def test_gossip_execution_payload_bid__ignore_gas_limit_decrease_exceeding_limit_off_by_one(
    spec, state
):
    """A bid one under the EIP-1559 min (when target is below the min) is ignored."""
    yield from _run_bid_gas_limit_scenario(
        spec,
        state,
        parent_gas_limit=60_000_000,
        bid_gas_limit=59_941_407,
        target_gas_limit=30_000_000,
        expected_result="ignore",
        expected_reason="bid gas limit is not compatible with the proposer's target",
    )


@with_gloas_and_later
@spec_state_test
def test_gossip_execution_payload_bid__valid_gas_limit_target_equals_parent(spec, state):
    """A bid whose gas_limit equals both target and parent gas_limit is valid."""
    yield from _run_bid_gas_limit_scenario(
        spec,
        state,
        parent_gas_limit=60_000_000,
        bid_gas_limit=60_000_000,
        target_gas_limit=60_000_000,
        expected_result="valid",
        expected_reason=None,
    )


@with_gloas_and_later
@spec_state_test
def test_gossip_execution_payload_bid__valid_gas_limit_parent_under_step(spec, state):
    """A bid is valid when parent gas_limit is below the 1024 step (step floors to 1)."""
    yield from _run_bid_gas_limit_scenario(
        spec,
        state,
        parent_gas_limit=1023,
        bid_gas_limit=1023,
        target_gas_limit=60_000_000,
        expected_result="valid",
        expected_reason=None,
    )
