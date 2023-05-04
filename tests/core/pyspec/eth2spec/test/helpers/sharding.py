import random
import rlp

from eth2spec.utils.rlp import get_sample_signed_blob_tx


def get_sample_blob(spec, rng=None):
    if rng is None:
        rng = random.Random(5566)

    values = [
        rng.randint(0, spec.BLS_MODULUS - 1)
        for _ in range(spec.FIELD_ELEMENTS_PER_BLOB)
    ]

    b = bytes()
    for v in values:
        b += v.to_bytes(32, spec.ENDIANNESS)

    return spec.Blob(b)


def eval_poly_in_coeff_form(spec, coeffs, x):
    """
    Evaluate a polynomial in coefficient form at 'x' using Horner's rule
    """
    total = 0
    for a in reversed(coeffs):
        total = (total * x + a) % spec.BLS_MODULUS
    return total % spec.BLS_MODULUS


def get_poly_in_both_forms(spec, rng=None):
    """
    Generate and return a random polynomial in both coefficient form and evaluation form
    """
    if rng is None:
        rng = random.Random(5566)

    roots_of_unity_brp = spec.bit_reversal_permutation(spec.ROOTS_OF_UNITY)

    coeffs = [
        rng.randint(0, spec.BLS_MODULUS - 1)
        for _ in range(spec.FIELD_ELEMENTS_PER_BLOB)
    ]

    evals = [
        eval_poly_in_coeff_form(spec, coeffs, int(z))
        for z in roots_of_unity_brp
    ]

    return coeffs, evals


def get_sample_opaque_tx(spec, blob_count=1, rng=None):
    blobs = []
    blob_kzg_commitments = []
    blob_kzg_proofs = []
    blob_versioned_hashes = []
    for _ in range(blob_count):
        blob = get_sample_blob(spec, rng)
        blob_commitment = spec.KZGCommitment(spec.blob_to_kzg_commitment(blob))
        blob_kzg_proof = spec.compute_blob_kzg_proof(blob, blob_commitment)
        blob_versioned_hash = spec.kzg_commitment_to_versioned_hash(blob_commitment)
        blobs.append(blob)
        blob_kzg_commitments.append(blob_commitment)
        blob_kzg_proofs.append(blob_kzg_proof)
        blob_versioned_hashes.append(blob_versioned_hash)

    signed_blob_tx = get_sample_signed_blob_tx(blob_versioned_hashes=blob_versioned_hashes)
    serialized_tx = rlp.encode(signed_blob_tx)
    opaque_tx = spec.uint_to_bytes(spec.BLOB_TX_TYPE) + serialized_tx
    return opaque_tx, blobs, blob_kzg_commitments, blob_kzg_proofs
