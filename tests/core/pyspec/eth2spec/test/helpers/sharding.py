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
    priority_fee_per_gas: uint256
    max_basefee_per_gas: uint256
    gas: uint64
    to: Union[None, Bytes20]  # Address = Bytes20
    value: uint256
    data: ByteList[MAX_CALLDATA_SIZE]
    access_list: List[AccessTuple, MAX_ACCESS_LIST_SIZE]
    blob_versioned_hashes: List[Bytes32, MAX_VERSIONED_HASHES_LIST_SIZE]


class SignedBlobTransaction(Container):
    message: BlobTransaction
    signature: ECDSASignature


def get_sample_blob(spec, rng=None):
    if rng is None:
        rng = random.Random(5566)

    values = [
        rng.randint(0, spec.BLS_MODULUS - 1)
        for _ in range(spec.FIELD_ELEMENTS_PER_BLOB)
    ]

    b = bytes()
    for v in values:
        b.append(v.to_bytes(32, "little"))

    return spec.Blob(b)


def get_sample_opaque_tx(spec, blob_count=1, rng=None):
    blobs = []
    blob_kzg_commitments = []
    blob_versioned_hashes = []
    for _ in range(blob_count):
        blob = get_sample_blob(spec, rng)
        blob_commitment = spec.KZGCommitment(spec.blob_to_kzg_commitment(blob))
        blob_versioned_hash = spec.kzg_commitment_to_versioned_hash(blob_commitment)
        blobs.append(blob)
        blob_kzg_commitments.append(blob_commitment)
        blob_versioned_hashes.append(blob_versioned_hash)

    signed_blob_tx = SignedBlobTransaction(
        message=BlobTransaction(
            blob_versioned_hashes=blob_versioned_hashes,
        )
    )
    serialized_tx = serialize(signed_blob_tx)
    opaque_tx = spec.uint_to_bytes(spec.BLOB_TX_TYPE) + serialized_tx
    return opaque_tx, blobs, blob_kzg_commitments
