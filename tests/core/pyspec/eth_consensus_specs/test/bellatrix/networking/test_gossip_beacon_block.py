from eth_consensus_specs.test.context import (
    spec_state_test,
    with_phases,
)
from eth_consensus_specs.test.helpers.block import (
    build_empty_block_for_next_slot,
    sign_block,
)
from eth_consensus_specs.test.helpers.constants import BELLATRIX
from eth_consensus_specs.test.helpers.execution_payload import (
    build_empty_execution_payload,
    build_state_with_complete_transition,
    build_state_with_incomplete_transition,
)
from eth_consensus_specs.test.helpers.fork_choice import (
    get_genesis_forkchoice_store_and_block,
)
from eth_consensus_specs.test.helpers.gossip import get_filename, get_seen
from eth_consensus_specs.test.helpers.state import (
    state_transition_and_sign_block,
)

PAYLOAD_STATUS_VALID = "VALID"
PAYLOAD_STATUS_NOT_VALIDATED = "NOT_VALIDATED"
PAYLOAD_STATUS_INVALIDATED = "INVALIDATED"


def wrap_genesis_block(spec, block):
    """Wrap an unsigned genesis block in a SignedBeaconBlock with empty signature."""
    return spec.SignedBeaconBlock(message=block)


def get_spec_block_payload_statuses(spec, block_payload_statuses):
    spec_block_payload_statuses = {}
    if block_payload_statuses is None:
        return spec_block_payload_statuses

    for block_root, payload_status in block_payload_statuses.items():
        if payload_status == PAYLOAD_STATUS_VALID:
            spec_block_payload_statuses[block_root] = spec.PAYLOAD_STATUS_VALID
        elif payload_status == PAYLOAD_STATUS_INVALIDATED:
            spec_block_payload_statuses[block_root] = spec.PAYLOAD_STATUS_INVALIDATED
        else:
            assert payload_status == PAYLOAD_STATUS_NOT_VALIDATED
            spec_block_payload_statuses[block_root] = spec.PAYLOAD_STATUS_NOT_VALIDATED

    return spec_block_payload_statuses


def run_validate_beacon_block_gossip(
    spec, seen, store, state, signed_block, current_time_ms, block_payload_statuses=None
):
    """
    Run validate_beacon_block_gossip and return the result.
    Returns: tuple of (result, reason) where result is "valid", "ignore", or "reject"
             and reason is the exception message (or None for valid).
    """
    try:
        spec.validate_beacon_block_gossip(
            seen,
            store,
            state,
            signed_block,
            current_time_ms,
            block_payload_statuses=get_spec_block_payload_statuses(spec, block_payload_statuses),
        )
        return "valid", None
    except spec.GossipIgnore as e:
        return "ignore", str(e)
    except spec.GossipReject as e:
        return "reject", str(e)


# ──────────────────────────────────────────────────────────────────────────────
# Execution payload timestamp checks (new in Bellatrix)
# ──────────────────────────────────────────────────────────────────────────────


@with_phases([BELLATRIX])
@spec_state_test
def test_gossip_beacon_block__valid_execution_enabled(spec, state):
    """
    Test that a valid block with execution enabled passes gossip validation.
    """
    yield "topic", "meta", "beacon_block"

    state = build_state_with_complete_transition(spec, state)
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)

    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block)

    yield get_filename(signed_block), signed_block

    block_time_ms = spec.compute_time_at_slot_ms(state, signed_block.message.slot)

    yield "current_time_ms", "meta", int(block_time_ms)

    result, reason = run_validate_beacon_block_gossip(
        spec, seen, store, state, signed_block, block_time_ms + 500
    )
    assert result == "valid"
    assert reason is None

    yield (
        "messages",
        "meta",
        [{"offset_ms": 500, "message": get_filename(signed_block), "expected": "valid"}],
    )


