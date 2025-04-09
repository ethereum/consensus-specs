from random import Random

from eth2spec.test.context import (
    spec_state_test,
    with_all_phases_from_to,
)

from eth2spec.test.helpers.constants import (
    DENEB,
    FULU,
    EIP7732,
)

from eth2spec.test.helpers.block import (
    build_empty_block_for_next_slot,
)
from eth2spec.test.helpers.execution_payload import (
    compute_el_block_hash,
    sign_execution_payload_envelope,
    build_empty_execution_payload,
)
from eth2spec.test.helpers.fork_choice import (
    BlobData,
    get_genesis_forkchoice_store_and_block,
    on_tick_and_append_step,
    tick_and_add_block_with_data,
)
from eth2spec.test.helpers.state import (
    state_transition_and_sign_block,
)
from eth2spec.test.helpers.blob import (
    get_sample_blob_tx,
)
from eth2spec.test.helpers.forks import is_post_eip7732


def get_block_with_blob(spec, state, rng=None):
    rng = rng or Random(1010)
    block = build_empty_block_for_next_slot(spec, state)

    blob_count = 1
    opaque_tx, blobs, blob_kzg_commitments, blob_kzg_proofs = get_sample_blob_tx(
        spec, blob_count, rng=rng
    )

    if is_post_eip7732(spec):
        # Handle EIP-7732 case
        payload = build_empty_execution_payload(spec, state)
        payload.transactions = [opaque_tx]
        payload.block_hash = compute_el_block_hash(spec, payload, state)

        # Set header block hash
        header = block.body.signed_execution_payload_header.message
        header.block_hash = payload.block_hash

        # Create blob kzg commitments list
        kzg_list = spec.List[spec.KZGCommitment, spec.MAX_BLOB_COMMITMENTS_PER_BLOCK](
            blob_kzg_commitments
        )

        # Set commitments root in header
        header.blob_kzg_commitments_root = kzg_list.hash_tree_root()

        # Prepare envelope
        envelope = spec.ExecutionPayloadEnvelope(
            payload=payload,
            execution_requests=spec.ExecutionRequests(),
            builder_index=header.builder_index,
            beacon_block_root=spec.Root(),  # Will be updated during signing
            blob_kzg_commitments=blob_kzg_commitments,
            payload_withheld=False,
            state_root=spec.Root(),  # Will be updated during signing
        )

        # Sign the envelope using our helper function
        signed_envelope = sign_execution_payload_envelope(
            spec, state, envelope, envelope.builder_index
        )

        # Store for later testing
        block.signed_execution_payload_envelope = signed_envelope
    else:
        # Pre EIP-7732 case
        block.body.execution_payload.transactions = [opaque_tx]
        block.body.execution_payload.block_hash = compute_el_block_hash(
            spec, block.body.execution_payload, state
        )
        block.body.blob_kzg_commitments = blob_kzg_commitments

    return block, blobs, blob_kzg_proofs


# TODO(jtraglia): Use with_all_phases_from_to_except after EIP7732 is based on Fulu.
# This applies to every other test in this file too.
@with_all_phases_from_to(DENEB, EIP7732)
@spec_state_test
def test_simple_blob_data(spec, state):
    rng = Random(1234)

    test_steps = []
    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    assert store.time == current_time

    # On receiving a block of `GENESIS_SLOT + 1` slot
    block, blobs, blob_kzg_proofs = get_block_with_blob(spec, state, rng=rng)
    signed_block = state_transition_and_sign_block(spec, state, block)
    blob_data = BlobData(blobs, blob_kzg_proofs)

    yield from tick_and_add_block_with_data(spec, store, signed_block, test_steps, blob_data)

    assert spec.get_head(store) == signed_block.message.hash_tree_root()

    # On receiving a block of next epoch
    block, blobs, blob_kzg_proofs = get_block_with_blob(spec, state, rng=rng)
    signed_block = state_transition_and_sign_block(spec, state, block)
    blob_data = BlobData(blobs, blob_kzg_proofs)

    yield from tick_and_add_block_with_data(spec, store, signed_block, test_steps, blob_data)

    assert spec.get_head(store) == signed_block.message.hash_tree_root()

    yield "steps", test_steps


@with_all_phases_from_to(DENEB, EIP7732)
@spec_state_test
def test_invalid_incorrect_proof(spec, state):
    rng = Random(1234)

    test_steps = []
    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    assert store.time == current_time

    # On receiving a block of `GENESIS_SLOT + 1` slot
    block, blobs, _ = get_block_with_blob(spec, state, rng=rng)
    signed_block = state_transition_and_sign_block(spec, state, block)
    # Insert incorrect proof
    blob_kzg_proofs = [b"\xc0" + b"\x00" * 47]
    blob_data = BlobData(blobs, blob_kzg_proofs)

    yield from tick_and_add_block_with_data(
        spec, store, signed_block, test_steps, blob_data, valid=False
    )

    assert spec.get_head(store) != signed_block.message.hash_tree_root()

    yield "steps", test_steps


@with_all_phases_from_to(DENEB, EIP7732)
@spec_state_test
def test_invalid_data_unavailable(spec, state):
    rng = Random(1234)

    test_steps = []
    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    assert store.time == current_time

    # On receiving a block of `GENESIS_SLOT + 1` slot
    block, _, _ = get_block_with_blob(spec, state, rng=rng)
    signed_block = state_transition_and_sign_block(spec, state, block)

    # data unavailable
    blob_data = BlobData([], [])

    yield from tick_and_add_block_with_data(
        spec, store, signed_block, test_steps, blob_data, valid=False
    )

    assert spec.get_head(store) != signed_block.message.hash_tree_root()

    yield "steps", test_steps


@with_all_phases_from_to(DENEB, EIP7732)
@spec_state_test
def test_invalid_wrong_proofs_length(spec, state):
    rng = Random(1234)

    test_steps = []
    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    assert store.time == current_time

    # On receiving a block of `GENESIS_SLOT + 1` slot
    block, blobs, _ = get_block_with_blob(spec, state, rng=rng)
    signed_block = state_transition_and_sign_block(spec, state, block)

    # unavailable proofs
    blob_data = BlobData(blobs, [])

    yield from tick_and_add_block_with_data(
        spec, store, signed_block, test_steps, blob_data, valid=False
    )

    assert spec.get_head(store) != signed_block.message.hash_tree_root()

    yield "steps", test_steps


@with_all_phases_from_to(DENEB, EIP7732)
@spec_state_test
def test_invalid_wrong_blobs_length(spec, state):
    rng = Random(1234)

    test_steps = []
    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    assert store.time == current_time

    # On receiving a block of `GENESIS_SLOT + 1` slot
    block, _, blob_kzg_proofs = get_block_with_blob(spec, state, rng=rng)
    signed_block = state_transition_and_sign_block(spec, state, block)

    # unavailable blobs
    blob_data = BlobData([], blob_kzg_proofs)

    yield from tick_and_add_block_with_data(
        spec, store, signed_block, test_steps, blob_data, valid=False
    )

    assert spec.get_head(store) != signed_block.message.hash_tree_root()

    yield "steps", test_steps
