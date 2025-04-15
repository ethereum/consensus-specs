import random
from eth2spec.test.context import (
    spec_state_test,
    with_deneb_and_later,
)
from eth2spec.test.helpers.execution_payload import (
    compute_el_block_hash,
)
from eth2spec.test.helpers.forks import is_post_eip7732
from eth2spec.test.helpers.blob import (
    get_sample_blob_tx,
)
from eth2spec.test.helpers.block import build_empty_block_for_next_slot, sign_block


def _get_sample_sidecars(spec, state, rng):
    block = build_empty_block_for_next_slot(spec, state)

    # 2 txs, each has 2 blobs
    blob_count = 2
    opaque_tx_1, blobs_1, blob_kzg_commitments_1, proofs_1 = get_sample_blob_tx(
        spec, blob_count=blob_count, rng=rng
    )
    opaque_tx_2, blobs_2, blob_kzg_commitments_2, proofs_2 = get_sample_blob_tx(
        spec, blob_count=blob_count, rng=rng
    )
    assert opaque_tx_1 != opaque_tx_2

    if is_post_eip7732(spec):
        blob_kzg_commitments = spec.List[spec.KZGCommitment, spec.MAX_BLOB_COMMITMENTS_PER_BLOCK](
            blob_kzg_commitments_1 + blob_kzg_commitments_2
        )
        kzg_root = blob_kzg_commitments.hash_tree_root()
        block.body.signed_execution_payload_header.message.blob_kzg_commitments_root = kzg_root
    else:
        block.body.blob_kzg_commitments = blob_kzg_commitments_1 + blob_kzg_commitments_2
        block.body.execution_payload.transactions = [opaque_tx_1, opaque_tx_2]
        block.body.execution_payload.block_hash = compute_el_block_hash(
            spec, block.body.execution_payload, state
        )

    blobs = blobs_1 + blobs_2
    proofs = proofs_1 + proofs_2
    signed_block = sign_block(spec, state, block, proposer_index=0)
    if is_post_eip7732(spec):
        return spec.get_blob_sidecars(signed_block, blobs, blob_kzg_commitments, proofs)
    return spec.get_blob_sidecars(signed_block, blobs, proofs)


@with_deneb_and_later
@spec_state_test
def test_blob_sidecar_inclusion_proof_correct(spec, state):
    rng = random.Random(1234)
    blob_sidecars = _get_sample_sidecars(spec, state, rng)

    for blob_sidecar in blob_sidecars:
        assert spec.verify_blob_sidecar_inclusion_proof(blob_sidecar)


@with_deneb_and_later
@spec_state_test
def test_blob_sidecar_inclusion_proof_incorrect_wrong_body(spec, state):
    rng = random.Random(1234)
    blob_sidecars = _get_sample_sidecars(spec, state, rng)

    for blob_sidecar in blob_sidecars:
        block = blob_sidecar.signed_block_header.message
        block.body_root = spec.hash(block.body_root)  # mutate body root to break proof
        assert not spec.verify_blob_sidecar_inclusion_proof(blob_sidecar)


@with_deneb_and_later
@spec_state_test
def test_blob_sidecar_inclusion_proof_incorrect_wrong_proof(spec, state):
    rng = random.Random(1234)
    blob_sidecars = _get_sample_sidecars(spec, state, rng)

    for blob_sidecar in blob_sidecars:
        # wrong proof
        blob_sidecar.kzg_commitment_inclusion_proof = spec.compute_merkle_proof(
            spec.BeaconBlockBody(), 0
        )
        assert not spec.verify_blob_sidecar_inclusion_proof(blob_sidecar)
