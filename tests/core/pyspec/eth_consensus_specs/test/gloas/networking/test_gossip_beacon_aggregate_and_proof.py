from eth_consensus_specs.test.context import (
    spec_state_test,
    with_gloas_and_later,
)
from eth_consensus_specs.test.helpers.attestations import (
    get_valid_attestation,
)
from eth_consensus_specs.test.helpers.block import build_empty_block_for_next_slot
from eth_consensus_specs.test.helpers.fork_choice import (
    get_genesis_forkchoice_store_and_block,
)
from eth_consensus_specs.test.helpers.gossip import (
    get_filename,
    get_seen,
    get_spec_block_payload_statuses,
    PAYLOAD_STATUS_INVALIDATED,
    PAYLOAD_STATUS_NOT_VALIDATED,
    PAYLOAD_STATUS_VALID,
    run_validate_gossip,
    wrap_genesis_block,
)
from eth_consensus_specs.test.helpers.keys import privkeys
from eth_consensus_specs.test.helpers.state import next_slot, state_transition_and_sign_block


def create_signed_aggregate_and_proof(spec, state, attestation):
    committee_index = spec.get_committee_indices(attestation.committee_bits)[0]
    committee = spec.get_beacon_committee(state, attestation.data.slot, committee_index)

    aggregator_index = None
    for index in committee:
        privkey = privkeys[index]
        selection_proof = spec.get_slot_signature(state, attestation.data.slot, privkey)
        if spec.is_aggregator(state, attestation.data.slot, committee_index, selection_proof):
            aggregator_index = index
            break

    if aggregator_index is None:
        aggregator_index = committee[0]

    privkey = privkeys[aggregator_index]
    aggregate_and_proof = spec.get_aggregate_and_proof(
        state, aggregator_index, attestation, privkey
    )
    signature = spec.get_aggregate_and_proof_signature(state, aggregate_and_proof, privkey)

    return spec.SignedAggregateAndProof(message=aggregate_and_proof, signature=signature)


def prepare_signed_aggregate(spec, state):
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    anchor_root = anchor_block.hash_tree_root()
    next_slot(spec, state)
    attestation = get_valid_attestation(spec, state, signed=True, beacon_block_root=anchor_root)
    signed_agg = create_signed_aggregate_and_proof(spec, state, attestation)
    return store, signed_anchor, signed_agg


@with_gloas_and_later
@spec_state_test
def test_gossip_beacon_aggregate_and_proof__reject_data_index_too_high(spec, state):
    """An aggregate with data.index >= 2 is rejected."""
    anchor_state = state.copy()
    yield "topic", "meta", "beacon_aggregate_and_proof"
    yield "state", anchor_state

    seen = get_seen(spec)
    store, signed_anchor, signed_agg = prepare_signed_aggregate(spec, state)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    # Bump the data index past the gloas-allowed range.
    signed_agg.message.aggregate.data.index = spec.CommitteeIndex(2)

    yield get_filename(signed_agg), signed_agg

    time_ms = spec.compute_time_at_slot_ms(state, signed_agg.message.aggregate.data.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 500
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        signed_aggregate_and_proof=signed_agg,
        current_time_ms=time_ms,
        block_payload_statuses={},
    )
    assert result == "reject"
    assert reason == "aggregate data index must be 0 or 1"
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_agg),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


def prepare_same_slot_aggregate(spec, state, payload_index):
    """
    Build a block at the next slot, register it in the store, then build a
    signed aggregate whose data.slot matches that block's slot.
    Returns (store, signed_anchor, signed_block, signed_agg, block_root).
    """
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block)
    block_root = signed_block.message.hash_tree_root()
    store.blocks[block_root] = signed_block.message
    store.block_states[block_root] = state.copy()

    attestation = get_valid_attestation(
        spec,
        state,
        beacon_block_root=block_root,
        payload_index=payload_index,
        signed=True,
    )
    signed_agg = create_signed_aggregate_and_proof(spec, state, attestation)
    return store, signed_anchor, signed_block, signed_agg, block_root


def prepare_past_slot_aggregate(spec, state, payload_index):
    """
    Build a block, register it, advance state so data.slot != block.slot, then
    build a signed aggregate with the requested ``data.index``.
    Returns (store, signed_anchor, signed_block, signed_agg, block_root).
    """
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block)
    block_root = signed_block.message.hash_tree_root()
    store.blocks[block_root] = signed_block.message
    store.block_states[block_root] = state.copy()
    next_slot(spec, state)

    attestation = get_valid_attestation(
        spec,
        state,
        beacon_block_root=block_root,
        payload_index=payload_index,
        signed=True,
    )
    signed_agg = create_signed_aggregate_and_proof(spec, state, attestation)
    return store, signed_anchor, signed_block, signed_agg, block_root


