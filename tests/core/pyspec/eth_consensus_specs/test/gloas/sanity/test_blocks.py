from eth_consensus_specs.test.context import (
    spec_state_test,
    with_gloas_and_later,
)
from eth_consensus_specs.test.gloas.block_processing.test_process_payload_attestation import (
    prepare_signed_payload_attestation,
)
from eth_consensus_specs.test.helpers.block import (
    build_empty_block_for_next_slot,
)
from eth_consensus_specs.test.helpers.payload_attestation import (
    get_random_payload_attestations,
)
from eth_consensus_specs.test.helpers.state import (
    state_transition_and_sign_block,
)


@with_gloas_and_later
@spec_state_test
def test_payload_attestation_included_in_block(spec, state):
    """
    Test that payload attestations can be included in a block and processed correctly.
    """
    yield "pre", state

    # Advance to next slot to allow payload attestations for the parent block
    block = build_empty_block_for_next_slot(spec, state)

    # Get random payload attestations for the parent block
    payload_attestations = get_random_payload_attestations(
        spec, state, rng=__import__("random").Random(1234)
    )
    block.body.payload_attestations = payload_attestations

    signed_block = state_transition_and_sign_block(spec, state, block)

    yield "blocks", [signed_block]
    yield "post", state


@with_gloas_and_later
@spec_state_test
def test_payload_attestation_with_full_participation(spec, state):
    """
    Test that payload attestations with full PTC participation are processed correctly.
    """
    yield "pre", state

    block = build_empty_block_for_next_slot(spec, state)

    # Get PTC for parent block slot
    parent_slot = state.latest_block_header.slot
    ptc = spec.get_ptc(state, parent_slot)

    if len(ptc) > 0:
        # Create payload attestation with all PTC members
        parent_header = state.latest_block_header.copy()
        if parent_header.state_root == spec.Root():
            parent_header.state_root = spec.hash_tree_root(state)
        beacon_block_root = spec.hash_tree_root(parent_header)

        payload_attestation = prepare_signed_payload_attestation(
            spec,
            state,
            slot=parent_slot,
            beacon_block_root=beacon_block_root,
            payload_present=True,
            attesting_indices=ptc,
        )
        block.body.payload_attestations = [payload_attestation]

    signed_block = state_transition_and_sign_block(spec, state, block)

    yield "blocks", [signed_block]
    yield "post", state


