import random

from eth2spec.test.context import (
    spec_state_test,
    with_fulu_and_later,
    with_test_suite_name,
)
from eth2spec.test.helpers.block import (
    build_empty_block_for_next_slot,
    sign_block,
)
from eth2spec.test.helpers.execution_payload import (
    compute_el_block_hash,
)
from eth2spec.test.helpers.blob import (
    get_sample_blob_tx,
)
from eth2spec.debug.random_value import (
    RandomizationMode,
    get_random_ssz_object,
)


def _run_blob_kzg_commitments_merkle_proof_test(spec, state, rng=None, blob_count=1):
    opaque_tx, blobs, blob_kzg_commitments, _ = get_sample_blob_tx(spec, blob_count=blob_count)
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
    cells_and_kzg_proofs = [spec.compute_cells_and_kzg_proofs(blob) for blob in blobs]
    column_sidcars = spec.get_data_column_sidecars_from_block(signed_block, cells_and_kzg_proofs)
    column_sidcar = column_sidcars[0]

    yield "object", block.body
    kzg_commitments_inclusion_proof = column_sidcar.kzg_commitments_inclusion_proof
    gindex = spec.get_generalized_index(spec.BeaconBlockBody, "blob_kzg_commitments")
    yield "proof", {
        "leaf": "0x" + column_sidcar.kzg_commitments.hash_tree_root().hex(),
        "leaf_index": gindex,
        "branch": ["0x" + root.hex() for root in kzg_commitments_inclusion_proof],
    }
    assert spec.is_valid_merkle_branch(
        leaf=column_sidcar.kzg_commitments.hash_tree_root(),
        branch=column_sidcar.kzg_commitments_inclusion_proof,
        depth=spec.floorlog2(gindex),
        index=spec.get_subtree_index(gindex),
        root=column_sidcar.signed_block_header.message.body_root,
    )
    assert spec.verify_data_column_sidecar_kzg_proofs(column_sidcar)
    assert spec.verify_data_column_sidecar_inclusion_proof(column_sidcar)


@with_test_suite_name("BeaconBlockBody")
@with_fulu_and_later
@spec_state_test
def test_blob_kzg_commitments_merkle_proof__basic(spec, state):
    yield from _run_blob_kzg_commitments_merkle_proof_test(spec, state)


@with_test_suite_name("BeaconBlockBody")
@with_fulu_and_later
@spec_state_test
def test_blob_kzg_commitments_merkle_proof__random_block_1(spec, state):
    rng = random.Random(1111)
    yield from _run_blob_kzg_commitments_merkle_proof_test(spec, state, rng=rng)


@with_test_suite_name("BeaconBlockBody")
@with_fulu_and_later
@spec_state_test
def test_blob_kzg_commitments_merkle_proof__multiple_blobs(spec, state):
    blob_count = 2
    rng = random.Random(2222)
    yield from _run_blob_kzg_commitments_merkle_proof_test(
        spec, state, rng=rng, blob_count=blob_count
    )


@with_test_suite_name("BeaconBlockBody")
@with_fulu_and_later
@spec_state_test
def test_blob_kzg_commitments_merkle_proof__max_blobs(spec, state):
    max_blobs = max(e["MAX_BLOBS_PER_BLOCK"] for e in spec.config.BLOB_SCHEDULE)
    rng = random.Random(3333)
    yield from _run_blob_kzg_commitments_merkle_proof_test(
        spec, state, rng=rng, blob_count=max_blobs
    )
