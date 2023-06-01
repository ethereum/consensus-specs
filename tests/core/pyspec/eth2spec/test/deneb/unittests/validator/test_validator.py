from eth2spec.test.context import (
    always_bls,
    spec_state_test,
    with_deneb_and_later,
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