@with_phases([BELLATRIX])
@spec_state_test
def test_gossip_beacon_block__valid_execution_disabled(spec, state):
    """
    Test that a valid block with execution disabled passes gossip validation.
    """
    yield "topic", "meta", "beacon_block"

    state = build_state_with_incomplete_transition(spec, state)
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)

    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    block = build_empty_block_for_next_slot(spec, state)
    block.body.execution_payload = spec.ExecutionPayload()
    signed_block = state_transition_and_sign_block(spec, state, block)

    yield get_filename(signed_block), signed_block

    block_time_ms = spec.compute_time_at_slot_ms(state, signed_block.message.slot)

    yield "current_time_ms", "meta", int(block_time_ms)

    result, reason = run_validate_beacon_block_gossip(
        spec, seen, store, state, signed_block, block_time_ms + 500
    )
    assert result == "valid"
    assert reason is None

    yield (
        "messages",
        "meta",
        [{"offset_ms": 500, "message": get_filename(signed_block), "expected": "valid"}],
    )


@with_phases([BELLATRIX])
@spec_state_test
def test_gossip_beacon_block__reject_incorrect_execution_payload_timestamp(spec, state):
    """
    Test that a block with incorrect execution payload timestamp is rejected.
    """
    yield "topic", "meta", "beacon_block"

    state = build_state_with_complete_transition(spec, state)
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)

    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    block = build_empty_block_for_next_slot(spec, state)

    # Corrupt the execution payload timestamp
    block.body.execution_payload.timestamp = 0

    signed_block = sign_block(spec, state, block, proposer_index=block.proposer_index)

    yield get_filename(signed_block), signed_block

    block_time_ms = spec.compute_time_at_slot_ms(state, block.slot)

    yield "current_time_ms", "meta", int(block_time_ms)

    result, reason = run_validate_beacon_block_gossip(
        spec, seen, store, state, signed_block, block_time_ms + 500
    )
    assert result == "reject"
    assert reason == "incorrect execution payload timestamp"

    yield (
        "messages",
        "meta",
        [
            {
                "offset_ms": 500,
                "message": get_filename(signed_block),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


# ──────────────────────────────────────────────────────────────────────────────
# Execution payload verification status (parent checks, new in Bellatrix)
# ──────────────────────────────────────────────────────────────────────────────


@with_phases([BELLATRIX])
@spec_state_test
def test_gossip_beacon_block__reject_parent_consensus_failed_execution_not_verified(spec, state):
    """
    Test that when execution is enabled and parent's execution status is
    unknown, a block whose parent failed consensus validation is rejected.
    """
    yield "topic", "meta", "beacon_block"

    state = build_state_with_complete_transition(spec, state)
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)

    yield get_filename(signed_anchor), signed_anchor

    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block)

    yield get_filename(signed_block), signed_block

    # Add to store.blocks but NOT store.block_states (simulating failed consensus validation)
    store.blocks[signed_block.message.hash_tree_root()] = signed_block.message
    # Parent payload status is NOT_VALIDATED, i.e. execution is not yet validated.

    yield (
        "blocks",
        "meta",
        [
            {"block": get_filename(signed_anchor)},
            {
                "block": get_filename(signed_block),
                "failed": True,
                "payload_status": PAYLOAD_STATUS_NOT_VALIDATED,
            },
        ],
    )

    # Build child block referencing the "failed" parent
    child_slot = signed_block.message.slot + 1
    temp_state = state.copy()
    spec.process_slots(temp_state, child_slot)
    proposer_index = spec.get_beacon_proposer_index(temp_state)

    child_block = spec.BeaconBlock(
        slot=child_slot,
        proposer_index=proposer_index,
        parent_root=signed_block.message.hash_tree_root(),
        state_root=temp_state.hash_tree_root(),
    )
    child_block.body.execution_payload = build_empty_execution_payload(spec, temp_state)
    signed_child = sign_block(spec, temp_state, child_block, proposer_index=proposer_index)

    yield get_filename(signed_child), signed_child

    block_time_ms = spec.compute_time_at_slot_ms(state, child_block.slot)

    yield "current_time_ms", "meta", int(block_time_ms)

    result, reason = run_validate_beacon_block_gossip(
        spec,
        seen,
        store,
        state,
        signed_child,
        block_time_ms + 500,
        block_payload_statuses={
            signed_block.message.hash_tree_root(): PAYLOAD_STATUS_NOT_VALIDATED,
        },
    )
    assert result == "reject"
    assert reason == "block's parent is invalid and EL result is unknown"

    yield (
        "messages",
        "meta",
        [
            {
                "offset_ms": 500,
                "message": get_filename(signed_child),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_phases([BELLATRIX])
@spec_state_test
def test_gossip_beacon_block__ignore_parent_consensus_failed_execution_known(spec, state):
    """
    Test that when execution is enabled and parent's execution status is known,
    a block whose parent failed consensus validation is ignored.
    """
    yield "topic", "meta", "beacon_block"

    state = build_state_with_complete_transition(spec, state)
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)

    yield get_filename(signed_anchor), signed_anchor

    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block)

    yield get_filename(signed_block), signed_block

    parent_root = signed_block.message.hash_tree_root()

    # Parent has a known execution status but failed consensus validation.
    store.blocks[parent_root] = signed_block.message
    block_payload_statuses = {parent_root: PAYLOAD_STATUS_VALID}

    yield (
        "blocks",
        "meta",
        [
            {"block": get_filename(signed_anchor)},
            {
                "block": get_filename(signed_block),
                "failed": True,
                "payload_status": PAYLOAD_STATUS_VALID,
            },
        ],
    )

    child_slot = signed_block.message.slot + 1
    temp_state = state.copy()
    spec.process_slots(temp_state, child_slot)
    proposer_index = spec.get_beacon_proposer_index(temp_state)

    child_block = spec.BeaconBlock(
        slot=child_slot,
        proposer_index=proposer_index,
        parent_root=parent_root,
        state_root=temp_state.hash_tree_root(),
    )
    child_block.body.execution_payload = build_empty_execution_payload(spec, temp_state)
    signed_child = sign_block(spec, temp_state, child_block, proposer_index=proposer_index)

    yield get_filename(signed_child), signed_child

    block_time_ms = spec.compute_time_at_slot_ms(state, child_block.slot)

    yield "current_time_ms", "meta", int(block_time_ms)

    result, reason = run_validate_beacon_block_gossip(
        spec,
        seen,
        store,
        state,
        signed_child,
        block_time_ms + 500,
        block_payload_statuses=block_payload_statuses,
    )
    assert result == "ignore"
    assert reason == "block's parent is invalid and EL result is known"

    yield (
        "messages",
        "meta",
        [
            {
                "offset_ms": 500,
                "message": get_filename(signed_child),
                "expected": "ignore",
                "reason": reason,
            }
        ],
    )


@with_phases([BELLATRIX])
@spec_state_test
def test_gossip_beacon_block__ignore_parent_execution_verified_invalid(spec, state):
    """
    Test that when execution is enabled and parent's execution has been verified
    as invalid, the child block is ignored.
    """
    yield "topic", "meta", "beacon_block"

    state = build_state_with_complete_transition(spec, state)
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)

    yield get_filename(signed_anchor), signed_anchor

    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block)

    yield get_filename(signed_block), signed_block

    parent_root = signed_block.message.hash_tree_root()

    # Parent is in store.blocks and store.block_states (consensus passed),
    # but execution was verified as INVALID
    store.blocks[parent_root] = signed_block.message
    store.block_states[parent_root] = state.copy()
    block_payload_statuses = {parent_root: PAYLOAD_STATUS_INVALIDATED}

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

    # Build child block
    child_slot = signed_block.message.slot + 1
    temp_state = state.copy()
    spec.process_slots(temp_state, child_slot)
    proposer_index = spec.get_beacon_proposer_index(temp_state)

    child_block = spec.BeaconBlock(
        slot=child_slot,
        proposer_index=proposer_index,
        parent_root=parent_root,
        state_root=temp_state.hash_tree_root(),
    )
    child_block.body.execution_payload = build_empty_execution_payload(spec, temp_state)
    signed_child = sign_block(spec, temp_state, child_block, proposer_index=proposer_index)

    yield get_filename(signed_child), signed_child

    block_time_ms = spec.compute_time_at_slot_ms(state, child_block.slot)

    yield "current_time_ms", "meta", int(block_time_ms)

    result, reason = run_validate_beacon_block_gossip(
        spec,
        seen,
        store,
        state,
        signed_child,
        block_time_ms + 500,
        block_payload_statuses=block_payload_statuses,
    )
    assert result == "ignore"
    assert reason == "block's parent is valid and EL result is invalid"

    yield (
        "messages",
        "meta",
        [
            {
                "offset_ms": 500,
                "message": get_filename(signed_child),
                "expected": "ignore",
                "reason": reason,
            }
        ],
    )


