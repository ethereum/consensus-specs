"""
KZG 4844 test vectors generator
"""

from hashlib import sha256
from typing import Tuple, Iterable, Any, Callable, Dict

from eth_utils import (
    encode_hex,
    int_to_big_endian,
)

from eth2spec.utils import bls
from eth2spec.test.helpers.constants import DENEB
from eth2spec.test.helpers.typing import SpecForkName
from eth2spec.gen_helpers.gen_base import gen_runner, gen_typing
from eth2spec.deneb import spec


def expect_exception(func, *args):
    try:
        func(*args)
    except Exception:
        pass
    else:
        raise Exception("should have raised exception")


def field_element_bytes(x):
    return int.to_bytes(x % spec.BLS_MODULUS, 32, spec.KZG_ENDIANNESS)


def field_element_bytes_unchecked(x):
    return int.to_bytes(x, 32, spec.KZG_ENDIANNESS)


def encode_hex_list(a):
    return [encode_hex(x) for x in a]


def bls_add_one(x):
    """
    Adds "one" (actually bls.G1()) to a compressed group element.
    Useful to compute definitely incorrect proofs.
    """
    return bls.G1_to_bytes48(
        bls.add(bls.bytes48_to_G1(x), bls.G1())
    )


def evaluate_blob_at(blob, z):
    return field_element_bytes(
        spec.evaluate_polynomial_in_evaluation_form(spec.blob_to_polynomial(blob), spec.bytes_to_bls_field(z))
    )


BLS_MODULUS_BYTES = spec.BLS_MODULUS.to_bytes(32, spec.KZG_ENDIANNESS)

G1 = bls.G1_to_bytes48(bls.G1())
G1_INVALID_TOO_FEW_BYTES = G1[:-1]
G1_INVALID_TOO_MANY_BYTES = G1 + b"\x00"
G1_INVALID_P1_NOT_IN_G1 = bytes.fromhex("8123456789abcdef0123456789abcdef0123456789abcdef" +
                                        "0123456789abcdef0123456789abcdef0123456789abcdef")
G1_INVALID_P1_NOT_ON_CURVE = bytes.fromhex("8123456789abcdef0123456789abcdef0123456789abcdef" +
                                           "0123456789abcdef0123456789abcdef0123456789abcde0")
INVALID_G1_POINTS = [G1_INVALID_TOO_FEW_BYTES, G1_INVALID_TOO_MANY_BYTES,
                     G1_INVALID_P1_NOT_IN_G1, G1_INVALID_P1_NOT_ON_CURVE]

BLOB_ALL_ZEROS = spec.Blob()
BLOB_ALL_TWOS = spec.Blob(b''.join([field_element_bytes(2) for n in range(4096)]))
BLOB_RANDOM_VALID1 = spec.Blob(b''.join([field_element_bytes(pow(2, n + 256, spec.BLS_MODULUS)) for n in range(4096)]))
BLOB_RANDOM_VALID2 = spec.Blob(b''.join([field_element_bytes(pow(3, n + 256, spec.BLS_MODULUS)) for n in range(4096)]))
BLOB_RANDOM_VALID3 = spec.Blob(b''.join([field_element_bytes(pow(5, n + 256, spec.BLS_MODULUS)) for n in range(4096)]))
BLOB_ALL_MODULUS_MINUS_ONE = spec.Blob(b''.join([field_element_bytes(spec.BLS_MODULUS - 1) for n in range(4096)]))
BLOB_ALMOST_ZERO = spec.Blob(b''.join([field_element_bytes(1 if n == 3211 else 0) for n in range(4096)]))
BLOB_INVALID = spec.Blob(b'\xFF' * 4096 * 32)
BLOB_INVALID_CLOSE = spec.Blob(b''.join(
    [BLS_MODULUS_BYTES if n == 2111 else field_element_bytes(0) for n in range(4096)]
))
BLOB_INVALID_LENGTH_PLUS_ONE = BLOB_RANDOM_VALID1 + b"\x00"
BLOB_INVALID_LENGTH_MINUS_ONE = BLOB_RANDOM_VALID1[:-1]

VALID_BLOBS = [BLOB_ALL_ZEROS, BLOB_ALL_TWOS, BLOB_RANDOM_VALID1, BLOB_RANDOM_VALID2,
               BLOB_RANDOM_VALID3, BLOB_ALL_MODULUS_MINUS_ONE, BLOB_ALMOST_ZERO]
