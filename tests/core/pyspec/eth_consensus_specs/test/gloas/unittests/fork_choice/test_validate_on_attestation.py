from eth_consensus_specs.test.context import (
    expect_assertion_error,
    spec_state_test,
    with_gloas_and_later,
)
from eth_consensus_specs.test.helpers.attestations import get_valid_attestation
from eth_consensus_specs.test.helpers.block import build_empty_block_for_next_slot
from eth_consensus_specs.test.helpers.execution_payload import (
    build_signed_execution_payload_envelope,
)
from eth_consensus_specs.test.helpers.fork_choice import get_genesis_forkchoice_store
from eth_consensus_specs.test.helpers.state import state_transition_and_sign_block


def _tick_to_slot(spec, store, slot):
    target_time = store.genesis_time + slot * spec.config.SLOT_DURATION_MS // 1000
    spec.on_tick(store, target_time)


def _build_store_with_block(spec, state):
    """
    Build genesis store, apply one signed block at slot 1
    """
    store = get_genesis_forkchoice_store(spec, state)
    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block)

    _tick_to_slot(spec, store, signed_block.message.slot)
    spec.on_block(store, signed_block)

    return store, signed_block


@with_gloas_and_later
@spec_state_test
def test_validate_on_attestation_invalid_index(spec, state):
    """
    Test that an attestation with an invalid index fails
    """
    store, signed_block = _build_store_with_block(spec, state)
    block_root = signed_block.message.hash_tree_root()

    # Build payload
    signed_envelope = build_signed_execution_payload_envelope(spec, state, block_root, signed_block)
    spec.on_execution_payload_envelope(store, signed_envelope)

    # Process slot
    spec.process_slots(state, state.slot + 1)
    _tick_to_slot(spec, store, state.slot + 1)

    # Get bad index attestation
    attestation = get_valid_attestation(spec, state, slot=state.slot, payload_index=2, signed=False)
    assert block_root in store.payloads

    expect_assertion_error(
        lambda: spec.validate_on_attestation(store, attestation, is_from_block=False)
    )


@with_gloas_and_later
@spec_state_test
def test_validate_on_attestation_same_slot_full_node(spec, state):
    """
    Test that a same slot attestation signaling a full node fails
    """
    store, signed_block = _build_store_with_block(spec, state)
    block_root = signed_block.message.hash_tree_root()

    # Build payload
    signed_envelope = build_signed_execution_payload_envelope(spec, state, block_root, signed_block)
    spec.on_execution_payload_envelope(store, signed_envelope)

    # Skip slot processing

    _tick_to_slot(spec, store, state.slot + 1)

    attestation = get_valid_attestation(spec, state, slot=state.slot, payload_index=1, signed=False)
    assert attestation.data.slot == signed_block.message.slot
    assert block_root in store.payloads

    expect_assertion_error(
        lambda: spec.validate_on_attestation(store, attestation, is_from_block=False)
    )


@with_gloas_and_later
@spec_state_test
def test_validate_on_attestation_same_slot_empty_node_no_payload(spec, state):
    """
    Test that a same slot attestation signaling empty for an actual empty node passes validation
    """
    store, signed_block = _build_store_with_block(spec, state)
    block_root = signed_block.message.hash_tree_root()

    # Skip payload building
    # Skip slot processing

    _tick_to_slot(spec, store, state.slot + 1)

    # Get attestation for same slot signaling empty node
    attestation = get_valid_attestation(spec, state, slot=state.slot, payload_index=0, signed=False)
    assert attestation.data.slot == signed_block.message.slot
    assert block_root not in store.payloads

    spec.validate_on_attestation(store, attestation, is_from_block=False)


@with_gloas_and_later
@spec_state_test
def test_validate_on_attestation_same_slot_empty_node_verified_payload(spec, state):
    """
    Test that a same slot attestation signaling an empty node for an actually full one passes validation
    """
    store, signed_block = _build_store_with_block(spec, state)
    block_root = signed_block.message.hash_tree_root()

    # Build payload
    signed_envelope = build_signed_execution_payload_envelope(spec, state, block_root, signed_block)
    spec.on_execution_payload_envelope(store, signed_envelope)

    # Skip slot processing

    _tick_to_slot(spec, store, state.slot + 1)

    # Get attestation for same slot signaling empty node
    attestation = get_valid_attestation(spec, state, slot=state.slot, payload_index=0, signed=False)
    assert attestation.data.slot == signed_block.message.slot
    assert block_root in store.payloads

    spec.validate_on_attestation(store, attestation, is_from_block=False)


@with_gloas_and_later
@spec_state_test
def test_validate_on_attestation_empty_node_no_payload(spec, state):
    """
    Test that an attestation signaling empty for an actual empty node passes validation
    """
    store, signed_block = _build_store_with_block(spec, state)
    block_root = signed_block.message.hash_tree_root()

    # Skip payload building

    spec.process_slots(state, state.slot + 1)
    _tick_to_slot(spec, store, state.slot + 1)

    # Signal empty node, local store has no payload
    attestation = get_valid_attestation(spec, state, slot=state.slot, payload_index=0, signed=False)
    assert attestation.data.slot > signed_block.message.slot
    assert block_root not in store.payloads

    spec.validate_on_attestation(store, attestation, is_from_block=False)


@with_gloas_and_later
@spec_state_test
def test_validate_on_attestation_full_node_no_payload(spec, state):
    """
    Test that an attestation signaling full node for an actually empty one fails
    """
    store, signed_block = _build_store_with_block(spec, state)
    block_root = signed_block.message.hash_tree_root()

    # Skip building and processing payload.

    spec.process_slots(state, state.slot + 1)
    _tick_to_slot(spec, store, state.slot + 1)

    # Signal full node, but local store has no payload
    attestation = get_valid_attestation(spec, state, slot=state.slot, payload_index=1, signed=False)
    assert attestation.data.slot > signed_block.message.slot
    assert block_root not in store.payloads

    expect_assertion_error(
        lambda: spec.validate_on_attestation(store, attestation, is_from_block=False)
    )


@with_gloas_and_later
@spec_state_test
def test_validate_on_attestation_full_node_verified_payload(spec, state):
    """
    Test that an attestation for a full node with a verified payload passes validation
    """
    store, signed_block = _build_store_with_block(spec, state)
    block_root = signed_block.message.hash_tree_root()

    # Build payload
    signed_envelope = build_signed_execution_payload_envelope(spec, state, block_root, signed_block)
    spec.on_execution_payload_envelope(store, signed_envelope)

    spec.process_slots(state, state.slot + 1)
    _tick_to_slot(spec, store, state.slot + 1)

    # Signal full node
    attestation = get_valid_attestation(spec, state, slot=state.slot, payload_index=1, signed=False)
    assert attestation.data.slot > signed_block.message.slot
    assert block_root in store.payloads

    spec.validate_on_attestation(store, attestation, is_from_block=False)
