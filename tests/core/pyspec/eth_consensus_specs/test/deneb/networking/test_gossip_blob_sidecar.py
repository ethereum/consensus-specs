import random

from eth_consensus_specs.test.context import (
    always_bls,
    spec_state_test,
    with_phases,
)
from eth_consensus_specs.test.helpers.blob import get_block_with_blob
from eth_consensus_specs.test.helpers.block import build_empty_block_for_next_slot
from eth_consensus_specs.test.helpers.constants import DENEB
from eth_consensus_specs.test.helpers.execution_payload import (
    build_state_with_complete_transition,
)
from eth_consensus_specs.test.helpers.fork_choice import (
    get_genesis_forkchoice_store_and_block,
)
from eth_consensus_specs.test.helpers.gossip import get_filename, get_seen, wrap_genesis_block
from eth_consensus_specs.test.helpers.keys import privkeys
from eth_consensus_specs.test.helpers.state import (
    state_transition_and_sign_block,
    transition_to,
)


def build_signed_block_and_sidecars(spec, state, rng=None, blob_count=1):
    """
    Build a signed block carrying ``blob_count`` blobs, applying the state
    transition. Returns (signed_block, blob_sidecars).
    """
    rng = rng or random.Random(1234)
    block, blobs, _, blob_kzg_proofs = get_block_with_blob(
        spec, state, rng=rng, blob_count=blob_count
    )
    signed_block = state_transition_and_sign_block(spec, state, block)
    sidecars = spec.get_blob_sidecars(signed_block, blobs, blob_kzg_proofs)
    return signed_block, list(sidecars)


def setup_store_with_anchor(spec, state):
    """Return a store seeded with the genesis anchor block."""
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    return store, anchor_block


def run_validate_blob_sidecar_gossip(
    spec, seen, store, state, blob_sidecar, subnet_id, current_time_ms
):
    try:
        spec.validate_blob_sidecar_gossip(
            seen, store, state, blob_sidecar, subnet_id, current_time_ms
        )
        return "valid", None
    except spec.GossipIgnore as e:
        return "ignore", str(e)
    except spec.GossipReject as e:
        return "reject", str(e)


def correct_subnet(spec, blob_sidecar):
    return spec.compute_subnet_for_blob_sidecar(blob_sidecar.index)


def resign_blob_sidecar_header(spec, state, blob_sidecar):
    proposer_index = blob_sidecar.signed_block_header.message.proposer_index
    domain = spec.get_domain(
        state,
        spec.DOMAIN_BEACON_PROPOSER,
        spec.compute_epoch_at_slot(blob_sidecar.signed_block_header.message.slot),
    )
    signing_root = spec.compute_signing_root(blob_sidecar.signed_block_header.message, domain)
    blob_sidecar.signed_block_header.signature = spec.bls.Sign(
        privkeys[proposer_index], signing_root
    )