INVALID_BLOBS = [BLOB_INVALID, BLOB_INVALID_CLOSE, BLOB_INVALID_LENGTH_PLUS_ONE, BLOB_INVALID_LENGTH_MINUS_ONE]

FE_VALID1 = field_element_bytes(0)
FE_VALID2 = field_element_bytes(1)
FE_VALID3 = field_element_bytes(2)
FE_VALID4 = field_element_bytes(pow(5, 1235, spec.BLS_MODULUS))
FE_VALID5 = field_element_bytes(spec.BLS_MODULUS - 1)
FE_VALID6 = field_element_bytes(spec.compute_roots_of_unity(spec.FIELD_ELEMENTS_PER_BLOB)[1])
VALID_FIELD_ELEMENTS = [FE_VALID1, FE_VALID2, FE_VALID3, FE_VALID4, FE_VALID5, FE_VALID6]

FE_INVALID_EQUAL_TO_MODULUS = field_element_bytes_unchecked(spec.BLS_MODULUS)
FE_INVALID_MODULUS_PLUS_ONE = field_element_bytes_unchecked(spec.BLS_MODULUS + 1)
FE_INVALID_UINT256_MAX = field_element_bytes_unchecked(2**256 - 1)
FE_INVALID_UINT256_MID = field_element_bytes_unchecked(2**256 - 2**128)
FE_INVALID_LENGTH_PLUS_ONE = VALID_FIELD_ELEMENTS[0] + b"\x00"
FE_INVALID_LENGTH_MINUS_ONE = VALID_FIELD_ELEMENTS[0][:-1]
INVALID_FIELD_ELEMENTS = [FE_INVALID_EQUAL_TO_MODULUS, FE_INVALID_MODULUS_PLUS_ONE,
                          FE_INVALID_UINT256_MAX, FE_INVALID_UINT256_MID,
                          FE_INVALID_LENGTH_PLUS_ONE, FE_INVALID_LENGTH_MINUS_ONE]


def hash(x):
    return sha256(x).digest()


def int_to_hex(n: int, byte_length: int = None) -> str:
    byte_value = int_to_big_endian(n)
    if byte_length:
        byte_value = byte_value.rjust(byte_length, b'\x00')
    return encode_hex(byte_value)


def case01_blob_to_kzg_commitment():
    # Valid cases
    for blob in VALID_BLOBS:
        commitment = spec.blob_to_kzg_commitment(blob)
        identifier = f'{encode_hex(hash(blob))}'
        yield f'blob_to_kzg_commitment_case_valid_blob_{(hash(bytes(identifier, "utf-8"))[:8]).hex()}', {
            'input': {
                'blob': encode_hex(blob),
            },
            'output': encode_hex(commitment)
        }

    # Edge case: Invalid blobs
    for blob in INVALID_BLOBS:
        identifier = f'{encode_hex(hash(blob))}'
        expect_exception(spec.blob_to_kzg_commitment, blob)
        yield f'blob_to_kzg_commitment_case_invalid_blob_{(hash(bytes(identifier, "utf-8"))[:8]).hex()}', {
            'input': {
                'blob': encode_hex(blob)
            },
            'output': None
        }


def case02_compute_kzg_proof():
    # Valid cases
    for blob in VALID_BLOBS:
        for z in VALID_FIELD_ELEMENTS:
            proof, y = spec.compute_kzg_proof(blob, z)
            identifier = f'{encode_hex(hash(blob))}_{encode_hex(z)}'
            yield f'compute_kzg_proof_case_valid_blob_{(hash(bytes(identifier, "utf-8"))[:8]).hex()}', {
                'input': {
                    'blob': encode_hex(blob),
                    'z': encode_hex(z),
                },
                'output': (encode_hex(proof), encode_hex(y))
            }

    # Edge case: Invalid blobs
    for blob in INVALID_BLOBS:
        z = VALID_FIELD_ELEMENTS[0]
        expect_exception(spec.compute_kzg_proof, blob, z)
        identifier = f'{encode_hex(hash(blob))}'
        yield f'compute_kzg_proof_case_invalid_blob_{(hash(bytes(identifier, "utf-8"))[:8]).hex()}', {
            'input': {
                'blob': encode_hex(blob),
                'z': encode_hex(z),
            },
            'output': None
        }

    # Edge case: Invalid z
    for z in INVALID_FIELD_ELEMENTS:
        blob = VALID_BLOBS[4]
        expect_exception(spec.compute_kzg_proof, blob, z)
        identifier = f'{encode_hex(hash(z))}'
        yield f'compute_kzg_proof_case_invalid_z_{(hash(bytes(identifier, "utf-8"))[:8]).hex()}', {
            'input': {
                'blob': encode_hex(blob),
                'z': encode_hex(z),
            },
            'output': None
        }