@with_phases([BELLATRIX])
@spec_state_test
def test_gossip_beacon_block__valid_parent_execution_verified_valid(spec, state):
    """
    Test that when parent's execution has been verified as valid, the child
    block passes validation.
    """
    yield "topic", "meta", "beacon_block"

    state = build_state_with_complete_transition(spec, state)
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)

    yield get_filename(signed_anchor), signed_anchor

    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block)

    yield get_filename(signed_block), signed_block

    parent_root = signed_block.message.hash_tree_root()

    # Parent fully validated: consensus and execution both passed
    store.blocks[parent_root] = signed_block.message
    store.block_states[parent_root] = state.copy()
    block_payload_statuses = {parent_root: PAYLOAD_STATUS_VALID}

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

    # Build child block
    child_slot = signed_block.message.slot + 1
    temp_state = state.copy()
    spec.process_slots(temp_state, child_slot)
    proposer_index = spec.get_beacon_proposer_index(temp_state)

    child_block = spec.BeaconBlock(
        slot=child_slot,
        proposer_index=proposer_index,
        parent_root=parent_root,
        state_root=temp_state.hash_tree_root(),
    )
    child_block.body.execution_payload = build_empty_execution_payload(spec, temp_state)
    signed_child = sign_block(spec, temp_state, child_block, proposer_index=proposer_index)

    yield get_filename(signed_child), signed_child

    block_time_ms = spec.compute_time_at_slot_ms(state, child_block.slot)

    yield "current_time_ms", "meta", int(block_time_ms)

    result, reason = run_validate_beacon_block_gossip(
        spec,
        seen,
        store,
        state,
        signed_child,
        block_time_ms + 500,
        block_payload_statuses=block_payload_statuses,
    )
    assert result == "valid"
    assert reason is None

    yield (
        "messages",
        "meta",
        [{"offset_ms": 500, "message": get_filename(signed_child), "expected": "valid"}],
    )


