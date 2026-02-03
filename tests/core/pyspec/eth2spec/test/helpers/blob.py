import random
from functools import cache
from random import Random

from rlp import encode, Serializable
from rlp.sedes import big_endian_int, Binary, binary, CountableList, List as RLPList

from eth2spec.test.helpers.block import build_empty_block_for_next_slot
from eth2spec.test.helpers.execution_payload import compute_el_block_hash
from eth2spec.test.helpers.forks import (
    is_post_electra,
    is_post_fulu,
    is_post_gloas,
)
from eth2spec.test.helpers.keys import builder_privkeys
from eth2spec.test.helpers.state import state_transition_and_sign_block


class Eip4844RlpTransaction(Serializable):
    fields = (
        ("chain_id", big_endian_int),
        ("nonce", big_endian_int),
        ("max_priority_fee_per_gas", big_endian_int),
        ("max_fee_per_gas", big_endian_int),
        ("gas_limit", big_endian_int),
        ("to", Binary(20, 20)),
        ("value", big_endian_int),
        ("data", binary),
        (
            "access_list",
            CountableList(
                RLPList(
                    [
                        Binary(20, 20),
                        CountableList(Binary(32, 32)),
                    ]
                )
            ),
        ),
        ("max_fee_per_blob_gas", big_endian_int),
        ("blob_versioned_hashes", CountableList(Binary(32, 32))),
        ("signature_y_parity", big_endian_int),
        ("signature_r", big_endian_int),
        ("signature_s", big_endian_int),
    )


def get_sample_blob(spec, rng=None, is_valid_blob=True):
    if rng is None:
        rng = random.Random(5566)
    values = [
        rng.randint(0, spec.BLS_MODULUS - 1) if is_valid_blob else spec.BLS_MODULUS
        for _ in range(spec.FIELD_ELEMENTS_PER_BLOB)
    ]

    b = b""
    for v in values:
        b += v.to_bytes(32, spec.KZG_ENDIANNESS)

    return spec.Blob(b)


def eval_poly_in_coeff_form(spec, coeffs, x):
    """
    Evaluate a polynomial in coefficient form at 'x' using Horner's rule
    """
    total = spec.BLSFieldElement(0)
    for a in reversed(coeffs):
        total = total * x + a
    return total


def get_poly_in_both_forms(spec, rng=None):
    """
    Generate and return a random polynomial in both coefficient form and evaluation form
    """
    if rng is None:
        rng = random.Random(5566)

    roots_of_unity_brp = spec.bit_reversal_permutation(
        spec.compute_roots_of_unity(spec.FIELD_ELEMENTS_PER_BLOB)
    )
    coeffs = [
        spec.BLSFieldElement(rng.randint(0, spec.BLS_MODULUS - 1))
        for _ in range(spec.FIELD_ELEMENTS_PER_BLOB)
    ]
    evals = [eval_poly_in_coeff_form(spec, coeffs, z) for z in roots_of_unity_brp]

    return coeffs, evals


def get_sample_blob_tx(spec, blob_count=1, rng=None, is_valid_blob=True):
    if rng is None:
        rng = random.Random(5566)
    blobs = []
    blob_kzg_commitments = []
    blob_kzg_proofs = []
    blob_versioned_hashes = []
    for _ in range(blob_count):
        blob = get_sample_blob(spec, rng, is_valid_blob=is_valid_blob)
        if is_valid_blob:
            blob_commitment = spec.KZGCommitment(spec.blob_to_kzg_commitment(blob))
            blob_kzg_proof = spec.compute_blob_kzg_proof(blob, blob_commitment)
        else:
            blob_commitment = spec.KZGCommitment()
            blob_kzg_proof = spec.KZGProof()
        blob_versioned_hash = spec.kzg_commitment_to_versioned_hash(blob_commitment)
        blobs.append(blob)
        blob_kzg_commitments.append(blob_commitment)
        blob_kzg_proofs.append(blob_kzg_proof)
        blob_versioned_hashes.append(blob_versioned_hash)

    signed_blob_tx = Eip4844RlpTransaction(
        chain_id=0,
        nonce=0,
        max_priority_fee_per_gas=0,
        max_fee_per_gas=0,
        gas_limit=0,
        to=bytes.fromhex("0000000000000000000000000000000000000000"),
        value=0,
        data=bytes.fromhex(""),
        access_list=[],
        max_fee_per_blob_gas=0,
        blob_versioned_hashes=[bytes(h) for h in blob_versioned_hashes],
        signature_y_parity=0,
        signature_r=0,
        signature_s=0,
    )
    opaque_tx = bytes([0x03]) + encode(signed_blob_tx)
    return opaque_tx, blobs, blob_kzg_commitments, blob_kzg_proofs


def get_max_blob_count(spec, state):
    if is_post_fulu(spec):
        return spec.get_blob_parameters(spec.get_current_epoch(state)).max_blobs_per_block
    elif is_post_electra(spec):
        return spec.config.MAX_BLOBS_PER_BLOCK_ELECTRA
    else:
        return spec.config.MAX_BLOBS_PER_BLOCK


def get_block_with_blob(spec, state, rng: Random | None = None, blob_count=1):
    block = build_empty_block_for_next_slot(spec, state)
    opaque_tx, blobs, blob_kzg_commitments, blob_kzg_proofs = get_sample_blob_tx(
        spec, blob_count=blob_count, rng=rng or random.Random(5566)
    )
    if is_post_gloas(spec):
        block.body.signed_execution_payload_bid.message.blob_kzg_commitments = spec.List[
            spec.KZGCommitment, spec.MAX_BLOB_COMMITMENTS_PER_BLOCK
        ](blob_kzg_commitments)
        # For self-builds, use point at infinity signature as per spec
        if (
            block.body.signed_execution_payload_bid.message.builder_index
            == spec.BUILDER_INDEX_SELF_BUILD
        ):
            block.body.signed_execution_payload_bid.signature = spec.G2_POINT_AT_INFINITY
        else:
            block.body.signed_execution_payload_bid.signature = (
                spec.get_execution_payload_bid_signature(
                    state,
                    block.body.signed_execution_payload_bid.message,
                    builder_privkeys[block.body.signed_execution_payload_bid.message.builder_index],
                )
            )
    else:
        block.body.execution_payload.transactions = [opaque_tx]
        block.body.execution_payload.block_hash = compute_el_block_hash(
            spec, block.body.execution_payload, state
        )
        block.body.blob_kzg_commitments = blob_kzg_commitments
    return block, blobs, blob_kzg_commitments, blob_kzg_proofs


def get_block_with_blob_and_sidecars(spec, state, rng=None, blob_count=1):
    block, blobs, blob_kzg_commitments, blob_kzg_proofs = get_block_with_blob(
        spec, state, rng=rng, blob_count=blob_count
    )
    cells_and_kzg_proofs = [_cached_compute_cells_and_kzg_proofs(spec, blob) for blob in blobs]

    # We need a signed block to call `get_data_column_sidecars_from_block`
    signed_block = state_transition_and_sign_block(spec, state, block)

    if is_post_gloas(spec):
        sidecars = spec.get_data_column_sidecars_from_block(signed_block, cells_and_kzg_proofs)
    else:
        # For Fulu and earlier, use 2-parameter version
        sidecars = spec.get_data_column_sidecars_from_block(signed_block, cells_and_kzg_proofs)
    return block, blobs, blob_kzg_proofs, signed_block, sidecars, blob_kzg_commitments


@cache
def _cached_compute_cells_and_kzg_proofs(spec, blob):
    return spec.compute_cells_and_kzg_proofs(blob)
