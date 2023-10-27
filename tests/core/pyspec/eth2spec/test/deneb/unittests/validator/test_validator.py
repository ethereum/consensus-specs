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
    build_empty_block_for_next_slot,
    sign_block
)
from tests.core.pyspec.eth2spec.utils.ssz.ssz_impl import hash_tree_root


@with_deneb_and_later
@spec_state_test
def test_blob_sidecar_inclusion_proof_correct(spec, state):
    """
    Test `verify_blob_sidecar_inclusion_proof`
    """
    blob_count = 4
    block = build_empty_block_for_next_slot(spec, state)
    opaque_tx, blobs, blob_kzg_commitments, proofs = get_sample_opaque_tx(spec, blob_count=blob_count)
    block.body.blob_kzg_commitments = blob_kzg_commitments
    block.body.execution_payload.transactions = [opaque_tx]
    block.body.execution_payload.block_hash = compute_el_block_hash(spec, block.body.execution_payload)

    signed_block = sign_block(spec, state, block, proposer_index=0)
    blob_sidecars = spec.get_blob_sidecars(signed_block, blobs, proofs)

    for blob_sidecar in blob_sidecars:
        assert spec.verify_blob_sidecar_inclusion_proof(blob_sidecar)


@with_deneb_and_later
@spec_state_test
@always_bls
def test_blob_sidecar_inclusion_proof_incorrect(spec, state):
    """
    Test `get_blob_sidecar_signature`
    """
    blob_count = 4
    block = build_empty_block_for_next_slot(spec, state)
    opaque_tx, blobs, blob_kzg_commitments, proofs = get_sample_opaque_tx(spec, blob_count=blob_count)
    block.body.blob_kzg_commitments = blob_kzg_commitments
    block.body.execution_payload.transactions = [opaque_tx]
    block.body.execution_payload.block_hash = compute_el_block_hash(spec, block.body.execution_payload)

    signed_block = sign_block(spec, state, block, proposer_index=0)
    blob_sidecars = spec.get_blob_sidecars(signed_block, blobs, proofs)

    for blob_sidecar in blob_sidecars:
        block = blob_sidecar.signed_block_header.message
        block = block.body_root = hash_tree_root(block.body_root)  # mutate body root to break proof
        assert not spec.verify_blob_sidecar_inclusion_proof(blob_sidecar)