@with_phases([BELLATRIX])
@spec_state_test
def test_gossip_beacon_block__valid_parent_optimistic(spec, state):
    """
    Test that when parent's execution verification is not yet complete
    (optimistic) but consensus validation passed, the child block passes.
    """
    yield "topic", "meta", "beacon_block"

    state = build_state_with_complete_transition(spec, state)
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)

    yield get_filename(signed_anchor), signed_anchor

    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block)

    yield get_filename(signed_block), signed_block

    parent_root = signed_block.message.hash_tree_root()

    # Parent passed consensus validation but execution not yet verified
    store.blocks[parent_root] = signed_block.message
    store.block_states[parent_root] = state.copy()
    block_payload_statuses = {parent_root: PAYLOAD_STATUS_NOT_VALIDATED}

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

    # Build child block
    child_slot = signed_block.message.slot + 1
    temp_state = state.copy()
    spec.process_slots(temp_state, child_slot)
    proposer_index = spec.get_beacon_proposer_index(temp_state)

    child_block = spec.BeaconBlock(
        slot=child_slot,
        proposer_index=proposer_index,
        parent_root=parent_root,
        state_root=temp_state.hash_tree_root(),
    )
    child_block.body.execution_payload = build_empty_execution_payload(spec, temp_state)
    signed_child = sign_block(spec, temp_state, child_block, proposer_index=proposer_index)

    yield get_filename(signed_child), signed_child

    block_time_ms = spec.compute_time_at_slot_ms(state, child_block.slot)

    yield "current_time_ms", "meta", int(block_time_ms)

    result, reason = run_validate_beacon_block_gossip(
        spec,
        seen,
        store,
        state,
        signed_child,
        block_time_ms + 500,
        block_payload_statuses=block_payload_statuses,
    )
    assert result == "valid"
    assert reason is None

    yield (
        "messages",
        "meta",
        [{"offset_ms": 500, "message": get_filename(signed_child), "expected": "valid"}],
    )


