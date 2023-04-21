from eth2spec.test.context import (
    always_bls,
    spec_state_test,
    with_deneb_and_later,
    expect_assertion_error,
)
from eth2spec.test.helpers.execution_payload import (
    compute_el_block_hash,
)
from eth2spec.test.helpers.sharding import (
    get_sample_opaque_tx,
)
from eth2spec.test.helpers.block import (
    build_empty_block_for_next_slot
)
from eth2spec.test.helpers.keys import (
    pubkey_to_privkey
)


@with_deneb_and_later
@spec_state_test
def test_validate_blobs_and_kzg_commitments(spec, state):
    """
    Test `validate_blobs_and_kzg_commitments`
    """
    blob_count = 4
    block = build_empty_block_for_next_slot(spec, state)
    opaque_tx, blobs, blob_kzg_commitments, proofs = get_sample_opaque_tx(spec, blob_count=blob_count)
    block.body.blob_kzg_commitments = blob_kzg_commitments
    block.body.execution_payload.transactions = [opaque_tx]
    block.body.execution_payload.block_hash = compute_el_block_hash(spec, block.body.execution_payload)

    spec.validate_blobs_and_kzg_commitments(block.body.execution_payload,
                                            blobs,
                                            blob_kzg_commitments,
                                            proofs)


@with_deneb_and_later
@spec_state_test
def test_validate_blobs_and_kzg_commitments_missing_blob(spec, state):
    """
    Test `validate_blobs_and_kzg_commitments`
    """
    blob_count = 4
    block = build_empty_block_for_next_slot(spec, state)
    opaque_tx, blobs, blob_kzg_commitments, proofs = get_sample_opaque_tx(spec, blob_count=blob_count)
    block.body.blob_kzg_commitments = blob_kzg_commitments
    block.body.execution_payload.transactions = [opaque_tx]
    block.body.execution_payload.block_hash = compute_el_block_hash(spec, block.body.execution_payload)

    expect_assertion_error(
        lambda: spec.validate_blobs_and_kzg_commitments(
            block.body.execution_payload,
            blobs[:-1],
            blob_kzg_commitments,
            proofs
        )
    )


@with_deneb_and_later
@spec_state_test
def test_validate_blobs_and_kzg_commitments_missing_proof(spec, state):
    """
    Test `validate_blobs_and_kzg_commitments`
    """
    blob_count = 4
    block = build_empty_block_for_next_slot(spec, state)
    opaque_tx, blobs, blob_kzg_commitments, proofs = get_sample_opaque_tx(spec, blob_count=blob_count)
    block.body.blob_kzg_commitments = blob_kzg_commitments
    block.body.execution_payload.transactions = [opaque_tx]
    block.body.execution_payload.block_hash = compute_el_block_hash(spec, block.body.execution_payload)

    expect_assertion_error(
        lambda: spec.validate_blobs_and_kzg_commitments(
            block.body.execution_payload,
            blobs,
            blob_kzg_commitments,
            proofs[:-1]
        )
    )


@with_deneb_and_later
@spec_state_test
def test_validate_blobs_and_kzg_commitments_incorrect_blob(spec, state):
    """
    Test `validate_blobs_and_kzg_commitments`
    """
    blob_count = 4
    block = build_empty_block_for_next_slot(spec, state)
    opaque_tx, blobs, blob_kzg_commitments, proofs = get_sample_opaque_tx(spec, blob_count=blob_count)
    block.body.blob_kzg_commitments = blob_kzg_commitments
    block.body.execution_payload.transactions = [opaque_tx]
    block.body.execution_payload.block_hash = compute_el_block_hash(spec, block.body.execution_payload)

    blobs[1] = spec.Blob(blobs[1][:13] + bytes([(blobs[1][13] + 1) % 256]) + blobs[1][14:])

    expect_assertion_error(
        lambda: spec.validate_blobs_and_kzg_commitments(
            block.body.execution_payload,
            blobs,
            blob_kzg_commitments,
            proofs
        )
    )


@with_deneb_and_later
@spec_state_test
def test_blob_sidecar_signature(spec, state):
    """
    Test `get_blob_sidecar_signature`
    """
    blob_count = 4
    block = build_empty_block_for_next_slot(spec, state)
    opaque_tx, blobs, blob_kzg_commitments, proofs = get_sample_opaque_tx(spec, blob_count=blob_count)
    block.body.blob_kzg_commitments = blob_kzg_commitments
    block.body.execution_payload.transactions = [opaque_tx]
    block.body.execution_payload.block_hash = compute_el_block_hash(spec, block.body.execution_payload)

    blob_sidecars = spec.get_blob_sidecars(block, blobs, proofs)
    proposer = state.validators[blob_sidecars[1].proposer_index]
    privkey = pubkey_to_privkey[proposer.pubkey]
    sidecar_signature = spec.get_blob_sidecar_signature(state,
                                                        blob_sidecars[1],
                                                        privkey)

    signed_blob_sidecar = spec.SignedBlobSidecar(message=blob_sidecars[1], signature=sidecar_signature)

    assert spec.verify_blob_sidecar_signature(state, signed_blob_sidecar)


@with_deneb_and_later
@spec_state_test
@always_bls
def test_blob_sidecar_signature_incorrect(spec, state):
    """
    Test `get_blob_sidecar_signature`
    """
    blob_count = 4
    block = build_empty_block_for_next_slot(spec, state)
    opaque_tx, blobs, blob_kzg_commitments, proofs = get_sample_opaque_tx(spec, blob_count=blob_count)
    block.body.blob_kzg_commitments = blob_kzg_commitments
    block.body.execution_payload.transactions = [opaque_tx]
    block.body.execution_payload.block_hash = compute_el_block_hash(spec, block.body.execution_payload)

    blob_sidecars = spec.get_blob_sidecars(block, blobs, proofs)

    sidecar_signature = spec.get_blob_sidecar_signature(state,
                                                        blob_sidecars[1],
                                                        123)

    signed_blob_sidecar = spec.SignedBlobSidecar(message=blob_sidecars[1], signature=sidecar_signature)

    assert not spec.verify_blob_sidecar_signature(state, signed_blob_sidecar)


@with_deneb_and_later
@spec_state_test
def test_slashed_validator_not_elected_for_proposal(spec, state):
    spec.process_slots(state, state.slot + 1)
    proposer_index = spec.get_beacon_proposer_index(state)
    state.validators[proposer_index].slashed = True

    assert spec.get_beacon_proposer_index(state) != proposer_index
