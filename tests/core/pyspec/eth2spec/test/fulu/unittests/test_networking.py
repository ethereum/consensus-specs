import random

from eth2spec.debug.random_value import (
    RandomizationMode,
    get_random_ssz_object,
)
from eth2spec.test.context import (
    single_phase,
    spec_state_test,
    spec_test,
    with_fulu_and_later,
)
from eth2spec.test.helpers.blob import (
    get_sample_blob_tx,
)
from eth2spec.test.helpers.block import (
    sign_block,
)
from eth2spec.test.helpers.execution_payload import (
    compute_el_block_hash,
)

# Helper functions


def compute_data_column_sidecar(spec, state):
    rng = random.Random(5566)
    opaque_tx, blobs, blob_kzg_commitments, _ = get_sample_blob_tx(spec, blob_count=2)
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
    return spec.get_data_column_sidecars_from_block(signed_block, cells_and_kzg_proofs)[0]


# Tests for verify_data_column_sidecar


@with_fulu_and_later
@spec_state_test
@single_phase
def test_verify_data_column_sidecar__valid(spec, state):
    sidecar = compute_data_column_sidecar(spec, state)
    assert spec.verify_data_column_sidecar(sidecar)


@with_fulu_and_later
@spec_state_test
@single_phase
def test_verify_data_column_sidecar__invalid_zero_blobs(spec, state):
    sidecar = compute_data_column_sidecar(spec, state)
    sidecar.column = []
    sidecar.kzg_commitments = []
    sidecar.kzg_proofs = []
    assert not spec.verify_data_column_sidecar(sidecar)


@with_fulu_and_later
@spec_state_test
@single_phase
def test_verify_data_column_sidecar__invalid_index(spec, state):
    sidecar = compute_data_column_sidecar(spec, state)
    sidecar.index = 128
    assert not spec.verify_data_column_sidecar(sidecar)


@with_fulu_and_later
@spec_state_test
@single_phase
def test_verify_data_column_sidecar__invalid_mismatch_len_column(spec, state):
    sidecar = compute_data_column_sidecar(spec, state)
    sidecar.column = sidecar.column[1:]
    assert not spec.verify_data_column_sidecar(sidecar)


@with_fulu_and_later
@spec_state_test
@single_phase
def test_verify_data_column_sidecar__invalid_mismatch_len_kzg_commitments(spec, state):
    sidecar = compute_data_column_sidecar(spec, state)
    sidecar.kzg_commitments = sidecar.kzg_commitments[1:]
    assert not spec.verify_data_column_sidecar(sidecar)


@with_fulu_and_later
@spec_state_test
@single_phase
def test_verify_data_column_sidecars__invalid_mismatch_len_kzg_proofs(spec, state):
    sidecar = compute_data_column_sidecar(spec, state)
    sidecar.kzg_proofs = sidecar.kzg_proofs[1:]
    assert not spec.verify_data_column_sidecar(sidecar)


# Tests for verify_data_column_sidecar_kzg_proofs


@with_fulu_and_later
@spec_state_test
@single_phase
def test_verify_data_column_sidecar_kzg_proofs__valid(spec, state):
    sidecar = compute_data_column_sidecar(spec, state)
    assert spec.verify_data_column_sidecar_kzg_proofs(sidecar)


@with_fulu_and_later
@spec_state_test
@single_phase
def test_verify_data_column_sidecar_kzg_proofs__invalid_wrong_column(spec, state):
    sidecar = compute_data_column_sidecar(spec, state)
    sidecar.column[0] = sidecar.column[1]
    assert not spec.verify_data_column_sidecar_kzg_proofs(sidecar)


@with_fulu_and_later
@spec_state_test
@single_phase
def test_verify_data_column_sidecar_kzg_proofs__invalid_wrong_commitment(spec, state):
    sidecar = compute_data_column_sidecar(spec, state)
    sidecar.kzg_commitments[0] = sidecar.kzg_commitments[1]
    assert not spec.verify_data_column_sidecar_kzg_proofs(sidecar)


@with_fulu_and_later
@spec_state_test
@single_phase
def test_verify_data_column_sidecar_kzg_proofs__invalid_wrong_proof(spec, state):
    sidecar = compute_data_column_sidecar(spec, state)
    sidecar.kzg_proofs[0] = sidecar.kzg_proofs[1]
    assert not spec.verify_data_column_sidecar_kzg_proofs(sidecar)


# Tests for verify_data_column_sidecar_inclusion_proof


@with_fulu_and_later
@spec_state_test
@single_phase
def test_verify_data_column_sidecar_inclusion_proof__valid(spec, state):
    sidecar = compute_data_column_sidecar(spec, state)
    assert spec.verify_data_column_sidecar_inclusion_proof(sidecar)


@with_fulu_and_later
@spec_state_test
@single_phase
def test_verify_data_column_sidecar_inclusion_proof__invalid_missing_commitment(spec, state):
    sidecar = compute_data_column_sidecar(spec, state)
    sidecar.kzg_commitments = sidecar.kzg_commitments[1:]
    assert not spec.verify_data_column_sidecar_inclusion_proof(sidecar)


@with_fulu_and_later
@spec_state_test
@single_phase
def test_verify_data_column_sidecar_inclusion_proof__invalid_duplicate_commitment(spec, state):
    sidecar = compute_data_column_sidecar(spec, state)
    sidecar.kzg_commitments = sidecar.kzg_commitments + [sidecar.kzg_commitments[0]]
    assert not spec.verify_data_column_sidecar_inclusion_proof(sidecar)


# Tests for compute_subnet_for_data_column_sidecar


@with_fulu_and_later
@spec_test
@single_phase
def test_compute_subnet_for_data_column_sidecar(spec):
    subnet_results = []
    for column_index in range(spec.config.DATA_COLUMN_SIDECAR_SUBNET_COUNT):
        subnet_results.append(spec.compute_subnet_for_data_column_sidecar(column_index))
    # no duplicates
    assert len(subnet_results) == len(set(subnet_results))
    # next one should be duplicate
    next_subnet = spec.compute_subnet_for_data_column_sidecar(
        spec.config.DATA_COLUMN_SIDECAR_SUBNET_COUNT
    )
    assert next_subnet == subnet_results[0]
