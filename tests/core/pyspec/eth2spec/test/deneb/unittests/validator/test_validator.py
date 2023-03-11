import random

from eth2spec.test.context import (
    spec_state_test,
    with_deneb_and_later,
    expect_assertion_error
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
from eth2spec.test.helpers.state import (
    state_transition_and_sign_block,
)
from eth2spec.utils import bls
from eth2spec.utils.bls import BLS_MODULUS

G1 = bls.G1_to_bytes48(bls.G1())
P1_NOT_IN_G1 = bytes.fromhex("8123456789abcdef0123456789abcdef0123456789abcdef" +
                             "0123456789abcdef0123456789abcdef0123456789abcdef")
P1_NOT_ON_CURVE = bytes.fromhex("8123456789abcdef0123456789abcdef0123456789abcdef" +
                                "0123456789abcdef0123456789abcdef0123456789abcde0")


def bls_add_one(x):
    """
    Adds "one" (actually bls.G1()) to a compressed group element.
    Useful to compute definitely incorrect proofs.
    """
    return bls.G1_to_bytes48(
        bls.add(bls.bytes48_to_G1(x), bls.G1())
    )


def field_element_bytes(x):
    return int.to_bytes(x % BLS_MODULUS, 32, "little")


@with_deneb_and_later
@spec_state_test
def test_validate_blobs_and_kzg_commitments(spec, state):
    """
    Test `validate_blobs_and_kzg_commitments`
    """
    blob_count = 4
    block = build_empty_block_for_next_slot(spec, state)
    opaque_tx, blobs, blob_kzg_commitments = get_sample_opaque_tx(spec, blob_count=blob_count)
    block.body.blob_kzg_commitments = blob_kzg_commitments
    block.body.execution_payload.transactions = [opaque_tx]
    block.body.execution_payload.block_hash = compute_el_block_hash(spec, block.body.execution_payload)

    blob_sidecars = spec.get_blob_sidecars(block, blobs)
    blobs = [sidecar.blob for sidecar in blob_sidecars]
    proofs = [sidecar.kzg_proof for sidecar in blob_sidecars]

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
    opaque_tx, blobs, blob_kzg_commitments = get_sample_opaque_tx(spec, blob_count=blob_count)
    block.body.blob_kzg_commitments = blob_kzg_commitments
    block.body.execution_payload.transactions = [opaque_tx]
    block.body.execution_payload.block_hash = compute_el_block_hash(spec, block.body.execution_payload)
    # state_transition_and_sign_block(spec, state, block)

    blob_sidecars = spec.get_blob_sidecars(block, blobs)
    blobs = [sidecar.blob for sidecar in blob_sidecars][:-1]
    proofs = [sidecar.kzg_proof for sidecar in blob_sidecars]

    expect_assertion_error(lambda: 
        spec.validate_blobs_and_kzg_commitments(block.body.execution_payload,
                                                blobs,
                                                blob_kzg_commitments,
                                                proofs)
    )


@with_deneb_and_later
@spec_state_test
def test_validate_blobs_and_kzg_commitments_missing_proof(spec, state):
    """
    Test `validate_blobs_and_kzg_commitments`
    """
    blob_count = 4
    block = build_empty_block_for_next_slot(spec, state)
    opaque_tx, blobs, blob_kzg_commitments = get_sample_opaque_tx(spec, blob_count=blob_count)
    block.body.blob_kzg_commitments = blob_kzg_commitments
    block.body.execution_payload.transactions = [opaque_tx]
    block.body.execution_payload.block_hash = compute_el_block_hash(spec, block.body.execution_payload)
    # state_transition_and_sign_block(spec, state, block)

    blob_sidecars = spec.get_blob_sidecars(block, blobs)
    blobs = [sidecar.blob for sidecar in blob_sidecars]
    proofs = [sidecar.kzg_proof for sidecar in blob_sidecars][:-1]

    expect_assertion_error(lambda: 
        spec.validate_blobs_and_kzg_commitments(block.body.execution_payload,
                                                blobs,
                                                blob_kzg_commitments,
                                                proofs)
    )


@with_deneb_and_later
@spec_state_test
def test_validate_blobs_and_kzg_commitments_incorrect_blob(spec, state):
    """
    Test `validate_blobs_and_kzg_commitments`
    """
    blob_count = 4
    block = build_empty_block_for_next_slot(spec, state)
    opaque_tx, blobs, blob_kzg_commitments = get_sample_opaque_tx(spec, blob_count=blob_count)
    block.body.blob_kzg_commitments = blob_kzg_commitments
    block.body.execution_payload.transactions = [opaque_tx]
    block.body.execution_payload.block_hash = compute_el_block_hash(spec, block.body.execution_payload)
    # state_transition_and_sign_block(spec, state, block)

    blob_sidecars = spec.get_blob_sidecars(block, blobs)
    blobs = [sidecar.blob for sidecar in blob_sidecars]
    proofs = [sidecar.kzg_proof for sidecar in blob_sidecars]

    blobs[1] = spec.Blob(blobs[1][:13] + bytes([(blobs[1][13] + 1) % 256]) + blobs[1][14:])

    expect_assertion_error(lambda: 
        spec.validate_blobs_and_kzg_commitments(block.body.execution_payload,
                                                blobs,
                                                blob_kzg_commitments,
                                                proofs)
    )