def case03_verify_kzg_proof():
    # Valid cases
    for blob in VALID_BLOBS:
        for z in VALID_FIELD_ELEMENTS:
            proof, y = spec.compute_kzg_proof(blob, z)
            commitment = spec.blob_to_kzg_commitment(blob)
            assert spec.verify_kzg_proof(commitment, z, y, proof)
            identifier = f'{encode_hex(hash(blob))}_{encode_hex(z)}'
            yield f'verify_kzg_proof_case_correct_proof_{(hash(bytes(identifier, "utf-8"))[:8]).hex()}', {
                'input': {
                    'commitment': encode_hex(commitment),
                    'z': encode_hex(z),
                    'y': encode_hex(y),
                    'proof': encode_hex(proof),
                },
                'output': True
            }

    # Incorrect proofs
    for blob in VALID_BLOBS:
        for z in VALID_FIELD_ELEMENTS:
            proof_orig, y = spec.compute_kzg_proof(blob, z)
            proof = bls_add_one(proof_orig)
            commitment = spec.blob_to_kzg_commitment(blob)
            assert not spec.verify_kzg_proof(commitment, z, y, proof)
            identifier = f'{encode_hex(hash(blob))}_{encode_hex(z)}'
            yield f'verify_kzg_proof_case_incorrect_proof_{(hash(bytes(identifier, "utf-8"))[:8]).hex()}', {
                'input': {
                    'commitment': encode_hex(commitment),
                    'z': encode_hex(z),
                    'y': encode_hex(y),
                    'proof': encode_hex(proof),
                },
                'output': False
            }

    # Incorrect `G1_POINT_AT_INFINITY` proof
    blob = BLOB_RANDOM_VALID1
    for z in VALID_FIELD_ELEMENTS:
        _, y = spec.compute_kzg_proof(blob, z)
        commitment = spec.blob_to_kzg_commitment(blob)
        proof = spec.G1_POINT_AT_INFINITY
        assert not spec.verify_kzg_proof(commitment, z, y, proof)
        prefix = 'verify_kzg_proof_case_incorrect_proof_point_at_infinity'
        identifier = f'{encode_hex(hash(blob))}_{encode_hex(z)}'
        yield f'{prefix}_{(hash(bytes(identifier, "utf-8"))[:8]).hex()}', {
            'input': {
                'commitment': encode_hex(commitment),
                'z': encode_hex(z),
                'y': encode_hex(y),
                'proof': encode_hex(proof),
            },
            'output': False
        }

    # Correct `G1_POINT_AT_INFINITY` proof for zero poly
    blob = BLOB_ALL_ZEROS
    for z in VALID_FIELD_ELEMENTS:
        _, y = spec.compute_kzg_proof(blob, z)
        commitment = spec.blob_to_kzg_commitment(blob)
        proof = spec.G1_POINT_AT_INFINITY
        assert spec.verify_kzg_proof(commitment, z, y, proof)
        prefix = 'verify_kzg_proof_case_correct_proof_point_at_infinity_for_zero_poly'
        identifier = f'{encode_hex(hash(blob))}_{encode_hex(z)}'
        yield f'{prefix}_{(hash(bytes(identifier, "utf-8"))[:8]).hex()}', {
            'input': {
                'commitment': encode_hex(commitment),
                'z': encode_hex(z),
                'y': encode_hex(y),
                'proof': encode_hex(proof),
            },
            'output': True
        }

    # Correct `G1_POINT_AT_INFINITY` proof for poly of all twos
    blob = BLOB_ALL_TWOS
    for z in VALID_FIELD_ELEMENTS:
        _, y = spec.compute_kzg_proof(blob, z)
        commitment = spec.blob_to_kzg_commitment(blob)
        proof = spec.G1_POINT_AT_INFINITY
        assert spec.verify_kzg_proof(commitment, z, y, proof)
        assert y == field_element_bytes(2)
        prefix = 'verify_kzg_proof_case_correct_proof_point_at_infinity_for_twos_poly'
        identifier = f'{encode_hex(hash(blob))}_{encode_hex(z)}'
        yield f'{prefix}_{(hash(bytes(identifier, "utf-8"))[:8]).hex()}', {
            'input': {
                'commitment': encode_hex(commitment),
                'z': encode_hex(z),
                'y': encode_hex(y),
                'proof': encode_hex(proof),
            },
            'output': True
        }

    # Edge case: Invalid commitment
    for commitment in INVALID_G1_POINTS:
        blob, z = VALID_BLOBS[2], VALID_FIELD_ELEMENTS[1]
        proof, y = spec.compute_kzg_proof(blob, z)
        expect_exception(spec.verify_kzg_proof, commitment, z, y, proof)
        identifier = f'{encode_hex(commitment)}'
        yield f'verify_kzg_proof_case_invalid_commitment_{(hash(bytes(identifier, "utf-8"))[:8]).hex()}', {
            'input': {
                'commitment': encode_hex(commitment),
                'z': encode_hex(z),
                'y': encode_hex(y),
                'proof': encode_hex(proof),
            },
            'output': None
        }

    # Edge case: Invalid z
    for z in INVALID_FIELD_ELEMENTS:
        blob, validz = VALID_BLOBS[4], VALID_FIELD_ELEMENTS[1]
        proof, y = spec.compute_kzg_proof(blob, validz)
        commitment = spec.blob_to_kzg_commitment(blob)
        expect_exception(spec.verify_kzg_proof, commitment, z, y, proof)
        identifier = f'{encode_hex(z)}'
        yield f'verify_kzg_proof_case_invalid_z_{(hash(bytes(identifier, "utf-8"))[:8]).hex()}', {
            'input': {
                'commitment': encode_hex(commitment),
                'z': encode_hex(z),
                'y': encode_hex(y),
                'proof': encode_hex(proof),
            },
            'output': None
        }

    # Edge case: Invalid y
    for y in INVALID_FIELD_ELEMENTS:
        blob, z = VALID_BLOBS[4], VALID_FIELD_ELEMENTS[1]
        proof, _ = spec.compute_kzg_proof(blob, z)
        commitment = spec.blob_to_kzg_commitment(blob)
        expect_exception(spec.verify_kzg_proof, commitment, z, y, proof)
        identifier = f'{encode_hex(y)}'
        yield f'verify_kzg_proof_case_invalid_y_{(hash(bytes(identifier, "utf-8"))[:8]).hex()}', {
            'input': {
                'commitment': encode_hex(commitment),
                'z': encode_hex(z),
                'y': encode_hex(y),
                'proof': encode_hex(proof),
            },
            'output': None
        }

    # Edge case: Invalid proof
    for proof in INVALID_G1_POINTS:
        blob, z = VALID_BLOBS[2], VALID_FIELD_ELEMENTS[1]
        _, y = spec.compute_kzg_proof(blob, z)
        commitment = spec.blob_to_kzg_commitment(blob)
        expect_exception(spec.verify_kzg_proof, commitment, z, y, proof)
        identifier = f'{encode_hex(proof)}'
        yield f'verify_kzg_proof_case_invalid_proof_{(hash(bytes(identifier, "utf-8"))[:8]).hex()}', {
            'input': {
                'commitment': encode_hex(commitment),
                'z': encode_hex(z),
                'y': encode_hex(y),
                'proof': encode_hex(proof),
            },
            'output': None
        }


