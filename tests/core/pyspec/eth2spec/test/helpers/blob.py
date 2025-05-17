import random

from eth2spec.test.helpers.forks import (
    is_post_electra,
    is_post_fulu,
)
from rlp import Serializable, encode
from rlp.sedes import Binary, CountableList, List as RLPList, big_endian_int, binary


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


def get_sample_blob(spec, rng=random.Random(5566), is_valid_blob=True):
    values = [
        rng.randint(0, spec.BLS_MODULUS - 1) if is_valid_blob else spec.BLS_MODULUS
        for _ in range(spec.FIELD_ELEMENTS_PER_BLOB)
    ]

    b = bytes()
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


def get_sample_blob_tx(spec, blob_count=1, rng=random.Random(5566), is_valid_blob=True):
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
        return spec.get_max_blobs_per_block(spec.get_current_epoch(state))
    elif is_post_electra(spec):
        return spec.config.MAX_BLOBS_PER_BLOCK_ELECTRA
    else:
        return spec.config.MAX_BLOBS_PER_BLOCK