@with_gloas_and_later
@spec_state_test
def test_gossip_beacon_aggregate_and_proof__reject_same_slot_with_payload(spec, state):
    """A same-slot aggregate with data.index != 0 is rejected."""
    anchor_state = state.copy()
    yield "topic", "meta", "beacon_aggregate_and_proof"
    yield "state", anchor_state

    store, signed_anchor, signed_block, signed_agg, _ = prepare_same_slot_aggregate(
        spec, state, payload_index=1
    )
    seen = get_seen(spec)
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
    yield get_filename(signed_agg), signed_agg

    time_ms = spec.compute_time_at_slot_ms(state, signed_agg.message.aggregate.data.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 500
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        signed_aggregate_and_proof=signed_agg,
        current_time_ms=time_ms,
        block_payload_statuses={},
    )
    assert result == "reject"
    assert reason == "same-slot aggregate must attest with index 0"
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_agg),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_beacon_aggregate_and_proof__ignore_payload_envelope_unseen(spec, state):
    """A data.index=1 aggregate with no known payload envelope is ignored."""
    anchor_state = state.copy()
    yield "topic", "meta", "beacon_aggregate_and_proof"
    yield "state", anchor_state

    store, signed_anchor, signed_block, signed_agg, _ = prepare_past_slot_aggregate(
        spec, state, payload_index=1
    )
    seen = get_seen(spec)
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
    yield get_filename(signed_agg), signed_agg

    time_ms = spec.compute_time_at_slot_ms(state, signed_agg.message.aggregate.data.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 500
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        signed_aggregate_and_proof=signed_agg,
        current_time_ms=time_ms,
        block_payload_statuses={},
    )
    assert result == "ignore"
    assert reason == "execution payload envelope has not been seen"
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_agg),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_beacon_aggregate_and_proof__ignore_payload_pending_el_validation(spec, state):
    """A data.index=1 aggregate with payload pending EL validation is ignored."""
    anchor_state = state.copy()
    yield "topic", "meta", "beacon_aggregate_and_proof"
    yield "state", anchor_state

    store, signed_anchor, signed_block, signed_agg, block_root = prepare_past_slot_aggregate(
        spec, state, payload_index=1
    )
    seen = get_seen(spec)
    yield get_filename(signed_anchor), signed_anchor
    yield get_filename(signed_block), signed_block
    yield (
        "blocks",
        "meta",
        [
            {"block": get_filename(signed_anchor)},
            {
                "block": get_filename(signed_block),
                "payload_status": PAYLOAD_STATUS_NOT_VALIDATED,
            },
        ],
    )
    yield get_filename(signed_agg), signed_agg

    time_ms = spec.compute_time_at_slot_ms(state, signed_agg.message.aggregate.data.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 500
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        signed_aggregate_and_proof=signed_agg,
        current_time_ms=time_ms,
        block_payload_statuses=get_spec_block_payload_statuses(
            spec, {block_root: PAYLOAD_STATUS_NOT_VALIDATED}
        ),
    )
    assert result == "ignore"
    assert reason == "execution payload pending EL validation"
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_agg),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_beacon_aggregate_and_proof__reject_payload_failed_el_validation(spec, state):
    """A data.index=1 aggregate whose payload was EL-invalidated is rejected."""
    anchor_state = state.copy()
    yield "topic", "meta", "beacon_aggregate_and_proof"
    yield "state", anchor_state

    store, signed_anchor, signed_block, signed_agg, block_root = prepare_past_slot_aggregate(
        spec, state, payload_index=1
    )
    seen = get_seen(spec)
    yield get_filename(signed_anchor), signed_anchor
    yield get_filename(signed_block), signed_block
    yield (
        "blocks",
        "meta",
        [
            {"block": get_filename(signed_anchor)},
            {
                "block": get_filename(signed_block),
                "payload_status": PAYLOAD_STATUS_INVALIDATED,
            },
        ],
    )
    yield get_filename(signed_agg), signed_agg

    time_ms = spec.compute_time_at_slot_ms(state, signed_agg.message.aggregate.data.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 500
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        signed_aggregate_and_proof=signed_agg,
        current_time_ms=time_ms,
        block_payload_statuses=get_spec_block_payload_statuses(
            spec, {block_root: PAYLOAD_STATUS_INVALIDATED}
        ),
    )
    assert result == "reject"
    assert reason == "execution payload failed EL validation"
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_agg),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_beacon_aggregate_and_proof__valid_payload_validated(spec, state):
    """A data.index=1 aggregate whose payload passed EL validation is valid."""
    anchor_state = state.copy()
    yield "topic", "meta", "beacon_aggregate_and_proof"
    yield "state", anchor_state

    store, signed_anchor, signed_block, signed_agg, block_root = prepare_past_slot_aggregate(
        spec, state, payload_index=1
    )
    seen = get_seen(spec)
    yield get_filename(signed_anchor), signed_anchor
    yield get_filename(signed_block), signed_block
    yield (
        "blocks",
        "meta",
        [
            {"block": get_filename(signed_anchor)},
            {
                "block": get_filename(signed_block),
                "payload_status": PAYLOAD_STATUS_VALID,
            },
        ],
    )
    yield get_filename(signed_agg), signed_agg

    time_ms = spec.compute_time_at_slot_ms(state, signed_agg.message.aggregate.data.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 500
    result, reason = run_validate_gossip(
        spec,
        seen=seen,
        store=store,
        state=state,
        signed_aggregate_and_proof=signed_agg,
        current_time_ms=time_ms,
        block_payload_statuses=get_spec_block_payload_statuses(
            spec, {block_root: PAYLOAD_STATUS_VALID}
        ),
    )
    assert result == "valid"
    assert reason is None
    messages.append(
        {
            "current_time_ms": int(time_ms),
            "message": get_filename(signed_agg),
            "expected": result,
        }
    )

    yield "messages", "meta", messages
