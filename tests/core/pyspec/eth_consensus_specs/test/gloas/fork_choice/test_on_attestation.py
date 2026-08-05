from eth_consensus_specs.test.context import (
    spec_state_test,
    with_gloas_and_later,
)
from eth_consensus_specs.test.helpers.attestations import get_valid_attestation
from eth_consensus_specs.test.helpers.execution_payload import (
    build_signed_execution_payload_envelope,
)
from eth_consensus_specs.test.helpers.fork_choice import (
    add_attestation,
    add_execution_payload,
    add_signed_empty_block,
    setup_one_block_store,
    tick_store_to_slot,
)
from eth_consensus_specs.test.helpers.state import transition_to


@with_gloas_and_later
@spec_state_test
def test_validate_on_attestation_same_slot_empty_vote(spec, state):
    """
    Test that an empty-node vote at the same slot as the
    attested block is accepted, regardless of payload verification.
    """
    store, _, block_state, _, test_steps = yield from setup_one_block_store(spec, state)

    # Get valid empty-node attestation at the anchor's slot.
    att = get_valid_attestation(spec, block_state, payload_index=0, signed=True)

    tick_store_to_slot(spec, store, att.data.slot + 1, test_steps)
    yield from add_attestation(spec, store, att, test_steps)
    yield "steps", test_steps


@with_gloas_and_later
@spec_state_test
def test_validate_on_attestation_same_slot_full_vote_rejected(spec, state):
    """
    Test that a full-node vote at the same slot as the
    attested block is rejected even if the payload is verified.
    """
    store, block_root, block_state, signed_block, test_steps = yield from setup_one_block_store(
        spec, state
    )
    envelope = build_signed_execution_payload_envelope(spec, block_state, block_root, signed_block)
    yield from add_execution_payload(spec, store, envelope, test_steps)

    # Get valid full-node attestation at the anchor's slot.
    att = get_valid_attestation(spec, block_state, payload_index=1, signed=True)

    tick_store_to_slot(spec, store, block_state.slot + 1, test_steps)
    yield from add_attestation(spec, store, att, test_steps, valid=False)
    yield "steps", test_steps


@with_gloas_and_later
@spec_state_test
def test_validate_on_attestation_later_slot_full_vote_valid(spec, state):
    """
    Test that a full-node vote at a later slot referencing a block with a
    verified payload is accepted.
    """
    store, block_root, block_state, signed_block, test_steps = yield from setup_one_block_store(
        spec, state
    )
    envelope = build_signed_execution_payload_envelope(spec, block_state, block_root, signed_block)
    yield from add_execution_payload(spec, store, envelope, test_steps)

    state_at_2 = block_state.copy()
    transition_to(spec, state_at_2, spec.Slot(2))

    # Get valid attestation at slot 2 for a full-node vote for slot 1.
    att = get_valid_attestation(
        spec,
        state_at_2,
        slot=spec.Slot(2),
        payload_index=1,
        beacon_block_root=block_root,
        signed=True,
    )

    tick_store_to_slot(spec, store, att.data.slot + 1, test_steps)
    yield from add_attestation(spec, store, att, test_steps)
    yield "steps", test_steps


@with_gloas_and_later
@spec_state_test
def test_validate_on_attestation_payload_invalid_index(spec, state):
    """
    Test that an attestation with an invalid index is rejected.
    """
    store, _, block_state, _, test_steps = yield from setup_one_block_store(spec, state)
    tick_store_to_slot(spec, store, block_state.slot + 1, test_steps)

    # Get attestation with an invalid index.
    att = get_valid_attestation(spec, block_state, payload_index=2, signed=True)

    yield from add_attestation(spec, store, att, test_steps, valid=False)
    yield "steps", test_steps


@with_gloas_and_later
@spec_state_test
def test_validate_on_attestation_beacon_root_payload_check(spec, state):
    """
    Test that a full-node vote requires the beacon block root's payload to
    be verified.
    """
    store, _, block_state, _, test_steps = yield from setup_one_block_store(spec, state)

    # Build across the epoch boundary
    target_slot = spec.compute_start_slot_at_epoch(spec.Epoch(1))
    beacon_slot = spec.Slot(target_slot + 1)
    chain_state = block_state.copy()
    while chain_state.slot < target_slot:
        target_root, target_state, target_block = yield from add_signed_empty_block(
            spec, store, chain_state, test_steps
        )

    # Build one more block at beacon_slot
    beacon_root, beacon_state, _ = yield from add_signed_empty_block(
        spec, store, chain_state, test_steps
    )

    # Verify the target's payload
    envelope = build_signed_execution_payload_envelope(
        spec, target_state, target_root, target_block
    )
    yield from add_execution_payload(spec, store, envelope, test_steps)

    # Build a full-node vote past the head
    att_slot = spec.Slot(beacon_slot + 1)
    att_state = beacon_state.copy()
    transition_to(spec, att_state, att_slot)
    att = get_valid_attestation(spec, att_state, slot=att_slot, payload_index=1, signed=True)
    assert att.data.target.root == target_root
    assert att.data.beacon_block_root == beacon_root

    tick_store_to_slot(spec, store, att_slot + 1, test_steps)
    yield from add_attestation(spec, store, att, test_steps, valid=False)
    yield "steps", test_steps
