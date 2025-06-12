import random

from eth2spec.debug.random_value import (
    get_random_ssz_object,
    RandomizationMode,
)
from eth2spec.test.context import (
    spec_state_test,
    with_deneb_and_later,
    with_test_suite_name,
)
from eth2spec.test.helpers.blob import (
    get_sample_blob_tx,
)
from eth2spec.test.helpers.block import (
    build_empty_block_for_next_slot,
    sign_block,
)
from eth2spec.test.helpers.execution_payload import (
    compute_el_block_hash,
)
from eth2spec.test.helpers.forks import is_post_eip7732


def _run_blob_kzg_commitment_merkle_proof_test(spec, state, rng=None):
    opaque_tx, blobs, blob_kzg_commitments, proofs = get_sample_blob_tx(spec, blob_count=1)
    if rng is None:
        block = build_empty_block_for_next_slot(spec, state)
    else:
        block = get_random_ssz_object(
            rng,
            spec.BeaconBlock,
            max_bytes_length=2000,
            max_list_length=2000,
            mode=RandomizationMode,
            chaos=True,
        )
    if is_post_eip7732(spec):
        blob_kzg_commitments = spec.List[spec.KZGCommitment, spec.MAX_BLOB_COMMITMENTS_PER_BLOCK](
            blob_kzg_commitments
        )
        kzg_root = blob_kzg_commitments.hash_tree_root()
        block.body.signed_execution_payload_header.message.blob_kzg_commitments_root = kzg_root
    else:
        block.body.blob_kzg_commitments = blob_kzg_commitments
        block.body.execution_payload.transactions = [opaque_tx]
        block.body.execution_payload.block_hash = compute_el_block_hash(
            spec, block.body.execution_payload, state
        )

    signed_block = sign_block(spec, state, block, proposer_index=0)
    if is_post_eip7732(spec):
        blob_sidecars = spec.get_blob_sidecars(signed_block, blobs, blob_kzg_commitments, proofs)
    else:
        blob_sidecars = spec.get_blob_sidecars(signed_block, blobs, proofs)
    blob_index = 0
    blob_sidecar = blob_sidecars[blob_index]

    yield "object", block.body
    kzg_commitment_inclusion_proof = blob_sidecar.kzg_commitment_inclusion_proof

    if is_post_eip7732(spec):
        inner_gindex = spec.get_generalized_index(
            spec.List[spec.KZGCommitment, spec.MAX_BLOB_COMMITMENTS_PER_BLOCK], blob_index
        )
        outer_gindex = spec.get_generalized_index(
            spec.BeaconBlockBody,
            "signed_execution_payload_header",
            "message",
            "blob_kzg_commitments_root",
        )
        gindex = spec.concat_generalized_indices(outer_gindex, inner_gindex)
    else:
        gindex = spec.get_generalized_index(
            spec.BeaconBlockBody, "blob_kzg_commitments", blob_index
        )

    yield (
        "proof",
        {
            "leaf": "0x" + blob_sidecar.kzg_commitment.hash_tree_root().hex(),
            "leaf_index": gindex,
            "branch": ["0x" + root.hex() for root in kzg_commitment_inclusion_proof],
        },
    )

    assert spec.is_valid_merkle_branch(
        leaf=blob_sidecar.kzg_commitment.hash_tree_root(),
        branch=blob_sidecar.kzg_commitment_inclusion_proof,
        depth=spec.floorlog2(gindex),
        index=spec.get_subtree_index(gindex),
        root=blob_sidecar.signed_block_header.message.body_root,
    )


@with_test_suite_name("BeaconBlockBody")
@with_deneb_and_later
@spec_state_test
def test_blob_kzg_commitment_merkle_proof__basic(spec, state):
    yield from _run_blob_kzg_commitment_merkle_proof_test(spec, state)


@with_test_suite_name("BeaconBlockBody")
@with_deneb_and_later
@spec_state_test
def test_blob_kzg_commitment_merkle_proof__random_block_1(spec, state):
    rng = random.Random(1111)
    yield from _run_blob_kzg_commitment_merkle_proof_test(spec, state, rng=rng)


@with_test_suite_name("BeaconBlockBody")
@with_deneb_and_later
@spec_state_test
def test_blob_kzg_commitment_merkle_proof__random_block_2(spec, state):
    rng = random.Random(2222)
    yield from _run_blob_kzg_commitment_merkle_proof_test(spec, state, rng=rng)


@with_test_suite_name("BeaconBlockBody")
@with_deneb_and_later
@spec_state_test
def test_blob_kzg_commitment_merkle_proof__random_block_3(spec, state):
    rng = random.Random(3333)
    yield from _run_blob_kzg_commitment_merkle_proof_test(spec, state, rng=rng)