# ──────────────────────────────────────────────────────────────────────────────
# Inherited Phase 0 checks in Bellatrix-specific contexts
# (These tests cover Bellatrix behavior that is distinct from the Phase 0
# version of the same validation.)
# ──────────────────────────────────────────────────────────────────────────────


@with_phases([BELLATRIX])
@spec_state_test
def test_gossip_beacon_block__reject_parent_failed_validation(spec, state):
    """
    Test that when execution is disabled, a block whose parent failed validation
    is rejected.
    """
    yield "topic", "meta", "beacon_block"

    state = build_state_with_incomplete_transition(spec, state)
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)

    yield get_filename(signed_anchor), signed_anchor

    block = build_empty_block_for_next_slot(spec, state)
    block.body.execution_payload = spec.ExecutionPayload()
    signed_block = state_transition_and_sign_block(spec, state, block)

    yield get_filename(signed_block), signed_block

    # Add block to store.blocks but NOT to store.block_states (simulating failed validation)
    store.blocks[signed_block.message.hash_tree_root()] = signed_block.message

    yield (
        "blocks",
        "meta",
        [
            {"block": get_filename(signed_anchor)},
            {"block": get_filename(signed_block), "failed": True},
        ],
    )

    # Build child block with execution disabled
    child_slot = signed_block.message.slot + 1
    temp_state = state.copy()
    spec.process_slots(temp_state, child_slot)
    proposer_index = spec.get_beacon_proposer_index(temp_state)

    child_block = spec.BeaconBlock(
        slot=child_slot,
        proposer_index=proposer_index,
        parent_root=signed_block.message.hash_tree_root(),
        state_root=temp_state.hash_tree_root(),
    )
    child_block.body.execution_payload = spec.ExecutionPayload()
    signed_child = sign_block(spec, temp_state, child_block, proposer_index=proposer_index)

    yield get_filename(signed_child), signed_child

    block_time_ms = spec.compute_time_at_slot_ms(state, child_block.slot)

    yield "current_time_ms", "meta", int(block_time_ms)

    result, reason = run_validate_beacon_block_gossip(
        spec, seen, store, state, signed_child, block_time_ms + 500
    )
    assert result == "reject"
    assert reason == "block's parent is invalid and execution is not enabled"

    yield (
        "messages",
        "meta",
        [
            {
                "offset_ms": 500,
                "message": get_filename(signed_child),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_phases([BELLATRIX])
@spec_state_test
def test_gossip_beacon_block__reject_slot_not_higher_than_parent(spec, state):
    """
    Test that a block with slot <= parent slot is rejected.
    Uses execution-enabled block with proper execution payload.
    """
    yield "topic", "meta", "beacon_block"

    state = build_state_with_complete_transition(spec, state)
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)

    yield get_filename(signed_anchor), signed_anchor

    # Build and add a valid block at slot 1
    parent_block = build_empty_block_for_next_slot(spec, state)
    signed_parent = state_transition_and_sign_block(spec, state, parent_block)

    yield get_filename(signed_parent), signed_parent

    # Add parent to store
    store.blocks[signed_parent.message.hash_tree_root()] = signed_parent.message
    store.block_states[signed_parent.message.hash_tree_root()] = state.copy()

    yield (
        "blocks",
        "meta",
        [
            {"block": get_filename(signed_anchor)},
            {"block": get_filename(signed_parent)},
        ],
    )

    # Build a block at the same slot as parent (invalid)
    proposer_index = signed_parent.message.proposer_index

    block = spec.BeaconBlock(
        slot=signed_parent.message.slot,  # Same slot as parent - invalid!
        proposer_index=proposer_index,
        parent_root=signed_parent.message.hash_tree_root(),
        state_root=state.hash_tree_root(),
    )
    # Need to add execution payload with correct timestamp for this slot
    # Use a temp state at the same slot as the block
    temp_state = state.copy()
    block.body.execution_payload = build_empty_execution_payload(spec, temp_state)
    signed_block = sign_block(spec, state, block, proposer_index=proposer_index)

    yield get_filename(signed_block), signed_block

    block_time_ms = spec.compute_time_at_slot_ms(state, block.slot)

    yield "current_time_ms", "meta", int(block_time_ms)

    result, reason = run_validate_beacon_block_gossip(
        spec, seen, store, state, signed_block, block_time_ms + 500
    )
    assert result == "reject"
    assert reason == "block is not from a higher slot than its parent"

    yield (
        "messages",
        "meta",
        [
            {
                "offset_ms": 500,
                "message": get_filename(signed_block),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_phases([BELLATRIX])
@spec_state_test
def test_gossip_beacon_block__reject_finalized_checkpoint_not_ancestor(spec, state):
    """
    Test that a block whose finalized checkpoint is not an ancestor is rejected.
    Uses execution-enabled block with proper execution payload.
    """
    yield "topic", "meta", "beacon_block"

    state = build_state_with_complete_transition(spec, state)
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)

    yield get_filename(signed_anchor), signed_anchor

    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block)

    yield get_filename(signed_block), signed_block

    # Add block to store
    store.blocks[signed_block.message.hash_tree_root()] = signed_block.message
    store.block_states[signed_block.message.hash_tree_root()] = state.copy()

    yield (
        "blocks",
        "meta",
        [
            {"block": get_filename(signed_anchor)},
            {"block": get_filename(signed_block)},
        ],
    )

    # Set finalized checkpoint to something that is NOT an ancestor
    fake_finalized_root = spec.Root(b"\xab" * 32)
    store.finalized_checkpoint = spec.Checkpoint(
        epoch=spec.Epoch(0),
        root=fake_finalized_root,
    )

    yield "finalized_checkpoint", "meta", {"epoch": 0, "root": "0x" + "ab" * 32}

    # Build child block with proper execution payload
    child_slot = signed_block.message.slot + 1
    temp_state = state.copy()
    spec.process_slots(temp_state, child_slot)
    proposer_index = spec.get_beacon_proposer_index(temp_state)

    child_block = spec.BeaconBlock(
        slot=child_slot,
        proposer_index=proposer_index,
        parent_root=signed_block.message.hash_tree_root(),
        state_root=temp_state.hash_tree_root(),
    )
    child_block.body.execution_payload = build_empty_execution_payload(spec, temp_state)
    signed_child = sign_block(spec, temp_state, child_block, proposer_index=proposer_index)

    yield get_filename(signed_child), signed_child

    block_time_ms = spec.compute_time_at_slot_ms(state, child_block.slot)

    yield "current_time_ms", "meta", int(block_time_ms)

    result, reason = run_validate_beacon_block_gossip(
        spec, seen, store, state, signed_child, block_time_ms + 500
    )
    assert result == "reject"
    assert reason == "finalized checkpoint is not an ancestor of block"

    yield (
        "messages",
        "meta",
        [
            {
                "offset_ms": 500,
                "message": get_filename(signed_child),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )
