import random

from eth2spec.debug.random_value import (
    get_random_ssz_object,
    RandomizationMode,
)
from eth2spec.test.context import (
    spec_state_test,
    with_all_phases_from_to,
    with_test_suite_name,
)
from eth2spec.test.helpers.blob import (
    get_sample_blob_tx,
)
from eth2spec.test.helpers.block import (
    build_empty_block_for_next_slot,
    sign_block,
)
from eth2spec.test.helpers.constants import (
    DENEB,
    ELECTRA,
)
from eth2spec.test.helpers.execution_payload import (
    compute_el_block_hash,
)


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
    block.body.blob_kzg_commitments = blob_kzg_commitments
    block.body.execution_payload.transactions = [opaque_tx]
    block.body.execution_payload.block_hash = compute_el_block_hash(
        spec, block.body.execution_payload, state
    )
    signed_block = sign_block(spec, state, block, proposer_index=0)
    blob_sidecars = spec.get_blob_sidecars(signed_block, blobs, proofs)
    blob_index = 0
    blob_sidecar = blob_sidecars[blob_index]

    yield "object", block.body
    kzg_commitment_inclusion_proof = blob_sidecar.kzg_commitment_inclusion_proof
    gindex = spec.get_generalized_index(spec.BeaconBlockBody, "blob_kzg_commitments", blob_index)

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
@with_all_phases_from_to(DENEB, ELECTRA)
@spec_state_test
def test_blob_kzg_commitment_merkle_proof__basic(spec, state):
    yield from _run_blob_kzg_commitment_merkle_proof_test(spec, state)


@with_test_suite_name("BeaconBlockBody")
@with_all_phases_from_to(DENEB, ELECTRA)
@spec_state_test
def test_blob_kzg_commitment_merkle_proof__random_block_1(spec, state):
    rng = random.Random(1111)
    yield from _run_blob_kzg_commitment_merkle_proof_test(spec, state, rng=rng)


@with_test_suite_name("BeaconBlockBody")
@with_all_phases_from_to(DENEB, ELECTRA)
@spec_state_test
def test_blob_kzg_commitment_merkle_proof__random_block_2(spec, state):
    rng = random.Random(2222)
    yield from _run_blob_kzg_commitment_merkle_proof_test(spec, state, rng=rng)


@with_test_suite_name("BeaconBlockBody")
@with_all_phases_from_to(DENEB, ELECTRA)
@spec_state_test
def test_blob_kzg_commitment_merkle_proof__random_block_3(spec, state):
    rng = random.Random(3333)
    yield from _run_blob_kzg_commitment_merkle_proof_test(spec, state, rng=rng)