@with_phases([DENEB])
@spec_state_test
def test_gossip_blob_sidecar__valid(spec, state):
    """Test that a valid blob sidecar passes gossip validation."""
    yield "topic", "meta", "blob_sidecar"

    state = build_state_with_complete_transition(spec, state)
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = setup_store_with_anchor(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    _, sidecars = build_signed_block_and_sidecars(spec, state, blob_count=1)
    blob_sidecar = sidecars[0]

    yield get_filename(blob_sidecar), blob_sidecar

    block_time_ms = spec.compute_time_at_slot_ms(
        state, blob_sidecar.signed_block_header.message.slot
    )
    yield "current_time_ms", "meta", int(block_time_ms)

    subnet_id = correct_subnet(spec, blob_sidecar)
    result, reason = run_validate_blob_sidecar_gossip(
        spec, seen, store, state, blob_sidecar, subnet_id, block_time_ms + 500
    )
    assert result == "valid"
    assert reason is None

    yield (
        "messages",
        "meta",
        [
            {
                "subnet_id": int(subnet_id),
                "offset_ms": 500,
                "message": get_filename(blob_sidecar),
                "expected": "valid",
            }
        ],
    )


@with_phases([DENEB])
@spec_state_test
def test_gossip_blob_sidecar__reject_index_out_of_range(spec, state):
    """Test that a blob sidecar with index >= MAX_BLOBS_PER_BLOCK is rejected."""
    yield "topic", "meta", "blob_sidecar"

    state = build_state_with_complete_transition(spec, state)
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = setup_store_with_anchor(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    _, sidecars = build_signed_block_and_sidecars(spec, state, blob_count=1)
    blob_sidecar = sidecars[0]
    blob_sidecar.index = spec.BlobIndex(spec.config.MAX_BLOBS_PER_BLOCK)

    yield get_filename(blob_sidecar), blob_sidecar

    block_time_ms = spec.compute_time_at_slot_ms(
        state, blob_sidecar.signed_block_header.message.slot
    )
    yield "current_time_ms", "meta", int(block_time_ms)

    subnet_id = spec.SubnetID(0)
    result, reason = run_validate_blob_sidecar_gossip(
        spec, seen, store, state, blob_sidecar, subnet_id, block_time_ms + 500
    )
    assert result == "reject"
    assert reason == "blob index out of range"

    yield (
        "messages",
        "meta",
        [
            {
                "subnet_id": int(subnet_id),
                "offset_ms": 500,
                "message": get_filename(blob_sidecar),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_phases([DENEB])
@spec_state_test
def test_gossip_blob_sidecar__reject_wrong_subnet(spec, state):
    """Test that a blob sidecar on the wrong subnet is rejected."""
    yield "topic", "meta", "blob_sidecar"

    state = build_state_with_complete_transition(spec, state)
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = setup_store_with_anchor(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    _, sidecars = build_signed_block_and_sidecars(spec, state, blob_count=1)
    blob_sidecar = sidecars[0]

    yield get_filename(blob_sidecar), blob_sidecar

    block_time_ms = spec.compute_time_at_slot_ms(
        state, blob_sidecar.signed_block_header.message.slot
    )
    yield "current_time_ms", "meta", int(block_time_ms)

    expected_subnet = correct_subnet(spec, blob_sidecar)
    wrong_subnet = spec.SubnetID((int(expected_subnet) + 1) % spec.config.BLOB_SIDECAR_SUBNET_COUNT)
    result, reason = run_validate_blob_sidecar_gossip(
        spec, seen, store, state, blob_sidecar, wrong_subnet, block_time_ms + 500
    )
    assert result == "reject"
    assert reason == "blob sidecar is for wrong subnet"

    yield (
        "messages",
        "meta",
        [
            {
                "subnet_id": int(wrong_subnet),
                "offset_ms": 500,
                "message": get_filename(blob_sidecar),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_phases([DENEB])
@spec_state_test
@always_bls
def test_gossip_blob_sidecar__reject_invalid_proposer_signature(spec, state):
    """Test that a blob sidecar with an invalid block header signature is rejected."""
    yield "topic", "meta", "blob_sidecar"

    state = build_state_with_complete_transition(spec, state)
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = setup_store_with_anchor(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    _, sidecars = build_signed_block_and_sidecars(spec, state, blob_count=1)
    blob_sidecar = sidecars[0]
    # Corrupt the signature
    blob_sidecar.signed_block_header.signature = spec.BLSSignature(b"\x00" * 96)

    yield get_filename(blob_sidecar), blob_sidecar

    block_time_ms = spec.compute_time_at_slot_ms(
        state, blob_sidecar.signed_block_header.message.slot
    )
    yield "current_time_ms", "meta", int(block_time_ms)

    subnet_id = correct_subnet(spec, blob_sidecar)
    result, reason = run_validate_blob_sidecar_gossip(
        spec, seen, store, state, blob_sidecar, subnet_id, block_time_ms + 500
    )
    assert result == "reject"
    assert reason == "invalid proposer signature on blob sidecar block header"

    yield (
        "messages",
        "meta",
        [
            {
                "subnet_id": int(subnet_id),
                "offset_ms": 500,
                "message": get_filename(blob_sidecar),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_phases([DENEB])
@spec_state_test
def test_gossip_blob_sidecar__reject_invalid_inclusion_proof(spec, state):
    """Test that a blob sidecar with a broken inclusion proof is rejected."""
    yield "topic", "meta", "blob_sidecar"

    state = build_state_with_complete_transition(spec, state)
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = setup_store_with_anchor(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    _, sidecars = build_signed_block_and_sidecars(spec, state, blob_count=1)
    blob_sidecar = sidecars[0]
    # Corrupt the inclusion proof
    blob_sidecar.kzg_commitment_inclusion_proof = spec.compute_merkle_proof(
        spec.BeaconBlockBody(), 0
    )
    resign_blob_sidecar_header(spec, state, blob_sidecar)

    yield get_filename(blob_sidecar), blob_sidecar

    block_time_ms = spec.compute_time_at_slot_ms(
        state, blob_sidecar.signed_block_header.message.slot
    )
    yield "current_time_ms", "meta", int(block_time_ms)

    subnet_id = correct_subnet(spec, blob_sidecar)
    result, reason = run_validate_blob_sidecar_gossip(
        spec, seen, store, state, blob_sidecar, subnet_id, block_time_ms + 500
    )
    assert result == "reject"
    assert reason == "invalid blob sidecar inclusion proof"

    yield (
        "messages",
        "meta",
        [
            {
                "subnet_id": int(subnet_id),
                "offset_ms": 500,
                "message": get_filename(blob_sidecar),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_phases([DENEB])
@spec_state_test
def test_gossip_blob_sidecar__reject_invalid_kzg_proof(spec, state):
    """Test that a blob sidecar with an invalid KZG proof is rejected."""
    yield "topic", "meta", "blob_sidecar"

    state = build_state_with_complete_transition(spec, state)
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = setup_store_with_anchor(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    _, sidecars = build_signed_block_and_sidecars(spec, state, blob_count=1)
    blob_sidecar = sidecars[0]
    # Corrupt the KZG proof to a zero point (invalid relative to the real commitment)
    blob_sidecar.kzg_proof = spec.KZGProof(b"\xc0" + b"\x00" * 47)

    yield get_filename(blob_sidecar), blob_sidecar

    block_time_ms = spec.compute_time_at_slot_ms(
        state, blob_sidecar.signed_block_header.message.slot
    )
    yield "current_time_ms", "meta", int(block_time_ms)

    subnet_id = correct_subnet(spec, blob_sidecar)
    result, reason = run_validate_blob_sidecar_gossip(
        spec, seen, store, state, blob_sidecar, subnet_id, block_time_ms + 500
    )
    assert result == "reject"
    assert reason == "invalid blob kzg proof"

    yield (
        "messages",
        "meta",
        [
            {
                "subnet_id": int(subnet_id),
                "offset_ms": 500,
                "message": get_filename(blob_sidecar),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_phases([DENEB])
@spec_state_test
def test_gossip_blob_sidecar__ignore_future_slot(spec, state):
    """Test that a blob sidecar from a future slot is ignored."""
    yield "topic", "meta", "blob_sidecar"

    state = build_state_with_complete_transition(spec, state)
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = setup_store_with_anchor(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    _, sidecars = build_signed_block_and_sidecars(spec, state, blob_count=1)
    blob_sidecar = sidecars[0]

    yield get_filename(blob_sidecar), blob_sidecar

    slot_time_ms = spec.compute_time_at_slot_ms(
        state, blob_sidecar.signed_block_header.message.slot
    )
    current_time_ms = slot_time_ms - spec.config.MAXIMUM_GOSSIP_CLOCK_DISPARITY - 1
    yield "current_time_ms", "meta", int(current_time_ms)

    subnet_id = correct_subnet(spec, blob_sidecar)
    result, reason = run_validate_blob_sidecar_gossip(
        spec, seen, store, state, blob_sidecar, subnet_id, current_time_ms
    )
    assert result == "ignore"
    assert reason == "blob sidecar is from a future slot"

    yield (
        "messages",
        "meta",
        [
            {
                "subnet_id": int(subnet_id),
                "offset_ms": 0,
                "message": get_filename(blob_sidecar),
                "expected": "ignore",
                "reason": reason,
            }
        ],
    )


@with_phases([DENEB])
@spec_state_test
def test_gossip_blob_sidecar__valid_slot_within_clock_disparity(spec, state):
    """Test that a blob sidecar at the future-slot boundary is valid."""
    yield "topic", "meta", "blob_sidecar"

    state = build_state_with_complete_transition(spec, state)
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = setup_store_with_anchor(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    _, sidecars = build_signed_block_and_sidecars(spec, state, blob_count=1)
    blob_sidecar = sidecars[0]

    yield get_filename(blob_sidecar), blob_sidecar

    slot_time_ms = spec.compute_time_at_slot_ms(
        state, blob_sidecar.signed_block_header.message.slot
    )
    current_time_ms = slot_time_ms - spec.config.MAXIMUM_GOSSIP_CLOCK_DISPARITY
    yield "current_time_ms", "meta", int(current_time_ms)

    subnet_id = correct_subnet(spec, blob_sidecar)
    result, reason = run_validate_blob_sidecar_gossip(
        spec, seen, store, state, blob_sidecar, subnet_id, current_time_ms
    )
    assert result == "valid"
    assert reason is None

    yield (
        "messages",
        "meta",
        [
            {
                "subnet_id": int(subnet_id),
                "offset_ms": 0,
                "message": get_filename(blob_sidecar),
                "expected": "valid",
            }
        ],
    )


@with_phases([DENEB])
@spec_state_test
def test_gossip_blob_sidecar__ignore_not_later_than_finalized_slot(spec, state):
    """Test that a blob sidecar at the latest finalized slot is ignored."""
    yield "topic", "meta", "blob_sidecar"

    state = build_state_with_complete_transition(spec, state)
    seen = get_seen(spec)
    store, anchor_block = setup_store_with_anchor(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    transition_to(spec, state, spec.Slot(spec.SLOTS_PER_EPOCH - 1))
    yield "state", state

    _, sidecars = build_signed_block_and_sidecars(spec, state, blob_count=1)
    blob_sidecar = sidecars[0]

    block_header = blob_sidecar.signed_block_header.message
    sidecar_epoch = spec.compute_epoch_at_slot(block_header.slot)
    store.finalized_checkpoint = spec.Checkpoint(
        epoch=sidecar_epoch,
        root=store.finalized_checkpoint.root,
    )
    yield (
        "finalized_checkpoint",
        "meta",
        {
            "epoch": int(sidecar_epoch),
            "block": get_filename(signed_anchor),
        },
    )

    yield get_filename(blob_sidecar), blob_sidecar

    block_time_ms = spec.compute_time_at_slot_ms(state, block_header.slot)
    yield "current_time_ms", "meta", int(block_time_ms)

    subnet_id = correct_subnet(spec, blob_sidecar)
    result, reason = run_validate_blob_sidecar_gossip(
        spec, seen, store, state, blob_sidecar, subnet_id, block_time_ms + 500
    )
    assert result == "ignore"
    assert reason == "blob sidecar is not from a slot greater than the latest finalized slot"

    yield (
        "messages",
        "meta",
        [
            {
                "subnet_id": int(subnet_id),
                "offset_ms": 500,
                "message": get_filename(blob_sidecar),
                "expected": "ignore",
                "reason": reason,
            }
        ],
    )


@with_phases([DENEB])
@spec_state_test
def test_gossip_blob_sidecar__reject_proposer_index_out_of_range(spec, state):
    """Test that a blob sidecar with proposer_index out of range is rejected."""
    yield "topic", "meta", "blob_sidecar"

    state = build_state_with_complete_transition(spec, state)
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = setup_store_with_anchor(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    _, sidecars = build_signed_block_and_sidecars(spec, state, blob_count=1)
    blob_sidecar = sidecars[0]
    blob_sidecar.signed_block_header.message.proposer_index = spec.ValidatorIndex(
        len(state.validators)
    )

    yield get_filename(blob_sidecar), blob_sidecar

    block_time_ms = spec.compute_time_at_slot_ms(
        state, blob_sidecar.signed_block_header.message.slot
    )
    yield "current_time_ms", "meta", int(block_time_ms)

    subnet_id = correct_subnet(spec, blob_sidecar)
    result, reason = run_validate_blob_sidecar_gossip(
        spec, seen, store, state, blob_sidecar, subnet_id, block_time_ms + 500
    )
    assert result == "reject"
    assert reason == "proposer index out of range"

    yield (
        "messages",
        "meta",
        [
            {
                "subnet_id": int(subnet_id),
                "offset_ms": 500,
                "message": get_filename(blob_sidecar),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_phases([DENEB])
@spec_state_test
def test_gossip_blob_sidecar__ignore_parent_not_seen(spec, state):
    """Test that a blob sidecar whose parent is unknown to the store is ignored."""
    yield "topic", "meta", "blob_sidecar"

    state = build_state_with_complete_transition(spec, state)
    yield "state", state

    seen = get_seen(spec)
    store, _ = setup_store_with_anchor(spec, state)
    # Drop anchor from store so the parent_root check fails
    store.blocks = {}
    store.block_states = {}

    _, sidecars = build_signed_block_and_sidecars(spec, state, blob_count=1)
    blob_sidecar = sidecars[0]

    yield get_filename(blob_sidecar), blob_sidecar

    block_time_ms = spec.compute_time_at_slot_ms(
        state, blob_sidecar.signed_block_header.message.slot
    )
    yield "current_time_ms", "meta", int(block_time_ms)

    subnet_id = correct_subnet(spec, blob_sidecar)
    result, reason = run_validate_blob_sidecar_gossip(
        spec, seen, store, state, blob_sidecar, subnet_id, block_time_ms + 500
    )
    assert result == "ignore"
    assert reason == "blob sidecar's parent has not been seen"

    yield (
        "messages",
        "meta",
        [
            {
                "subnet_id": int(subnet_id),
                "offset_ms": 500,
                "message": get_filename(blob_sidecar),
                "expected": "ignore",
                "reason": reason,
            }
        ],
    )


@with_phases([DENEB])
@spec_state_test
def test_gossip_blob_sidecar__reject_parent_failed_validation(spec, state):
    """Test that a blob sidecar whose parent failed validation is rejected."""
    yield "topic", "meta", "blob_sidecar"

    state = build_state_with_complete_transition(spec, state)
    seen = get_seen(spec)
    store, anchor_block = setup_store_with_anchor(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    yield get_filename(signed_anchor), signed_anchor

    parent_block = build_empty_block_for_next_slot(spec, state)
    signed_parent = state_transition_and_sign_block(spec, state, parent_block)
    yield "state", state

    yield get_filename(signed_parent), signed_parent

    # Add the parent block to store.blocks but not store.block_states, matching
    # the reference-test encoding of a failed block.
    store.blocks[signed_parent.message.hash_tree_root()] = signed_parent.message

    yield (
        "blocks",
        "meta",
        [
            {"block": get_filename(signed_anchor)},
            {"block": get_filename(signed_parent), "failed": True},
        ],
    )

    _, sidecars = build_signed_block_and_sidecars(spec, state.copy(), blob_count=1)
    blob_sidecar = sidecars[0]

    yield get_filename(blob_sidecar), blob_sidecar

    block_time_ms = spec.compute_time_at_slot_ms(
        state, blob_sidecar.signed_block_header.message.slot
    )
    yield "current_time_ms", "meta", int(block_time_ms)

    subnet_id = correct_subnet(spec, blob_sidecar)
    result, reason = run_validate_blob_sidecar_gossip(
        spec, seen, store, state, blob_sidecar, subnet_id, block_time_ms + 500
    )
    assert result == "reject"
    assert reason == "blob sidecar's parent failed validation"

    yield (
        "messages",
        "meta",
        [
            {
                "subnet_id": int(subnet_id),
                "offset_ms": 500,
                "message": get_filename(blob_sidecar),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_phases([DENEB])
@spec_state_test
def test_gossip_blob_sidecar__ignore_already_seen_tuple(spec, state):
    """
    Test that a duplicate blob sidecar for the same
    (slot, proposer_index, index) tuple is ignored.
    """
    yield "topic", "meta", "blob_sidecar"

    state = build_state_with_complete_transition(spec, state)
    yield "state", state

    messages = []
    seen = get_seen(spec)
    store, anchor_block = setup_store_with_anchor(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    _, sidecars = build_signed_block_and_sidecars(spec, state, blob_count=1)
    blob_sidecar = sidecars[0]

    yield get_filename(blob_sidecar), blob_sidecar

    block_time_ms = spec.compute_time_at_slot_ms(
        state, blob_sidecar.signed_block_header.message.slot
    )
    yield "current_time_ms", "meta", int(block_time_ms)

    subnet_id = correct_subnet(spec, blob_sidecar)

    # First delivery passes.
    result, reason = run_validate_blob_sidecar_gossip(
        spec, seen, store, state, blob_sidecar, subnet_id, block_time_ms + 500
    )
    assert result == "valid"
    messages.append(
        {
            "subnet_id": int(subnet_id),
            "offset_ms": 500,
            "message": get_filename(blob_sidecar),
            "expected": "valid",
        }
    )

    # Second delivery of the same sidecar is ignored.
    result, reason = run_validate_blob_sidecar_gossip(
        spec, seen, store, state, blob_sidecar, subnet_id, block_time_ms + 600
    )
    assert result == "ignore"
    assert reason == "already seen blob sidecar for this slot/proposer/index"
    messages.append(
        {
            "subnet_id": int(subnet_id),
            "offset_ms": 600,
            "message": get_filename(blob_sidecar),
            "expected": "ignore",
            "reason": reason,
        }
    )

    yield "messages", "meta", messages


@with_phases([DENEB])
@spec_state_test
def test_gossip_blob_sidecar__reject_slot_not_higher_than_parent(spec, state):
    """
    Test that a blob sidecar whose block_header.slot is not strictly greater
    than its parent's slot is rejected.
    """
    yield "topic", "meta", "blob_sidecar"

    state = build_state_with_complete_transition(spec, state)

    seen = get_seen(spec)
    store, anchor_block = setup_store_with_anchor(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    yield get_filename(signed_anchor), signed_anchor

    parent_block = build_empty_block_for_next_slot(spec, state)
    signed_parent = state_transition_and_sign_block(spec, state, parent_block)
    yield "state", state

    yield get_filename(signed_parent), signed_parent
    parent_root = signed_parent.message.hash_tree_root()
    store.blocks[parent_root] = signed_parent.message
    store.block_states[parent_root] = state.copy()
    yield (
        "blocks",
        "meta",
        [
            {"block": get_filename(signed_anchor)},
            {"block": get_filename(signed_parent)},
        ],
    )

    _, sidecars = build_signed_block_and_sidecars(spec, state.copy(), blob_count=1)
    blob_sidecar = sidecars[0]
    blob_sidecar.signed_block_header.message.slot = signed_parent.message.slot
    resign_blob_sidecar_header(spec, state, blob_sidecar)

    yield get_filename(blob_sidecar), blob_sidecar

    block_time_ms = spec.compute_time_at_slot_ms(
        state, blob_sidecar.signed_block_header.message.slot
    )
    yield "current_time_ms", "meta", int(block_time_ms)

    subnet_id = correct_subnet(spec, blob_sidecar)
    result, reason = run_validate_blob_sidecar_gossip(
        spec, seen, store, state, blob_sidecar, subnet_id, block_time_ms + 500
    )
    assert result == "reject"
    assert reason == "blob sidecar is not from a higher slot than its parent"

    yield (
        "messages",
        "meta",
        [
            {
                "subnet_id": int(subnet_id),
                "offset_ms": 500,
                "message": get_filename(blob_sidecar),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_phases([DENEB])
@spec_state_test
def test_gossip_blob_sidecar__reject_non_ancestor_finalized_checkpoint(spec, state):
    """Test that a blob sidecar is rejected if the finalized checkpoint is not an ancestor."""
    yield "topic", "meta", "blob_sidecar"

    state = build_state_with_complete_transition(spec, state)
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = setup_store_with_anchor(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    _, sidecars = build_signed_block_and_sidecars(spec, state, blob_count=1)
    blob_sidecar = sidecars[0]

    fake_finalized_root = spec.Root(b"\xab" * 32)
    store.finalized_checkpoint = spec.Checkpoint(
        epoch=spec.Epoch(0),
        root=fake_finalized_root,
    )

    yield "finalized_checkpoint", "meta", {"epoch": 0, "root": "0x" + "ab" * 32}
    yield get_filename(blob_sidecar), blob_sidecar

    block_time_ms = spec.compute_time_at_slot_ms(
        state, blob_sidecar.signed_block_header.message.slot
    )
    yield "current_time_ms", "meta", int(block_time_ms)

    subnet_id = correct_subnet(spec, blob_sidecar)
    result, reason = run_validate_blob_sidecar_gossip(
        spec, seen, store, state, blob_sidecar, subnet_id, block_time_ms + 500
    )
    assert result == "reject"
    assert reason == "finalized checkpoint is not an ancestor of blob sidecar's block"

    yield (
        "messages",
        "meta",
        [
            {
                "subnet_id": int(subnet_id),
                "offset_ms": 500,
                "message": get_filename(blob_sidecar),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )


@with_phases([DENEB])
@spec_state_test
def test_gossip_blob_sidecar__reject_wrong_proposer_index(spec, state):
    """Test that a blob sidecar with the wrong proposer_index is rejected."""
    yield "topic", "meta", "blob_sidecar"

    state = build_state_with_complete_transition(spec, state)
    yield "state", state

    seen = get_seen(spec)
    store, anchor_block = setup_store_with_anchor(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    yield get_filename(signed_anchor), signed_anchor
    yield "blocks", "meta", [{"block": get_filename(signed_anchor)}]

    _, sidecars = build_signed_block_and_sidecars(spec, state, blob_count=1)
    blob_sidecar = sidecars[0]

    correct_proposer = blob_sidecar.signed_block_header.message.proposer_index
    wrong_proposer = spec.ValidatorIndex((int(correct_proposer) + 1) % len(state.validators))
    blob_sidecar.signed_block_header.message.proposer_index = wrong_proposer
    resign_blob_sidecar_header(spec, state, blob_sidecar)

    yield get_filename(blob_sidecar), blob_sidecar

    block_time_ms = spec.compute_time_at_slot_ms(
        state, blob_sidecar.signed_block_header.message.slot
    )
    yield "current_time_ms", "meta", int(block_time_ms)

    subnet_id = correct_subnet(spec, blob_sidecar)
    result, reason = run_validate_blob_sidecar_gossip(
        spec, seen, store, state, blob_sidecar, subnet_id, block_time_ms + 500
    )
    assert result == "reject"
    assert reason == "blob sidecar proposer_index does not match expected proposer"

    yield (
        "messages",
        "meta",
        [
            {
                "subnet_id": int(subnet_id),
                "offset_ms": 500,
                "message": get_filename(blob_sidecar),
                "expected": "reject",
                "reason": reason,
            }
        ],
    )
