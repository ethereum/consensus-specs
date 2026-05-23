from eth_consensus_specs.test.context import (
    spec_state_test,
    with_gloas_and_later,
)
from eth_consensus_specs.test.helpers.attestations import (
    get_valid_attestation,
    to_single_attestation,
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
from eth_consensus_specs.test.helpers.state import next_slot, state_transition_and_sign_block


def get_correct_subnet(spec, state, attestation):
    committees_per_slot = spec.get_committee_count_per_slot(state, attestation.data.target.epoch)
    return spec.compute_subnet_for_attestation(
        committees_per_slot, attestation.data.slot, attestation.committee_index
    )


def prepare_single_attestation(spec, state):
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    anchor_root = anchor_block.hash_tree_root()
    next_slot(spec, state)
    attestation = get_valid_attestation(spec, state, signed=False, beacon_block_root=anchor_root)
    single = to_single_attestation(spec, state, attestation)
    return store, signed_anchor, single


@with_gloas_and_later
@spec_state_test
def test_gossip_beacon_attestation__reject_data_index_too_high(spec, state):
    """A SingleAttestation with data.index >= 2 is rejected."""
    yield "topic", "meta", "beacon_attestation"
    yield "state", state

    seen = get_seen(spec)
    store, signed_anchor, attestation = prepare_single_attestation(spec, state)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    attestation.data.index = spec.CommitteeIndex(2)

    yield get_filename(attestation), attestation

    time_ms = spec.compute_time_at_slot_ms(state, attestation.data.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    subnet_id = get_correct_subnet(spec, state, attestation)
    time_ms += 500
    result, reason = run_validate_gossip(
        spec, seen, store, state, attestation, current_time_ms=time_ms, subnet_id=subnet_id
    )
    assert result == "reject"
    assert reason == "attestation data index must be 0 or 1"
    messages.append(
        {
            "subnet_id": int(subnet_id),
            "current_time_ms": int(time_ms),
            "message": get_filename(attestation),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


def prepare_same_slot_attestation(spec, state, payload_index):
    """
    Build a block at the next slot, register it in the store, then return a
    SingleAttestation whose data.slot matches that block's slot.
    Returns (store, signed_anchor, signed_block, single_attestation, subnet_id).
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
    single = to_single_attestation(spec, state, attestation)
    subnet_id = get_correct_subnet(spec, state, single)
    return store, signed_anchor, signed_block, single, subnet_id


@with_gloas_and_later
@spec_state_test
def test_gossip_beacon_attestation__reject_same_slot_with_payload(spec, state):
    """A same-slot attestation with data.index != 0 is rejected."""
    yield "topic", "meta", "beacon_attestation"
    yield "state", state

    store, signed_anchor, signed_block, attestation, subnet_id = prepare_same_slot_attestation(
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
    yield get_filename(attestation), attestation

    time_ms = spec.compute_time_at_slot_ms(state, attestation.data.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 500
    result, reason = run_validate_gossip(
        spec, seen, store, state, attestation, current_time_ms=time_ms, subnet_id=subnet_id
    )
    assert result == "reject"
    assert reason == "same-slot attestation must attest with index 0"
    messages.append(
        {
            "subnet_id": int(subnet_id),
            "current_time_ms": int(time_ms),
            "message": get_filename(attestation),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


def prepare_past_slot_attestation(spec, state, payload_index):
    """
    Build a block at the next slot, register it, then advance state once more
    so the attestation refers to a *past*-slot block (block.slot != data.slot).
    Returns (store, signed_anchor, signed_block, attestation, subnet_id, block_root).
    """
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block)
    block_root = signed_block.message.hash_tree_root()
    store.blocks[block_root] = signed_block.message
    store.block_states[block_root] = state.copy()
    # Advance state to a later slot so data.slot != block.slot.
    next_slot(spec, state)

    attestation = get_valid_attestation(
        spec,
        state,
        beacon_block_root=block_root,
        payload_index=payload_index,
        signed=True,
    )
    single = to_single_attestation(spec, state, attestation)
    subnet_id = get_correct_subnet(spec, state, single)
    return store, signed_anchor, signed_block, single, subnet_id, block_root


@with_gloas_and_later
@spec_state_test
def test_gossip_beacon_attestation__ignore_payload_envelope_unseen(spec, state):
    """A data.index=1 attestation whose payload envelope is unknown is ignored."""
    yield "topic", "meta", "beacon_attestation"
    yield "state", state

    store, signed_anchor, signed_block, attestation, subnet_id, _ = prepare_past_slot_attestation(
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
    yield get_filename(attestation), attestation

    time_ms = spec.compute_time_at_slot_ms(state, attestation.data.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 500
    result, reason = run_validate_gossip(
        spec,
        seen,
        store,
        state,
        attestation,
        current_time_ms=time_ms,
        subnet_id=subnet_id,
        block_payload_statuses={},
    )
    assert result == "ignore"
    assert reason == "execution payload envelope has not been seen"
    messages.append(
        {
            "subnet_id": int(subnet_id),
            "current_time_ms": int(time_ms),
            "message": get_filename(attestation),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_beacon_attestation__ignore_payload_pending_el_validation(spec, state):
    """A data.index=1 attestation whose payload is pending EL is ignored."""
    yield "topic", "meta", "beacon_attestation"
    yield "state", state

    store, signed_anchor, signed_block, attestation, subnet_id, block_root = (
        prepare_past_slot_attestation(spec, state, payload_index=1)
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
    yield get_filename(attestation), attestation

    time_ms = spec.compute_time_at_slot_ms(state, attestation.data.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 500
    result, reason = run_validate_gossip(
        spec,
        seen,
        store,
        state,
        attestation,
        current_time_ms=time_ms,
        subnet_id=subnet_id,
        block_payload_statuses=get_spec_block_payload_statuses(
            spec, {block_root: PAYLOAD_STATUS_NOT_VALIDATED}
        ),
    )
    assert result == "ignore"
    assert reason == "execution payload pending EL validation"
    messages.append(
        {
            "subnet_id": int(subnet_id),
            "current_time_ms": int(time_ms),
            "message": get_filename(attestation),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_beacon_attestation__reject_payload_failed_el_validation(spec, state):
    """A data.index=1 attestation whose payload was EL-invalidated is rejected."""
    yield "topic", "meta", "beacon_attestation"
    yield "state", state

    store, signed_anchor, signed_block, attestation, subnet_id, block_root = (
        prepare_past_slot_attestation(spec, state, payload_index=1)
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
    yield get_filename(attestation), attestation

    time_ms = spec.compute_time_at_slot_ms(state, attestation.data.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 500
    result, reason = run_validate_gossip(
        spec,
        seen,
        store,
        state,
        attestation,
        current_time_ms=time_ms,
        subnet_id=subnet_id,
        block_payload_statuses=get_spec_block_payload_statuses(
            spec, {block_root: PAYLOAD_STATUS_INVALIDATED}
        ),
    )
    assert result == "reject"
    assert reason == "execution payload failed EL validation"
    messages.append(
        {
            "subnet_id": int(subnet_id),
            "current_time_ms": int(time_ms),
            "message": get_filename(attestation),
            "expected": result,
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_gloas_and_later
@spec_state_test
def test_gossip_beacon_attestation__valid_payload_validated(spec, state):
    """A data.index=1 attestation whose payload passed EL validation is valid."""
    yield "topic", "meta", "beacon_attestation"
    yield "state", state

    store, signed_anchor, signed_block, attestation, subnet_id, block_root = (
        prepare_past_slot_attestation(spec, state, payload_index=1)
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
    yield get_filename(attestation), attestation

    time_ms = spec.compute_time_at_slot_ms(state, attestation.data.slot)
    yield "current_time_ms", "meta", int(time_ms)
    messages = []

    time_ms += 500
    result, reason = run_validate_gossip(
        spec,
        seen,
        store,
        state,
        attestation,
        current_time_ms=time_ms,
        subnet_id=subnet_id,
        block_payload_statuses=get_spec_block_payload_statuses(
            spec, {block_root: PAYLOAD_STATUS_VALID}
        ),
    )
    assert result == "valid"
    assert reason is None
    messages.append(
        {
            "subnet_id": int(subnet_id),
            "current_time_ms": int(time_ms),
            "message": get_filename(attestation),
            "expected": result,
        }
    )

    yield "messages", "meta", messages