def case04_compute_blob_kzg_proof():
    # Valid cases
    for blob in VALID_BLOBS:
        commitment = spec.blob_to_kzg_commitment(blob)
        proof = spec.compute_blob_kzg_proof(blob, commitment)
        identifier = f'{encode_hex(hash(blob))}'
        yield f'compute_blob_kzg_proof_case_valid_blob_{(hash(bytes(identifier, "utf-8"))[:8]).hex()}', {
            'input': {
                'blob': encode_hex(blob),
                'commitment': encode_hex(commitment),
            },
            'output': encode_hex(proof)
        }

    # Edge case: Invalid blob
    for blob in INVALID_BLOBS:
        commitment = G1
        expect_exception(spec.compute_blob_kzg_proof, blob, commitment)
        identifier = f'{encode_hex(hash(blob))}'
        yield f'compute_blob_kzg_proof_case_invalid_blob_{(hash(bytes(identifier, "utf-8"))[:8]).hex()}', {
            'input': {
                'blob': encode_hex(blob),
                'commitment': encode_hex(commitment),
            },
            'output': None
        }

    # Edge case: Invalid commitment
    for commitment in INVALID_G1_POINTS:
        blob = VALID_BLOBS[1]
        expect_exception(spec.compute_blob_kzg_proof, blob, commitment)
        identifier = f'{encode_hex(hash(commitment))}'
        yield f'compute_blob_kzg_proof_case_invalid_commitment_{(hash(bytes(identifier, "utf-8"))[:8]).hex()}', {
            'input': {
                'blob': encode_hex(blob),
                'commitment': encode_hex(commitment),
            },
            'output': None
        }


