from hashlib import sha256

from eth_utils import (
    encode_hex,
    int_to_big_endian,
)

from eth2spec.utils import bls
from eth2spec.fulu import spec


###############################################################################
# Helper functions
###############################################################################


def expect_exception(func, *args):
    try:
        func(*args)
    except Exception:
        pass
    else:
        raise Exception("should have raised exception")


def bls_add_one(x):
    """
    Adds "one" (actually bls.G1()) to a compressed group element.
    Useful to compute definitely incorrect proofs.
    """
    return bls.G1_to_bytes48(bls.add(bls.bytes48_to_G1(x), bls.G1()))


def hash(x):
    return sha256(x).digest()


def make_id(*args):
    values_str = "_".join(str(arg) for arg in args)
    return hash(bytes(values_str, "utf-8"))[:8].hex()


def field_element_bytes(x: int):
    assert x < spec.BLS_MODULUS
    return int.to_bytes(x, 32, spec.KZG_ENDIANNESS)


def field_element_bytes_unchecked(x: int):
    return int.to_bytes(x, 32, spec.KZG_ENDIANNESS)


def encode_hex_list(a):
    return [encode_hex(x) for x in a]


def int_to_hex(n: int, byte_length: int = None) -> str:
    byte_value = int_to_big_endian(n)
    if byte_length:
        byte_value = byte_value.rjust(byte_length, b"\x00")
    return encode_hex(byte_value)


def evaluate_blob_at(blob, z):
    return field_element_bytes(
        int(
            spec.evaluate_polynomial_in_evaluation_form(
                spec.blob_to_polynomial(blob), spec.bytes_to_bls_field(z)
            )
        )
    )


###############################################################################
# Global variables
###############################################################################

BLS_MODULUS_BYTES = spec.BLS_MODULUS.to_bytes(32, spec.KZG_ENDIANNESS)

# Field Elements

FE_VALID1 = field_element_bytes(0)
FE_VALID2 = field_element_bytes(1)
FE_VALID3 = field_element_bytes(2)
FE_VALID4 = field_element_bytes(pow(5, 1235, spec.BLS_MODULUS))
FE_VALID5 = field_element_bytes(spec.BLS_MODULUS - 1)
FE_VALID6 = field_element_bytes(int(spec.compute_roots_of_unity(spec.FIELD_ELEMENTS_PER_BLOB)[1]))
VALID_FIELD_ELEMENTS = [FE_VALID1, FE_VALID2, FE_VALID3, FE_VALID4, FE_VALID5, FE_VALID6]

FE_INVALID_EQUAL_TO_MODULUS = field_element_bytes_unchecked(spec.BLS_MODULUS)
FE_INVALID_MODULUS_PLUS_ONE = field_element_bytes_unchecked(spec.BLS_MODULUS + 1)
FE_INVALID_UINT256_MAX = field_element_bytes_unchecked(2**256 - 1)
FE_INVALID_UINT256_MID = field_element_bytes_unchecked(2**256 - 2**128)
FE_INVALID_LENGTH_PLUS_ONE = VALID_FIELD_ELEMENTS[0] + b"\x00"
FE_INVALID_LENGTH_MINUS_ONE = VALID_FIELD_ELEMENTS[0][:-1]
INVALID_FIELD_ELEMENTS = [
    FE_INVALID_EQUAL_TO_MODULUS,
    FE_INVALID_MODULUS_PLUS_ONE,
    FE_INVALID_UINT256_MAX,
    FE_INVALID_UINT256_MID,
    FE_INVALID_LENGTH_PLUS_ONE,
    FE_INVALID_LENGTH_MINUS_ONE,
]

# Blobs

BLOB_ALL_ZEROS = spec.Blob()
BLOB_ALL_TWOS = spec.Blob(b"".join([field_element_bytes(2) for n in range(4096)]))
BLOB_RANDOM_VALID1 = spec.Blob(
    b"".join([field_element_bytes(pow(2, n + 256, spec.BLS_MODULUS)) for n in range(4096)])
)
BLOB_RANDOM_VALID2 = spec.Blob(
    b"".join([field_element_bytes(pow(3, n + 256, spec.BLS_MODULUS)) for n in range(4096)])
)
BLOB_RANDOM_VALID3 = spec.Blob(
    b"".join([field_element_bytes(pow(5, n + 256, spec.BLS_MODULUS)) for n in range(4096)])
)
BLOB_ALL_MODULUS_MINUS_ONE = spec.Blob(
    b"".join([field_element_bytes(spec.BLS_MODULUS - 1) for n in range(4096)])
)
BLOB_ALMOST_ZERO = spec.Blob(
    b"".join([field_element_bytes(1 if n == 3211 else 0) for n in range(4096)])
)

