import random
from eth2spec.utils.ssz.ssz_typing import (
    Container,
    Bytes20, Bytes32,
    ByteList,
    List,
    Union,
    boolean,
    uint256, uint64,
)
from eth2spec.utils.ssz.ssz_impl import serialize


#
# Containers from EIP-4844
#
MAX_CALLDATA_SIZE = 2**24
MAX_VERSIONED_HASHES_LIST_SIZE = 2**24
MAX_ACCESS_LIST_STORAGE_KEYS = 2**24
MAX_ACCESS_LIST_SIZE = 2**24


class AccessTuple(Container):
    address: Bytes20  # Address = Bytes20
    storage_keys: List[Bytes32, MAX_ACCESS_LIST_STORAGE_KEYS]


class ECDSASignature(Container):
    y_parity: boolean
    r: uint256
    s: uint256


class BlobTransaction(Container):
    chain_id: uint256
    nonce: uint64
    max_priority_fee_per_gas: uint256
    max_fee_per_gas: uint256
    gas: uint64
    to: Union[None, Bytes20]  # Address = Bytes20
    value: uint256
    data: ByteList[MAX_CALLDATA_SIZE]
    access_list: List[AccessTuple, MAX_ACCESS_LIST_SIZE]
    max_fee_per_blob_gas: uint256
    blob_versioned_hashes: List[Bytes32, MAX_VERSIONED_HASHES_LIST_SIZE]


class SignedBlobTransaction(Container):
    message: BlobTransaction
    signature: ECDSASignature


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

    roots_of_unity_brp = spec.bit_reversal_permutation(spec.compute_roots_of_unity(spec.FIELD_ELEMENTS_PER_BLOB))

    coeffs = [
        rng.randint(0, spec.BLS_MODULUS - 1)
        for _ in range(spec.FIELD_ELEMENTS_PER_BLOB)
    ]

    evals = [
        eval_poly_in_coeff_form(spec, coeffs, int(z))
        for z in roots_of_unity_brp
    ]

    return coeffs, evals


def get_sample_opaque_tx(spec, blob_count=1, rng=random.Random(5566), is_valid_blob=True):
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

    signed_blob_tx = SignedBlobTransaction(
        message=BlobTransaction(
            blob_versioned_hashes=blob_versioned_hashes,
        )
    )
    serialized_tx = serialize(signed_blob_tx)
    opaque_tx = spec.uint_to_bytes(spec.BLOB_TX_TYPE) + serialized_tx
    return opaque_tx, blobs, blob_kzg_commitments, blob_kzg_proofs