def case05_verify_blob_kzg_proof():
    # Valid cases
    for blob in VALID_BLOBS:
        commitment = spec.blob_to_kzg_commitment(blob)
        proof = spec.compute_blob_kzg_proof(blob, commitment)
        assert spec.verify_blob_kzg_proof(blob, commitment, proof)
        identifier = f'{encode_hex(hash(blob))}'
        yield f'verify_blob_kzg_proof_case_correct_proof_{(hash(bytes(identifier, "utf-8"))[:8]).hex()}', {
            'input': {
                'blob': encode_hex(blob),
                'commitment': encode_hex(commitment),
                'proof': encode_hex(proof),
            },
            'output': True
        }

    # Incorrect proofs
    for blob in VALID_BLOBS:
        commitment = spec.blob_to_kzg_commitment(blob)
        proof = bls_add_one(spec.compute_blob_kzg_proof(blob, commitment))
        assert not spec.verify_blob_kzg_proof(blob, commitment, proof)
        identifier = f'{encode_hex(hash(blob))}'
        yield f'verify_blob_kzg_proof_case_incorrect_proof_{(hash(bytes(identifier, "utf-8"))[:8]).hex()}', {
            'input': {
                'blob': encode_hex(blob),
                'commitment': encode_hex(commitment),
                'proof': encode_hex(proof),
            },
            'output': False
        }

    # Incorrect `G1_POINT_AT_INFINITY` proof
    blob = BLOB_RANDOM_VALID1
    commitment = spec.blob_to_kzg_commitment(blob)
    proof = spec.G1_POINT_AT_INFINITY
    assert not spec.verify_blob_kzg_proof(blob, commitment, proof)
    yield 'verify_blob_kzg_proof_case_incorrect_proof_point_at_infinity', {
        'input': {
            'blob': encode_hex(blob),
            'commitment': encode_hex(commitment),
            'proof': encode_hex(proof),
        },
        'output': False
    }

    # Correct `G1_POINT_AT_INFINITY` proof and commitment for zero poly
    blob = BLOB_ALL_ZEROS
    commitment = spec.blob_to_kzg_commitment(blob)
    proof = spec.G1_POINT_AT_INFINITY
    assert commitment == spec.G1_POINT_AT_INFINITY
    assert spec.verify_blob_kzg_proof(blob, commitment, proof)
    yield 'verify_blob_kzg_proof_case_correct_proof_point_at_infinity_for_zero_poly', {
        'input': {
            'blob': encode_hex(blob),
            'commitment': encode_hex(commitment),
            'proof': encode_hex(proof),
        },
        'output': True
    }

    # Correct `G1_POINT_AT_INFINITY` proof for all twos poly
    blob = BLOB_ALL_TWOS
    commitment = spec.blob_to_kzg_commitment(blob)
    proof = spec.G1_POINT_AT_INFINITY
    assert commitment != spec.G1_POINT_AT_INFINITY
    assert spec.verify_blob_kzg_proof(blob, commitment, proof)
    yield 'verify_blob_kzg_proof_case_correct_proof_point_at_infinity_for_twos_poly', {
        'input': {
            'blob': encode_hex(blob),
            'commitment': encode_hex(commitment),
            'proof': encode_hex(proof),
        },
        'output': True
    }

    # Edge case: Invalid blob
    for blob in INVALID_BLOBS:
        proof = G1
        commitment = G1
        expect_exception(spec.verify_blob_kzg_proof, blob, commitment, proof)
        identifier = f'{encode_hex(hash(blob))}'
        yield f'verify_blob_kzg_proof_case_invalid_blob_{(hash(bytes(identifier, "utf-8"))[:8]).hex()}', {
            'input': {
                'blob': encode_hex(blob),
                'commitment': encode_hex(commitment),
                'proof': encode_hex(proof),
            },
            'output': None
        }

    # Edge case: Invalid commitment
    for commitment in INVALID_G1_POINTS:
        blob = VALID_BLOBS[1]
        proof = G1
        expect_exception(spec.verify_blob_kzg_proof, blob, commitment, proof)
        identifier = f'{encode_hex(hash(commitment))}'
        yield f'verify_blob_kzg_proof_case_invalid_commitment_{(hash(bytes(identifier, "utf-8"))[:8]).hex()}', {
            'input': {
                'blob': encode_hex(blob),
                'commitment': encode_hex(commitment),
                'proof': encode_hex(proof),
            },
            'output': None
        }

    # Edge case: Invalid proof
    for proof in INVALID_G1_POINTS:
        blob = VALID_BLOBS[1]
        commitment = G1
        expect_exception(spec.verify_blob_kzg_proof, blob, commitment, proof)
        identifier = f'{encode_hex(hash(proof))}'
        yield f'verify_blob_kzg_proof_case_invalid_proof_{(hash(bytes(identifier, "utf-8"))[:8]).hex()}', {
            'input': {
                'blob': encode_hex(blob),
                'commitment': encode_hex(commitment),
                'proof': encode_hex(proof),
            },
            'output': None
        }