BLOB_INVALID = spec.Blob(b"\xff" * 4096 * 32)
BLOB_INVALID_CLOSE = spec.Blob(
    b"".join([BLS_MODULUS_BYTES if n == 2111 else field_element_bytes(0) for n in range(4096)])
)
BLOB_INVALID_LENGTH_PLUS_ONE = BLOB_RANDOM_VALID1 + b"\x00"
BLOB_INVALID_LENGTH_MINUS_ONE = BLOB_RANDOM_VALID1[:-1]

VALID_BLOBS = [
    BLOB_ALL_ZEROS,
    BLOB_ALL_TWOS,
    BLOB_RANDOM_VALID1,
    BLOB_RANDOM_VALID2,
    BLOB_RANDOM_VALID3,
    BLOB_ALL_MODULUS_MINUS_ONE,
    BLOB_ALMOST_ZERO,
]
INVALID_BLOBS = [
    BLOB_INVALID,
    BLOB_INVALID_CLOSE,
    BLOB_INVALID_LENGTH_PLUS_ONE,
    BLOB_INVALID_LENGTH_MINUS_ONE,
]

# Commitments

VALID_COMMITMENTS = [spec.blob_to_kzg_commitment(blob) for blob in VALID_BLOBS]

# Points

G1 = bls.G1_to_bytes48(bls.G1())
G1_INVALID_TOO_FEW_BYTES = G1[:-1]
G1_INVALID_TOO_MANY_BYTES = G1 + b"\x00"
G1_INVALID_P1_NOT_IN_G1 = bytes.fromhex(
    "8123456789abcdef0123456789abcdef0123456789abcdef"
    + "0123456789abcdef0123456789abcdef0123456789abcdef"
)
G1_INVALID_P1_NOT_ON_CURVE = bytes.fromhex(
    "8123456789abcdef0123456789abcdef0123456789abcdef"
    + "0123456789abcdef0123456789abcdef0123456789abcde0"
)
INVALID_G1_POINTS = [
    G1_INVALID_TOO_FEW_BYTES,
    G1_INVALID_TOO_MANY_BYTES,
    G1_INVALID_P1_NOT_IN_G1,
    G1_INVALID_P1_NOT_ON_CURVE,
]

# Individual Cells

CELL_RANDOM_VALID1 = b"".join(
    [
        field_element_bytes(pow(2, n + 256, spec.BLS_MODULUS))
        for n in range(spec.FIELD_ELEMENTS_PER_CELL)
    ]
)
CELL_RANDOM_VALID2 = b"".join(
    [
        field_element_bytes(pow(3, n + 256, spec.BLS_MODULUS))
        for n in range(spec.FIELD_ELEMENTS_PER_CELL)
    ]
)
CELL_RANDOM_VALID3 = b"".join(
    [
        field_element_bytes(pow(5, n + 256, spec.BLS_MODULUS))
        for n in range(spec.FIELD_ELEMENTS_PER_CELL)
    ]
)

CELL_ALL_MAX_VALUE = b"".join(
    [field_element_bytes_unchecked(2**256 - 1) for n in range(spec.FIELD_ELEMENTS_PER_CELL)]
)
CELL_ONE_INVALID_FIELD = b"".join(
    [
        field_element_bytes_unchecked(spec.BLS_MODULUS) if n == 7 else field_element_bytes(0)
        for n in range(spec.FIELD_ELEMENTS_PER_CELL)
    ]
)
CELL_INVALID_TOO_FEW_BYTES = CELL_RANDOM_VALID1[:-1]
CELL_INVALID_TOO_MANY_BYTES = CELL_RANDOM_VALID2 + b"\x00"

VALID_INDIVIDUAL_RANDOM_CELL_BYTES = [CELL_RANDOM_VALID1, CELL_RANDOM_VALID2, CELL_RANDOM_VALID3]
INVALID_INDIVIDUAL_CELL_BYTES = [
    CELL_ALL_MAX_VALUE,
    CELL_ONE_INVALID_FIELD,
    CELL_INVALID_TOO_FEW_BYTES,
    CELL_INVALID_TOO_MANY_BYTES,
]

# Cells & Proofs

VALID_CELLS_AND_PROOFS = []  # Saved in case02_compute_cells_and_kzg_proofs
