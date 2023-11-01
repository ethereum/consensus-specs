from eth2spec.test.context import (
    spec_state_test,
    with_deneb_and_later,
    with_test_suite_name,
)
from eth2spec.test.helpers.block import (
    build_empty_block_for_next_slot,
    sign_block
)
from eth2spec.test.helpers.execution_payload import (
    compute_el_block_hash,
)
from eth2spec.test.helpers.sharding import (
    get_sample_opaque_tx,
)


@with_test_suite_name("BeaconBlockBody")
@with_deneb_and_later
@spec_state_test
def test_blob_kzg_commitment_merkle_proof(spec, state):
    opaque_tx, blobs, blob_kzg_commitments, proofs = get_sample_opaque_tx(spec, blob_count=1)
    block = build_empty_block_for_next_slot(spec, state)
    block.body.blob_kzg_commitments = blob_kzg_commitments
    block.body.execution_payload.transactions = [opaque_tx]
    block.body.execution_payload.block_hash = compute_el_block_hash(spec, block.body.execution_payload)
    signed_block = sign_block(spec, state, block, proposer_index=0)
    blob_sidecars = spec.get_blob_sidecars(signed_block, blobs, proofs)
    blob_index = 0
    blob_sidecar = blob_sidecars[blob_index]

    yield "object", block.body
    kzg_commitment_inclusion_proof = blob_sidecar.kzg_commitment_inclusion_proof
    gindex = spec.get_generalized_index(spec.BeaconBlockBody, 'blob_kzg_commitments', blob_index)
    yield "proof", {
        "leaf": "0x" + blob_sidecar.kzg_commitment.hash_tree_root().hex(),
        "leaf_index": gindex,
        "branch": ['0x' + root.hex() for root in kzg_commitment_inclusion_proof]
    }
    assert spec.is_valid_merkle_branch(
        leaf=blob_sidecar.kzg_commitment.hash_tree_root(),
        branch=blob_sidecar.kzg_commitment_inclusion_proof,
        depth=spec.floorlog2(gindex),
        index=spec.get_subtree_index(gindex),
        root=blob_sidecar.signed_block_header.message.body_root,
    )