def case06_verify_blob_kzg_proof_batch():
    # Valid cases
    proofs = []
    commitments = []
    for blob in VALID_BLOBS:
        commitments.append(spec.blob_to_kzg_commitment(blob))
        proofs.append(spec.compute_blob_kzg_proof(blob, commitments[-1]))

    for i in range(len(proofs)):
        assert spec.verify_blob_kzg_proof_batch(VALID_BLOBS[:i], commitments[:i], proofs[:i])
        identifier = f'{encode_hex(hash(b"".join(VALID_BLOBS[:i])))}'
        yield f'verify_blob_kzg_proof_batch_case_{(hash(bytes(identifier, "utf-8"))[:8]).hex()}', {
            'input': {
                'blobs': encode_hex_list(VALID_BLOBS[:i]),
                'commitments': encode_hex_list(commitments[:i]),
                'proofs': encode_hex_list(proofs[:i]),
            },
            'output': True
        }

    # Incorrect proof
    proofs_incorrect = [bls_add_one(proofs[0])] + proofs[1:]
    assert not spec.verify_blob_kzg_proof_batch(VALID_BLOBS, commitments, proofs_incorrect)
    yield 'verify_blob_kzg_proof_batch_case_incorrect_proof_add_one', {
        'input': {
            'blobs': encode_hex_list(VALID_BLOBS),
            'commitments': encode_hex_list(commitments),
            'proofs': encode_hex_list(proofs_incorrect),
        },
        'output': False
    }

    # Incorrect `G1_POINT_AT_INFINITY` proof
    blob = BLOB_RANDOM_VALID1
    commitment = spec.blob_to_kzg_commitment(blob)
    proof = spec.G1_POINT_AT_INFINITY
    assert not spec.verify_blob_kzg_proof_batch([blob], [commitment], [proof])
    yield 'verify_blob_kzg_proof_batch_case_incorrect_proof_point_at_infinity', {
        'input': {
            'blobs': encode_hex_list([blob]),
            'commitments': encode_hex_list([commitment]),
            'proofs': encode_hex_list([proof]),
        },
        'output': False
    }

    # Edge case: Invalid blobs
    for blob in INVALID_BLOBS:
        blobs_invalid = VALID_BLOBS[:4] + [blob] + VALID_BLOBS[5:]
        expect_exception(spec.verify_blob_kzg_proof_batch, blobs_invalid, commitments, proofs)
        identifier = f'{encode_hex(hash(blob))}'
        yield f'verify_blob_kzg_proof_batch_case_invalid_blob_{(hash(bytes(identifier, "utf-8"))[:8]).hex()}', {
            'input': {
                'blobs': encode_hex_list(blobs_invalid),
                'commitments': encode_hex_list(commitments),
                'proofs': encode_hex_list(proofs),
            },
            'output': None
        }

    # Edge case: Invalid commitment
    for commitment in INVALID_G1_POINTS:
        blobs = VALID_BLOBS
        commitments_invalid = [commitment] + commitments[1:]
        expect_exception(spec.verify_blob_kzg_proof_batch, blobs, commitments_invalid, proofs)
        identifier = f'{encode_hex(hash(commitment))}'
        yield f'verify_blob_kzg_proof_batch_case_invalid_commitment_{(hash(bytes(identifier, "utf-8"))[:8]).hex()}', {
            'input': {
                'blobs': encode_hex_list(blobs),
                'commitments': encode_hex_list(commitments_invalid),
                'proofs': encode_hex_list(proofs),
            },
            'output': None
        }

    # Edge case: Invalid proof
    for proof in INVALID_G1_POINTS:
        blobs = VALID_BLOBS
        proofs_invalid = [proof] + proofs[1:]
        expect_exception(spec.verify_blob_kzg_proof_batch, blobs, commitments, proofs_invalid)
        identifier = f'{encode_hex(hash(proof))}'
        yield f'verify_blob_kzg_proof_batch_case_invalid_proof_{(hash(bytes(identifier, "utf-8"))[:8]).hex()}', {
            'input': {
                'blobs': encode_hex_list(blobs),
                'commitments': encode_hex_list(commitments),
                'proofs': encode_hex_list(proofs_invalid),
            },
            'output': None
        }

    # Edge case: Blob length different
    expect_exception(spec.verify_blob_kzg_proof_batch, VALID_BLOBS[:-1], commitments, proofs)
    yield 'verify_blob_kzg_proof_batch_case_blob_length_different', {
        'input': {
            'blobs': encode_hex_list(VALID_BLOBS[:-1]),
            'commitments': encode_hex_list(commitments),
            'proofs': encode_hex_list(proofs),
        },
        'output': None
    }

    # Edge case: Commitment length different
    expect_exception(spec.verify_blob_kzg_proof_batch, VALID_BLOBS, commitments[:-1], proofs)
    yield 'verify_blob_kzg_proof_batch_case_commitment_length_different', {
        'input': {
            'blobs': encode_hex_list(VALID_BLOBS),
            'commitments': encode_hex_list(commitments[:-1]),
            'proofs': encode_hex_list(proofs),
        },
        'output': None
    }

    # Edge case: Proof length different
    expect_exception(spec.verify_blob_kzg_proof_batch, VALID_BLOBS, commitments, proofs[:-1])
    yield 'verify_blob_kzg_proof_batch_case_proof_length_different', {
        'input': {
            'blobs': encode_hex_list(VALID_BLOBS),
            'commitments': encode_hex_list(commitments),
            'proofs': encode_hex_list(proofs[:-1]),
        },
        'output': None
    }


