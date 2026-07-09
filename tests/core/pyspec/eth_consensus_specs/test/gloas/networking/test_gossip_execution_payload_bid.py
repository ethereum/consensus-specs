from eth_consensus_specs.test.context import (
    spec_state_test,
    with_gloas_and_later,
)
from eth_consensus_specs.test.helpers.block import build_empty_block_for_next_slot
from eth_consensus_specs.test.helpers.execution_payload import (
    build_signed_execution_payload_envelope,
)
from eth_consensus_specs.test.helpers.gloas.bid import (
    activate_builders,
    build_signed_bid,
    setup_store_advanced_for_bid,
    setup_store_finalized_with_pending_payment,
)
from eth_consensus_specs.test.helpers.gloas.proposer_preferences import (
    build_signed_proposer_preferences,
    find_upcoming_proposal_slot,
)
from eth_consensus_specs.test.helpers.gossip import (
    add_pending_block_to_store,
    get_filename,
    get_seen,
    run_validate_gossip,
)
from eth_consensus_specs.test.helpers.state import (
    state_transition_and_sign_block,
)


def _seed_bid_context(
    spec, state, store, blocks, parent_root, messages, time_ms, seed_prefs=True, seed_envelope=True
):
    """
    Yield and validate the proposer preferences and payload envelope messages
    that seed ``seen`` for a fully valid bid, appending their entries to
    ``messages``.

    Together with an advanced store and active builders, this satisfies every
    bid validation condition, so tests can flip exactly the one condition
    under test. The expected outcome then does not depend on the order in
    which a client checks independent conditions.

    Returns (seen, common_fee, parent_gas_limit, proposal_slot, parent_block_hash, time_ms).
    """
    seen = get_seen(spec)
    common_fee = spec.ExecutionAddress(b"\x11" * 20)
    # A target_gas_limit equal to the parent's payload gas_limit makes the
    # is_gas_limit_target_compatible check accept bid.gas_limit == target.
    parent_gas_limit = state.latest_execution_payload_bid.gas_limit
    parent_block_hash = state.latest_execution_payload_bid.block_hash
    proposal_slot, validator_index = find_upcoming_proposal_slot(spec, state)

    if seed_prefs:
        time_ms += 50
        signed_prefs = build_signed_proposer_preferences(
            spec,
            state,
            proposal_slot=proposal_slot,
            validator_index=validator_index,
            fee_recipient=common_fee,
            target_gas_limit=parent_gas_limit,
        )
        yield get_filename(signed_prefs), signed_prefs
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

    if seed_envelope:
        time_ms += 10
        parent_signed_block = blocks[-1]
        signed_envelope = build_signed_execution_payload_envelope(
            spec, state, parent_root, parent_signed_block
        )
        assert signed_envelope.message.payload.block_hash == parent_block_hash
        yield get_filename(signed_envelope), signed_envelope
        result, reason = run_validate_gossip(
            spec,
            seen=seen,
            store=store,
            state=state,
            signed_execution_payload_envelope=signed_envelope,
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

    return seen, common_fee, parent_gas_limit, proposal_slot, parent_block_hash, time_ms


@with_gloas_and_later
@spec_state_test
def test_gossip_execution_payload_bid__valid(spec, state):
    """A bid for the next slot from an active builder with matching preferences is valid."""
    anchor_state = state.copy()
    yield "topic", "meta", "execution_payload_bid"

    store, blocks, parent_root = setup_store_advanced_for_bid(spec, state)
    finalized_checkpoint_meta = activate_builders(spec, state, store, blocks)
    yield "state", anchor_state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]
    yield "finalized_checkpoint", "meta", finalized_checkpoint_meta

    time_ms = spec.compute_time_at_slot_ms(state, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []
    seen, common_fee, parent_gas_limit, proposal_slot, parent_block_hash, time_ms = yield from (
        _seed_bid_context(spec, state, store, blocks, parent_root, messages, time_ms)
    )

    signed_bid = build_signed_bid(
        spec,
        state,
        builder_index=spec.BuilderIndex(0),
        slot=proposal_slot,
        parent_block_hash=parent_block_hash,
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
    anchor_state = state.copy()
    yield "topic", "meta", "execution_payload_bid"

    store, blocks, parent_root = setup_store_advanced_for_bid(spec, state)
    finalized_checkpoint_meta = activate_builders(spec, state, store, blocks)
    yield "state", anchor_state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]
    yield "finalized_checkpoint", "meta", finalized_checkpoint_meta

    time_ms = spec.compute_time_at_slot_ms(state, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []
    seen, common_fee, parent_gas_limit, _, parent_block_hash, time_ms = yield from (
        _seed_bid_context(spec, state, store, blocks, parent_root, messages, time_ms)
    )

    far_slot = spec.Slot(state.slot + 100)
    signed_bid = build_signed_bid(
        spec,
        state,
        builder_index=spec.BuilderIndex(0),
        slot=far_slot,
        parent_block_hash=parent_block_hash,
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
    anchor_state = state.copy()
    yield "topic", "meta", "execution_payload_bid"

    store, blocks, parent_root = setup_store_advanced_for_bid(spec, state)
    finalized_checkpoint_meta = activate_builders(spec, state, store, blocks)
    yield "state", anchor_state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]
    yield "finalized_checkpoint", "meta", finalized_checkpoint_meta

    # Lower edge: (bid_slot - 1)'s start - MAXIMUM_GOSSIP_CLOCK_DISPARITY. One
    # ms before that places the bid outside the disparity window. The seeding
    # messages are validated shortly before the edge.
    bid_slot = spec.Slot(state.slot + 1)
    edge_time_ms = (
        spec.compute_time_at_slot_ms(state, spec.Slot(bid_slot - 1))
        - spec.config.MAXIMUM_GOSSIP_CLOCK_DISPARITY
        - 1
    )
    time_ms = edge_time_ms - 100
    yield "current_time_ms", "meta", int(time_ms)
    messages = []
    seen, common_fee, parent_gas_limit, proposal_slot, parent_block_hash, time_ms = yield from (
        _seed_bid_context(spec, state, store, blocks, parent_root, messages, time_ms)
    )
    assert proposal_slot == bid_slot

    signed_bid = build_signed_bid(
        spec,
        state,
        builder_index=spec.BuilderIndex(0),
        slot=bid_slot,
        parent_block_hash=parent_block_hash,
        parent_block_root=parent_root,
        fee_recipient=common_fee,
        gas_limit=parent_gas_limit,
        value=spec.Gwei(1),
    )
    yield get_filename(signed_bid), signed_bid

    time_ms = edge_time_ms
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
    anchor_state = state.copy()
    yield "topic", "meta", "execution_payload_bid"

    store, blocks, parent_root = setup_store_advanced_for_bid(spec, state)
    finalized_checkpoint_meta = activate_builders(spec, state, store, blocks)
    parent_signed_block = blocks[-1]
    yield "state", anchor_state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]
    yield "finalized_checkpoint", "meta", finalized_checkpoint_meta

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
    yield get_filename(signed_prefs), signed_prefs
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
    yield get_filename(signed_envelope), signed_envelope
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
    anchor_state = state.copy()
    yield "topic", "meta", "execution_payload_bid"

    store, blocks, parent_root = setup_store_advanced_for_bid(spec, state)
    finalized_checkpoint_meta = activate_builders(spec, state, store, blocks)
    parent_signed_block = blocks[-1]
    yield "state", anchor_state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]
    yield "finalized_checkpoint", "meta", finalized_checkpoint_meta

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
    yield get_filename(signed_prefs), signed_prefs
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
    yield get_filename(signed_envelope), signed_envelope
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
    anchor_state = state.copy()
    yield "topic", "meta", "execution_payload_bid"

    store, blocks, parent_root = setup_store_advanced_for_bid(spec, state)
    finalized_checkpoint_meta = activate_builders(spec, state, store, blocks)
    yield "state", anchor_state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]
    yield "finalized_checkpoint", "meta", finalized_checkpoint_meta

    time_ms = spec.compute_time_at_slot_ms(state, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []
    seen, common_fee, parent_gas_limit, proposal_slot, parent_block_hash, time_ms = yield from (
        _seed_bid_context(spec, state, store, blocks, parent_root, messages, time_ms)
    )

    signed_bid = build_signed_bid(
        spec,
        state,
        builder_index=spec.BuilderIndex(0),
        slot=proposal_slot,
        parent_block_hash=parent_block_hash,
        parent_block_root=parent_root,
        fee_recipient=common_fee,
        gas_limit=parent_gas_limit,
        value=spec.Gwei(1),
    )
    yield get_filename(signed_bid), signed_bid

    # Upper edge: (bid_slot + 1)'s start + MAXIMUM_GOSSIP_CLOCK_DISPARITY. One
    # ms past that places the bid outside the disparity window.
    time_ms = (
        spec.compute_time_at_slot_ms(state, spec.Slot(proposal_slot + 1))
        + spec.config.MAXIMUM_GOSSIP_CLOCK_DISPARITY
        + 1
    )
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
    """A second bid from the same builder for the same slot is ignored.

    The first bid is fully valid, seeding the seen-bids cache, so the second
    (higher-value) bid from the same builder hits the duplicate check.
    """
    anchor_state = state.copy()
    yield "topic", "meta", "execution_payload_bid"

    store, blocks, parent_root = setup_store_advanced_for_bid(spec, state)
    finalized_checkpoint_meta = activate_builders(spec, state, store, blocks)
    yield "state", anchor_state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]
    yield "finalized_checkpoint", "meta", finalized_checkpoint_meta

    time_ms = spec.compute_time_at_slot_ms(state, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []
    seen, common_fee, parent_gas_limit, proposal_slot, parent_block_hash, time_ms = yield from (
        _seed_bid_context(spec, state, store, blocks, parent_root, messages, time_ms)
    )

    builder_index = spec.BuilderIndex(0)
    first_bid = build_signed_bid(
        spec,
        state,
        builder_index=builder_index,
        slot=proposal_slot,
        parent_block_hash=parent_block_hash,
        parent_block_root=parent_root,
        fee_recipient=common_fee,
        gas_limit=parent_gas_limit,
        value=spec.Gwei(1),
    )
    yield get_filename(first_bid), first_bid

    time_ms += 40
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        signed_execution_payload_bid=first_bid,
        current_time_ms=time_ms,
    )
    assert result == "valid"
    assert reason is None
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(first_bid),
            "expected": result,
        }
    )

    # A second bid from the same builder for the same slot, with a higher
    # value so only the duplicate check can trigger the ignore.
    duplicate_bid = build_signed_bid(
        spec,
        state,
        builder_index=builder_index,
        slot=proposal_slot,
        parent_block_hash=parent_block_hash,
        parent_block_root=parent_root,
        fee_recipient=common_fee,
        gas_limit=parent_gas_limit,
        value=spec.Gwei(2),
    )
    yield get_filename(duplicate_bid), duplicate_bid

    time_ms += 10
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        signed_execution_payload_bid=duplicate_bid,
        current_time_ms=time_ms,
    )
    assert result == "ignore"
    assert reason == "already seen valid bid from this builder for this slot"
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(duplicate_bid),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_execution_payload_bid__ignore_not_highest_value(spec, state):
    """A bid whose value does not exceed the best bid for this slot/parent is ignored.

    A first fully valid bid from another builder seeds the best-bid cache, so
    the second builder's lower-value bid hits the highest-value check.
    """
    anchor_state = state.copy()
    yield "topic", "meta", "execution_payload_bid"

    store, blocks, parent_root = setup_store_advanced_for_bid(spec, state)
    finalized_checkpoint_meta = activate_builders(spec, state, store, blocks)
    yield "state", anchor_state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]
    yield "finalized_checkpoint", "meta", finalized_checkpoint_meta

    time_ms = spec.compute_time_at_slot_ms(state, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []
    seen, common_fee, parent_gas_limit, proposal_slot, parent_block_hash, time_ms = yield from (
        _seed_bid_context(spec, state, store, blocks, parent_root, messages, time_ms)
    )

    best_bid = build_signed_bid(
        spec,
        state,
        builder_index=spec.BuilderIndex(0),
        slot=proposal_slot,
        parent_block_hash=parent_block_hash,
        parent_block_root=parent_root,
        fee_recipient=common_fee,
        gas_limit=parent_gas_limit,
        value=spec.Gwei(100),
    )
    yield get_filename(best_bid), best_bid

    time_ms += 40
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        signed_execution_payload_bid=best_bid,
        current_time_ms=time_ms,
    )
    assert result == "valid"
    assert reason is None
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(best_bid),
            "expected": result,
        }
    )

    # A lower-value bid from a different builder (so the duplicate check does
    # not apply) is not the highest bid for this slot and parent.
    lower_bid = build_signed_bid(
        spec,
        state,
        builder_index=spec.BuilderIndex(1),
        slot=proposal_slot,
        parent_block_hash=parent_block_hash,
        parent_block_root=parent_root,
        fee_recipient=common_fee,
        gas_limit=parent_gas_limit,
        value=spec.Gwei(10),
    )
    yield get_filename(lower_bid), lower_bid

    time_ms += 10
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        signed_execution_payload_bid=lower_bid,
        current_time_ms=time_ms,
    )
    assert result == "ignore"
    assert reason == "bid is not the highest value bid seen for this slot and parent"
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(lower_bid),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_execution_payload_bid__reject_builder_index_out_of_range(spec, state):
    """A bid whose builder_index is past the builder registry is rejected.

    Every other condition is satisfied, so any client rejects regardless of
    check order. Conditions that require the builder record (coverage,
    activity, signature) can only be evaluated after the bounds check.
    """
    anchor_state = state.copy()
    yield "topic", "meta", "execution_payload_bid"

    store, blocks, parent_root = setup_store_advanced_for_bid(spec, state)
    finalized_checkpoint_meta = activate_builders(spec, state, store, blocks)
    yield "state", anchor_state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]
    yield "finalized_checkpoint", "meta", finalized_checkpoint_meta

    time_ms = spec.compute_time_at_slot_ms(state, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []
    seen, common_fee, parent_gas_limit, proposal_slot, parent_block_hash, time_ms = yield from (
        _seed_bid_context(spec, state, store, blocks, parent_root, messages, time_ms)
    )

    out_of_range_index = spec.BuilderIndex(len(state.builders))
    signed_bid = build_signed_bid(
        spec,
        state,
        builder_index=out_of_range_index,
        slot=proposal_slot,
        parent_block_hash=parent_block_hash,
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
    # Zero out the builder's balance so it cannot cover even a tiny bid. This
    # is baked into the anchor state so replaying the blocks preserves it.
    # Builder activity does not depend on balance, so this is the only
    # failing condition.
    builder_index = spec.BuilderIndex(0)
    state.builders[builder_index].balance = spec.Gwei(0)
    anchor_state = state.copy()
    yield "topic", "meta", "execution_payload_bid"

    store, blocks, parent_root = setup_store_advanced_for_bid(spec, state)
    finalized_checkpoint_meta = activate_builders(spec, state, store, blocks)
    yield "state", anchor_state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]
    yield "finalized_checkpoint", "meta", finalized_checkpoint_meta

    time_ms = spec.compute_time_at_slot_ms(state, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []
    seen, common_fee, parent_gas_limit, proposal_slot, parent_block_hash, time_ms = yield from (
        _seed_bid_context(spec, state, store, blocks, parent_root, messages, time_ms)
    )

    signed_bid = build_signed_bid(
        spec,
        state,
        builder_index=builder_index,
        slot=proposal_slot,
        parent_block_hash=parent_block_hash,
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
    anchor_state = state.copy()
    yield "topic", "meta", "execution_payload_bid"

    store, blocks, parent_root = setup_store_advanced_for_bid(spec, state)
    finalized_checkpoint_meta = activate_builders(spec, state, store, blocks)
    yield "state", anchor_state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]
    yield "finalized_checkpoint", "meta", finalized_checkpoint_meta

    time_ms = spec.compute_time_at_slot_ms(state, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []
    seen, common_fee, parent_gas_limit, proposal_slot, parent_block_hash, time_ms = yield from (
        _seed_bid_context(spec, state, store, blocks, parent_root, messages, time_ms)
    )

    signed_bid = build_signed_bid(
        spec,
        state,
        builder_index=spec.BuilderIndex(0),
        slot=proposal_slot,
        parent_block_hash=parent_block_hash,
        parent_block_root=parent_root,
        fee_recipient=common_fee,
        gas_limit=parent_gas_limit,
        value=spec.Gwei(1),
        execution_payment=spec.Gwei(1),
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
    anchor_state = state.copy()
    yield "topic", "meta", "execution_payload_bid"

    store, blocks, parent_root = setup_store_advanced_for_bid(spec, state)
    yield "state", anchor_state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    time_ms = spec.compute_time_at_slot_ms(state, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []
    seen, common_fee, parent_gas_limit, proposal_slot, parent_block_hash, time_ms = yield from (
        _seed_bid_context(spec, state, store, blocks, parent_root, messages, time_ms)
    )

    builder_index = spec.BuilderIndex(0)
    # The chain of empty blocks never finalizes, so builder.deposit_epoch (0)
    # is not less than the finalized epoch (0) and is_active_builder returns
    # False. No finalized_checkpoint meta is emitted, deliberately.
    assert not spec.is_active_builder(state, builder_index)
    signed_bid = build_signed_bid(
        spec,
        state,
        builder_index=builder_index,
        slot=proposal_slot,
        parent_block_hash=parent_block_hash,
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
    anchor_state = state.copy()
    yield "topic", "meta", "execution_payload_bid"

    store, blocks, parent_root = setup_store_advanced_for_bid(spec, state)
    finalized_checkpoint_meta = activate_builders(spec, state, store, blocks)
    yield "state", anchor_state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]
    yield "finalized_checkpoint", "meta", finalized_checkpoint_meta

    time_ms = spec.compute_time_at_slot_ms(state, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []
    seen, common_fee, parent_gas_limit, proposal_slot, parent_block_hash, time_ms = yield from (
        _seed_bid_context(spec, state, store, blocks, parent_root, messages, time_ms)
    )

    # Overfill blob commitments above the per-epoch limit. The commitments are
    # part of the signed message, so the signature stays valid.
    max_blobs = spec.get_blob_parameters(
        spec.compute_epoch_at_slot(proposal_slot)
    ).max_blobs_per_block
    over_limit = int(max_blobs) + 1
    signed_bid = build_signed_bid(
        spec,
        state,
        builder_index=spec.BuilderIndex(0),
        slot=proposal_slot,
        parent_block_hash=parent_block_hash,
        parent_block_root=parent_root,
        fee_recipient=common_fee,
        gas_limit=parent_gas_limit,
        value=spec.Gwei(1),
        blob_kzg_commitments=spec.ProgressiveList[spec.KZGCommitment](
            *([spec.KZGCommitment()] * over_limit)
        ),
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
    """A bid whose parent_block_root is not in store.blocks is ignored.

    Conditions that require the parent block or its state (lookahead,
    preferences, randao) can only be evaluated once the parent is known.
    """
    anchor_state = state.copy()
    yield "topic", "meta", "execution_payload_bid"

    store, blocks, parent_root = setup_store_advanced_for_bid(spec, state)
    finalized_checkpoint_meta = activate_builders(spec, state, store, blocks)
    yield "state", anchor_state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]
    yield "finalized_checkpoint", "meta", finalized_checkpoint_meta

    time_ms = spec.compute_time_at_slot_ms(state, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []
    seen, common_fee, parent_gas_limit, proposal_slot, parent_block_hash, time_ms = yield from (
        _seed_bid_context(spec, state, store, blocks, parent_root, messages, time_ms)
    )

    unknown_root = spec.Root(b"\xab" * 32)
    signed_bid = build_signed_bid(
        spec,
        state,
        builder_index=spec.BuilderIndex(0),
        slot=proposal_slot,
        parent_block_hash=parent_block_hash,
        parent_block_root=unknown_root,
        fee_recipient=common_fee,
        gas_limit=parent_gas_limit,
        value=spec.Gwei(1),
    )
    yield get_filename(signed_bid), signed_bid

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
def test_gossip_execution_payload_bid__reject_slot_not_higher_than_parent(spec, state):
    """A bid whose slot is not greater than its parent block's slot is rejected.

    The preferences for the (current) bid slot are seeded at an earlier
    message time, while the slot was still upcoming, so the slot comparison is
    the only failing condition.
    """
    anchor_state = state.copy()
    yield "topic", "meta", "execution_payload_bid"

    store, blocks, parent_root = setup_store_advanced_for_bid(spec, state)
    finalized_checkpoint_meta = activate_builders(spec, state, store, blocks)
    yield "state", anchor_state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]
    yield "finalized_checkpoint", "meta", finalized_checkpoint_meta

    # The bid targets the head's own slot, so bid.slot == parent.slot.
    assert blocks[-1].message.slot == state.slot
    bid_slot = spec.Slot(state.slot)
    head_slot_time_ms = spec.compute_time_at_slot_ms(state, bid_slot)
    time_ms = head_slot_time_ms - spec.config.MAXIMUM_GOSSIP_CLOCK_DISPARITY - 200
    yield "current_time_ms", "meta", int(time_ms)
    messages = []
    seen, common_fee, parent_gas_limit, _, parent_block_hash, time_ms = yield from (
        _seed_bid_context(
            spec, state, store, blocks, parent_root, messages, time_ms, seed_prefs=False
        )
    )

    # Seed preferences for the bid's (current) slot, validated while the slot
    # was still upcoming.
    time_ms += 10
    signed_prefs = build_signed_proposer_preferences(
        spec,
        state,
        proposal_slot=bid_slot,
        validator_index=spec.get_beacon_proposer_index(state),
        fee_recipient=common_fee,
        target_gas_limit=parent_gas_limit,
    )
    yield get_filename(signed_prefs), signed_prefs
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

    signed_bid = build_signed_bid(
        spec,
        state,
        builder_index=spec.BuilderIndex(0),
        slot=bid_slot,
        parent_block_hash=parent_block_hash,
        parent_block_root=parent_root,
        fee_recipient=common_fee,
        gas_limit=parent_gas_limit,
        value=spec.Gwei(1),
    )
    yield get_filename(signed_bid), signed_bid

    time_ms = head_slot_time_ms + 100
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        signed_execution_payload_bid=signed_bid,
        current_time_ms=time_ms,
    )
    assert result == "reject"
    assert reason == "bid's slot is not higher than its parent's slot"
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
    """A bid whose parent_block_hash is not in seen.execution_payloads is ignored.

    No envelope is seeded, which is exactly the condition under test. The gas
    limit compatibility check requires the parent payload, so it can only be
    evaluated once the parent block hash is known.
    """
    anchor_state = state.copy()
    yield "topic", "meta", "execution_payload_bid"

    store, blocks, parent_root = setup_store_advanced_for_bid(spec, state)
    finalized_checkpoint_meta = activate_builders(spec, state, store, blocks)
    yield "state", anchor_state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]
    yield "finalized_checkpoint", "meta", finalized_checkpoint_meta

    time_ms = spec.compute_time_at_slot_ms(state, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []
    seen, common_fee, parent_gas_limit, proposal_slot, parent_block_hash, time_ms = yield from (
        _seed_bid_context(
            spec, state, store, blocks, parent_root, messages, time_ms, seed_envelope=False
        )
    )

    signed_bid = build_signed_bid(
        spec,
        state,
        builder_index=spec.BuilderIndex(0),
        slot=proposal_slot,
        parent_block_hash=parent_block_hash,
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
    """A bid whose parent block's state is missing is ignored."""
    anchor_state = state.copy()
    yield "topic", "meta", "execution_payload_bid"

    store, blocks, head_root = setup_store_advanced_for_bid(spec, state)
    head_signed_block = blocks[-1]
    # Build the bid's parent on a copy: it has been seen but not yet imported,
    # so it has no post-state and the yielded state stays at the head block.
    parent_state = state.copy()
    parent_block = build_empty_block_for_next_slot(spec, parent_state)
    signed_parent = state_transition_and_sign_block(spec, parent_state, parent_block)
    add_pending_block_to_store(store, signed_parent)
    parent_root = signed_parent.message.hash_tree_root()
    finalized_checkpoint_meta = activate_builders(spec, state, store, blocks)
    yield "state", anchor_state
    for signed in blocks:
        yield get_filename(signed), signed
    yield get_filename(signed_parent), signed_parent
    yield (
        "blocks",
        "meta",
        [{"block": get_filename(b)} for b in blocks]
        + [{"block": get_filename(signed_parent), "pending": True}],
    )
    yield "finalized_checkpoint", "meta", finalized_checkpoint_meta

    seen = get_seen(spec)
    time_ms = spec.compute_time_at_slot_ms(state, signed_parent.message.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    # Make the bid's parent block hash a known execution payload by validating
    # a real envelope for the head block. The pending parent is an empty
    # block, so the bid builds on the same payload.
    time_ms += 50
    signed_envelope = build_signed_execution_payload_envelope(
        spec, state, head_root, head_signed_block
    )
    yield get_filename(signed_envelope), signed_envelope
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

    signed_bid = build_signed_bid(
        spec,
        state,
        builder_index=spec.BuilderIndex(0),
        slot=spec.Slot(signed_parent.message.slot + 1),
        parent_block_hash=signed_envelope.message.payload.block_hash,
        parent_block_root=parent_root,
        value=spec.Gwei(1),
    )
    yield get_filename(signed_bid), signed_bid

    time_ms += 50
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
def test_gossip_execution_payload_bid__ignore_slot_past_parent_lookahead(spec, state):
    """
    A bid whose slot is more than MIN_SEED_LOOKAHEAD epochs ahead of its parent
    is ignored.

    The parent state can only determine the proposer (and thus the proposer
    lookahead dependent root) for proposals within MIN_SEED_LOOKAHEAD epochs of
    the parent's epoch. A bid building on a parent that is two or more epochs
    stale -- e.g. while the chain recovers from a multi-epoch halt -- must be
    ignored rather than trip the get_block_root_at_slot lookup inside
    get_proposer_dependent_root.
    """
    anchor_state = state.copy()
    yield "topic", "meta", "execution_payload_bid"

    store, blocks, parent_root = setup_store_advanced_for_bid(spec, state)
    finalized_checkpoint_meta = activate_builders(spec, state, store, blocks)
    parent_signed_block = blocks[-1]
    yield "state", anchor_state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]
    yield "finalized_checkpoint", "meta", finalized_checkpoint_meta

    seen = get_seen(spec)
    time_ms = spec.compute_time_at_slot_ms(state, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    # Make the parent's execution payload a known payload by validating its
    # envelope, so the bid passes the parent-known checks before the lookahead
    # check.
    time_ms += 50
    signed_envelope = build_signed_execution_payload_envelope(
        spec, state, parent_root, parent_signed_block
    )
    yield get_filename(signed_envelope), signed_envelope
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

    # A bid for a slot more than MIN_SEED_LOOKAHEAD epochs past the parent's
    # epoch: the parent cannot supply the proposer lookahead dependent root.
    parent_epoch = spec.get_current_epoch(state)
    future_epoch = spec.Epoch(parent_epoch + spec.MIN_SEED_LOOKAHEAD + 1)
    future_slot = spec.compute_start_slot_at_epoch(future_epoch)
    signed_bid = build_signed_bid(
        spec,
        state,
        builder_index=spec.BuilderIndex(0),
        slot=future_slot,
        parent_block_hash=signed_envelope.message.payload.block_hash,
        parent_block_root=parent_root,
        value=spec.Gwei(1),
    )
    yield get_filename(signed_bid), signed_bid

    # Validate at the bid's own (future) slot so it counts as the current slot.
    bid_time_ms = spec.compute_time_at_slot_ms(state, future_slot)
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        signed_execution_payload_bid=signed_bid,
        current_time_ms=bid_time_ms,
    )
    assert result == "ignore"
    assert reason == "bid's slot is past the parent's proposer lookahead"
    messages.append(
        {
            "current_time_ms": int(bid_time_ms),
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
    anchor_state = state.copy()
    yield "topic", "meta", "execution_payload_bid"

    # get_proposer_dependent_root subtracts MIN_SEED_LOOKAHEAD from the epoch,
    # so the parent state must already be at least MIN_SEED_LOOKAHEAD + 1 epochs
    # in for the lookup to land on a non-underflowing slot.
    store, blocks, parent_root = setup_store_advanced_for_bid(spec, state)
    parent_signed_block = blocks[-1]
    finalized_checkpoint_meta = activate_builders(spec, state, store, blocks)
    yield "state", anchor_state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]
    yield "finalized_checkpoint", "meta", finalized_checkpoint_meta

    seen = get_seen(spec)
    time_ms = spec.compute_time_at_slot_ms(state, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    # Make the bid's parent block hash a known execution payload by validating
    # a real envelope for the parent block. Leave seen.proposer_preferences
    # empty.
    time_ms += 50
    signed_envelope = build_signed_execution_payload_envelope(
        spec, state, parent_root, parent_signed_block
    )
    yield get_filename(signed_envelope), signed_envelope
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

    next_slot_value = spec.Slot(state.slot + 1)
    builder_index = spec.BuilderIndex(0)
    signed_bid = build_signed_bid(
        spec,
        state,
        builder_index=builder_index,
        slot=next_slot_value,
        parent_block_hash=signed_envelope.message.payload.block_hash,
        parent_block_root=parent_root,
        value=spec.Gwei(1),
    )
    yield get_filename(signed_bid), signed_bid

    time_ms += 50
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
def test_gossip_execution_payload_bid__ignore_fee_recipient_mismatch(spec, state):
    """A bid whose fee_recipient does not match the proposer's preference is ignored."""
    anchor_state = state.copy()
    yield "topic", "meta", "execution_payload_bid"

    store, blocks, parent_root = setup_store_advanced_for_bid(spec, state)
    finalized_checkpoint_meta = activate_builders(spec, state, store, blocks)
    parent_signed_block = blocks[-1]
    yield "state", anchor_state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]
    yield "finalized_checkpoint", "meta", finalized_checkpoint_meta

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
    yield get_filename(signed_prefs), signed_prefs
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
    yield get_filename(signed_envelope), signed_envelope
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
    anchor_state = state.copy()
    yield "topic", "meta", "execution_payload_bid"

    store, blocks, parent_root = setup_store_advanced_for_bid(spec, state)
    finalized_checkpoint_meta = activate_builders(spec, state, store, blocks)
    parent_signed_block = blocks[-1]
    yield "state", anchor_state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]
    yield "finalized_checkpoint", "meta", finalized_checkpoint_meta

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
    yield get_filename(signed_prefs), signed_prefs
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
    yield get_filename(signed_envelope), signed_envelope
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
def test_gossip_execution_payload_bid__reject_incorrect_prev_randao(spec, state):
    """A bid whose prev_randao does not match the parent state's RANDAO mix is rejected."""
    anchor_state = state.copy()
    yield "topic", "meta", "execution_payload_bid"

    store, blocks, parent_root = setup_store_advanced_for_bid(spec, state)
    finalized_checkpoint_meta = activate_builders(spec, state, store, blocks)
    parent_signed_block = blocks[-1]
    yield "state", anchor_state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]
    yield "finalized_checkpoint", "meta", finalized_checkpoint_meta

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
    yield get_filename(signed_prefs), signed_prefs
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
    yield get_filename(signed_envelope), signed_envelope
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

    # All other checks pass and only prev_randao is wrong. The expected value is
    # the parent state's current-epoch RANDAO mix, so use a clearly different one.
    expected_randao = spec.get_randao_mix(state, spec.get_current_epoch(state))
    wrong_randao = spec.Bytes32(b"\x42" * 32)
    assert wrong_randao != expected_randao
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
        prev_randao=wrong_randao,
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
    assert reason == "bid's previous randao is incorrect"
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
    anchor_state = state.copy()
    yield "topic", "meta", "execution_payload_bid"

    store, blocks, parent_root = setup_store_advanced_for_bid(spec, state)
    finalized_checkpoint_meta = activate_builders(spec, state, store, blocks)
    parent_signed_block = blocks[-1]
    yield "state", anchor_state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]
    yield "finalized_checkpoint", "meta", finalized_checkpoint_meta

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
    yield get_filename(signed_prefs), signed_prefs
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
    yield get_filename(signed_envelope), signed_envelope
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
    anchor_state = state.copy()
    yield "topic", "meta", "execution_payload_bid"

    store, blocks, parent_root = setup_store_advanced_for_bid(spec, state)
    finalized_checkpoint_meta = activate_builders(spec, state, store, blocks)
    parent_signed_block = blocks[-1]
    # Override the parent's bid gas_limit so the envelope's payload.gas_limit
    # (which gets seeded into seen.execution_payloads) equals our target value.
    state.latest_execution_payload_bid.gas_limit = spec.uint64(parent_gas_limit)
    yield "state", anchor_state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]
    yield "finalized_checkpoint", "meta", finalized_checkpoint_meta

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
    yield get_filename(signed_prefs), signed_prefs
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
    yield get_filename(signed_envelope), signed_envelope
    assert signed_envelope.message.payload.gas_limit == parent_gas_limit
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


@with_gloas_and_later
@spec_state_test
def test_gossip_execution_payload_bid__valid_requires_state_advanced_across_epoch(spec, state):
    """
    A bid that is only coverable because validation advances the state across
    the epoch boundary.

    The chain finalizes epoch 1 organically (activating the builders), and a
    block then records a sub-quorum pending payment against builder 0. The
    bid's parent is at the last slot of an epoch, and the bid claims the
    builder's entire coverable balance, so the pending payment makes it
    uncoverable at the parent's slot. Validation advances the state to the
    bid's slot (the first slot of the next epoch), where
    process_builder_pending_payments has dropped the payment -- so the bid is
    valid. If the advance were removed, validation would yield an "ignore"
    instead.
    """
    anchor_state = state.copy()
    yield "topic", "meta", "execution_payload_bid"

    store, blocks, parent_root, builder_index, pending_value = (
        setup_store_finalized_with_pending_payment(spec, state)
    )
    parent_signed_block = blocks[-1]
    yield "state", anchor_state
    for signed in blocks:
        yield get_filename(signed), signed
    yield "blocks", "meta", [{"block": get_filename(b)} for b in blocks]

    # The bid claims the builder's entire coverable balance: coverable only
    # once the pending payment is dropped at the epoch transition.
    bid_value = spec.Gwei(state.builders[builder_index].balance - spec.MIN_DEPOSIT_AMOUNT)
    assert pending_value > 0
    assert not spec.can_builder_cover_bid(state, builder_index, bid_value)
    advanced_state = state.copy()
    spec.process_slots(advanced_state, spec.Slot(state.slot + 1))
    assert spec.can_builder_cover_bid(advanced_state, builder_index, bid_value)

    seen = get_seen(spec)
    time_ms = spec.compute_time_at_slot_ms(state, state.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    common_fee = spec.ExecutionAddress(b"\x11" * 20)
    parent_gas_limit = state.latest_execution_payload_bid.gas_limit

    # The first proposal slot after the parent is the first slot of the next
    # epoch, so validating the bid must advance the state across the boundary.
    time_ms += 50
    proposal_slot, validator_index = find_upcoming_proposal_slot(spec, state)
    assert spec.compute_epoch_at_slot(proposal_slot) == spec.compute_epoch_at_slot(state.slot) + 1
    signed_prefs = build_signed_proposer_preferences(
        spec,
        state,
        proposal_slot=proposal_slot,
        validator_index=validator_index,
        fee_recipient=common_fee,
        target_gas_limit=parent_gas_limit,
    )
    yield get_filename(signed_prefs), signed_prefs
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
    signed_envelope = build_signed_execution_payload_envelope(
        spec, state, parent_root, parent_signed_block
    )
    yield get_filename(signed_envelope), signed_envelope
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

    signed_bid = build_signed_bid(
        spec,
        state,
        builder_index=builder_index,
        slot=proposal_slot,
        parent_block_hash=signed_envelope.message.payload.block_hash,
        parent_block_root=parent_root,
        fee_recipient=common_fee,
        gas_limit=parent_gas_limit,
        value=bid_value,
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