@with_gloas_and_later
@spec_state_test
def test_payload_attestation_with_partial_participation(spec, state):
    """
    Test that payload attestations with partial PTC participation are processed correctly.
    """
    yield "pre", state

    block = build_empty_block_for_next_slot(spec, state)

    parent_slot = state.latest_block_header.slot
    ptc = spec.get_ptc(state, parent_slot)

    if len(ptc) > 0:
        # Create payload attestation with half of the PTC members
        attesting_indices = ptc[: len(ptc) // 2] if len(ptc) > 1 else ptc

        parent_header = state.latest_block_header.copy()
        if parent_header.state_root == spec.Root():
            parent_header.state_root = spec.hash_tree_root(state)
        beacon_block_root = spec.hash_tree_root(parent_header)

        payload_attestation = prepare_signed_payload_attestation(
            spec,
            state,
            slot=parent_slot,
            beacon_block_root=beacon_block_root,
            payload_present=True,
            attesting_indices=attesting_indices,
        )
        block.body.payload_attestations = [payload_attestation]

    signed_block = state_transition_and_sign_block(spec, state, block)

    yield "blocks", [signed_block]
    yield "post", state


@with_gloas_and_later
@spec_state_test
def test_payload_attestation_payload_not_present(spec, state):
    """
    Test that payload attestations indicating payload not present are processed correctly.
    """
    yield "pre", state

    block = build_empty_block_for_next_slot(spec, state)

    parent_slot = state.latest_block_header.slot
    ptc = spec.get_ptc(state, parent_slot)

    if len(ptc) > 0:
        parent_header = state.latest_block_header.copy()
        if parent_header.state_root == spec.Root():
            parent_header.state_root = spec.hash_tree_root(state)
        beacon_block_root = spec.hash_tree_root(parent_header)

        payload_attestation = prepare_signed_payload_attestation(
            spec,
            state,
            slot=parent_slot,
            beacon_block_root=beacon_block_root,
            payload_present=False,
            attesting_indices=ptc,
        )
        block.body.payload_attestations = [payload_attestation]

    signed_block = state_transition_and_sign_block(spec, state, block)

    yield "blocks", [signed_block]
    yield "post", state


@with_gloas_and_later
@spec_state_test
def test_multiple_payload_attestations_in_block(spec, state):
    """
    Test that multiple payload attestations can be included in a single block.
    """
    yield "pre", state

    block = build_empty_block_for_next_slot(spec, state)

    parent_slot = state.latest_block_header.slot
    ptc = spec.get_ptc(state, parent_slot)

    payload_attestations = []
    if len(ptc) > 1:
        parent_header = state.latest_block_header.copy()
        if parent_header.state_root == spec.Root():
            parent_header.state_root = spec.hash_tree_root(state)
        beacon_block_root = spec.hash_tree_root(parent_header)

        # Create multiple attestations with different participants
        half = len(ptc) // 2

        # First attestation: first half with payload present
        attestation_1 = prepare_signed_payload_attestation(
            spec,
            state,
            slot=parent_slot,
            beacon_block_root=beacon_block_root,
            payload_present=True,
            attesting_indices=ptc[:half],
        )
        payload_attestations.append(attestation_1)

        # Second attestation: second half with payload not present
        attestation_2 = prepare_signed_payload_attestation(
            spec,
            state,
            slot=parent_slot,
            beacon_block_root=beacon_block_root,
            payload_present=False,
            attesting_indices=ptc[half:],
        )
        payload_attestations.append(attestation_2)

    block.body.payload_attestations = payload_attestations

    signed_block = state_transition_and_sign_block(spec, state, block)

    yield "blocks", [signed_block]
    yield "post", state


@with_gloas_and_later
@spec_state_test
def test_invalid_payload_attestation_wrong_beacon_block_root(spec, state):
    """
    Test that payload attestation with wrong beacon_block_root fails.
    """
    yield "pre", state

    block = build_empty_block_for_next_slot(spec, state)

    parent_slot = state.latest_block_header.slot
    ptc = spec.get_ptc(state, parent_slot)

    if len(ptc) > 0:
        wrong_root = spec.Root(b"\x42" * 32)
        payload_attestation = prepare_signed_payload_attestation(
            spec,
            state,
            slot=parent_slot,
            beacon_block_root=wrong_root,
            payload_present=True,
            attesting_indices=ptc,
        )
        block.body.payload_attestations = [payload_attestation]

    signed_block = state_transition_and_sign_block(spec, state, block, expect_fail=True)

    yield "blocks", [signed_block]
    yield "post", None


@with_gloas_and_later
@spec_state_test
def test_invalid_payload_attestation_too_old_slot(spec, state):
    """
    Test that payload attestation for slot too far in past fails.
    """
    yield "pre", state

    # Advance state to slot 3
    spec.process_slots(state, state.slot + 3)

    block = build_empty_block_for_next_slot(spec, state)

    ptc = spec.get_ptc(state, state.slot - 2)

    if len(ptc) > 0:
        parent_header = state.latest_block_header.copy()
        if parent_header.state_root == spec.Root():
            parent_header.state_root = spec.hash_tree_root(state)
        beacon_block_root = spec.hash_tree_root(parent_header)

        payload_attestation = prepare_signed_payload_attestation(
            spec,
            state,
            slot=state.slot - 2,  # Too old - should fail
            beacon_block_root=beacon_block_root,
            payload_present=True,
            attesting_indices=ptc,
        )
        block.body.payload_attestations = [payload_attestation]

    signed_block = state_transition_and_sign_block(spec, state, block, expect_fail=True)

    yield "blocks", [signed_block]
    yield "post", None


@with_gloas_and_later
@spec_state_test
def test_invalid_payload_attestation_invalid_signature(spec, state):
    """
    Test that payload attestation with invalid signature fails.
    """
    yield "pre", state

    block = build_empty_block_for_next_slot(spec, state)

    parent_slot = state.latest_block_header.slot
    ptc = spec.get_ptc(state, parent_slot)

    if len(ptc) > 0:
        parent_header = state.latest_block_header.copy()
        if parent_header.state_root == spec.Root():
            parent_header.state_root = spec.hash_tree_root(state)
        beacon_block_root = spec.hash_tree_root(parent_header)

        payload_attestation = prepare_signed_payload_attestation(
            spec,
            state,
            slot=parent_slot,
            beacon_block_root=beacon_block_root,
            payload_present=True,
            attesting_indices=ptc,
            valid_signature=False,
        )
        block.body.payload_attestations = [payload_attestation]

    signed_block = state_transition_and_sign_block(spec, state, block, expect_fail=True)

    yield "blocks", [signed_block]
    yield "post", None