def create_provider(fork_name: SpecForkName,
                    handler_name: str,
                    test_case_fn: Callable[[], Iterable[Tuple[str, Dict[str, Any]]]]) -> gen_typing.TestProvider:

    def prepare_fn() -> None:
        # Nothing to load / change in spec. Maybe in future forks.
        # Put the tests into the general config category, to not require any particular configuration.
        return

    def cases_fn() -> Iterable[gen_typing.TestCase]:
        for data in test_case_fn():
            (case_name, case_content) = data
            yield gen_typing.TestCase(
                fork_name=fork_name,
                preset_name='general',
                runner_name='kzg',
                handler_name=handler_name,
                suite_name='kzg-mainnet',
                case_name=case_name,
                case_fn=lambda: [('data', 'data', case_content)]
            )

    return gen_typing.TestProvider(prepare=prepare_fn, make_cases=cases_fn)


if __name__ == "__main__":
    bls.use_arkworks()
    gen_runner.run_generator("kzg", [
        # DENEB
        create_provider(DENEB, 'blob_to_kzg_commitment', case01_blob_to_kzg_commitment),
        create_provider(DENEB, 'compute_kzg_proof', case02_compute_kzg_proof),
        create_provider(DENEB, 'verify_kzg_proof', case03_verify_kzg_proof),
        create_provider(DENEB, 'compute_blob_kzg_proof', case04_compute_blob_kzg_proof),
        create_provider(DENEB, 'verify_blob_kzg_proof', case05_verify_blob_kzg_proof),
        create_provider(DENEB, 'verify_blob_kzg_proof_batch', case06_verify_blob_kzg_proof_batch),
    ])
