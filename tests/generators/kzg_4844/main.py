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
    return int.to_bytes(x % spec.BLS_MODULUS, 32, "little")


def encode_hex_list(a):
    return [encode_hex(x) for x in a]


BLOB_ALL_ZEROS = spec.Blob()
BLOB_RANDOM_VALID1 = spec.Blob(b''.join([field_element_bytes(pow(2, n + 256, spec.BLS_MODULUS)) for n in range(4096)]))
BLOB_RANDOM_VALID2 = spec.Blob(b''.join([field_element_bytes(pow(3, n + 256, spec.BLS_MODULUS)) for n in range(4096)]))
BLOB_INVALID = spec.Blob(b'\xFF' * 4096 * 32)

VALID_BLOBS = [BLOB_ALL_ZEROS, BLOB_RANDOM_VALID1, BLOB_RANDOM_VALID2]
INVALID_BLOBS = [BLOB_INVALID]
VALID_ZS = [x.to_bytes(32, spec.ENDIANNESS) for x in [0, 1, 15, 2**150 - 1, spec.BLS_MODULUS - 1]]
INVALID_ZS = [x.to_bytes(32, spec.ENDIANNESS) for x in [spec.BLS_MODULUS, 2**256 - 1]]


def hash(x):
    return sha256(x).digest()


def int_to_hex(n: int, byte_length: int = None) -> str:
    byte_value = int_to_big_endian(n)
    if byte_length:
        byte_value = byte_value.rjust(byte_length, b'\x00')
    return encode_hex(byte_value)


def case01_compute_kzg_proof():
    # Valid cases
    for blob in VALID_BLOBS:
        for z in VALID_ZS:
            proof = spec.compute_kzg_proof(blob, z)
            identifier = f'{encode_hex(hash(blob))}_{encode_hex(z)}'
            yield f'compute_kzg_proof_case_{(hash(bytes(identifier, "utf-8"))[:8]).hex()}', {
                'input': {
                    'blob': encode_hex(blob),
                    'z': encode_hex(z),
                },
                'output': encode_hex(proof)
            }

    # Edge case: Invalid blob
    expect_exception(spec.compute_kzg_proof, BLOB_INVALID, VALID_ZS[0])
    yield 'compute_kzg_proof_case_invalid_blob', {
        'input': {
            'blob': encode_hex(BLOB_INVALID),
            'z': encode_hex(VALID_ZS[0]),
        },
        'output': None
    }

    # Edge case: Invalid z
    expect_exception(spec.compute_kzg_proof, BLOB_ALL_ZEROS, INVALID_ZS[0])
    yield 'compute_kzg_proof_case_invalid_z', {
        'input': {
            'blob': encode_hex(BLOB_ALL_ZEROS),
            'z': encode_hex(INVALID_ZS[0]),
        },
        'output': None
    }


def case02_blob_to_kzg_commitment():
    # Valid cases
    for blob in VALID_BLOBS:
        commitment = spec.blob_to_kzg_commitment(blob)
        identifier = f'{encode_hex(hash(blob))}'
        yield f'blob_to_kzg_commitment_case_{(hash(bytes(identifier, "utf-8"))[:8]).hex()}', {
            'input': {
                'blob': encode_hex(blob),
            },
            'output': encode_hex(commitment)
        }
    # Edge case: Invalid blob
    expect_exception(spec.blob_to_kzg_commitment, BLOB_INVALID)
    yield 'blob_to_kzg_commitment_case_invalid_blob', {
        'input': {
            'blob': encode_hex(BLOB_INVALID)
        },
        'output': None
    }


def case03_verify_kzg_proof():
    # Valid cases
    for blob in VALID_BLOBS:
        for z in VALID_ZS:
            proof = spec.compute_kzg_proof(blob, z)
            commitment = spec.blob_to_kzg_commitment(blob)
            y = (
                spec.evaluate_polynomial_in_evaluation_form(spec.blob_to_polynomial(blob), spec.bytes_to_bls_field(z))
            ).to_bytes(32, spec.ENDIANNESS)
            assert spec.verify_kzg_proof(commitment, z, y, proof)
            identifier = f'{encode_hex(hash(blob))}_{encode_hex(z)}_correct'
            yield f'verify_kzg_proof_case_{(hash(bytes(identifier, "utf-8"))[:8]).hex()}', {
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
        for z in VALID_ZS:
            proof = bls.G1_to_bytes48(
                bls.add(bls.bytes48_to_G1(spec.compute_kzg_proof(blob, z)), bls.G1())
            )
            commitment = spec.blob_to_kzg_commitment(blob)
            y = (
                spec.evaluate_polynomial_in_evaluation_form(spec.blob_to_polynomial(blob), spec.bytes_to_bls_field(z))
            ).to_bytes(32, spec.ENDIANNESS)
            assert not spec.verify_kzg_proof(commitment, z, y, proof)
            identifier = f'{encode_hex(hash(blob))}_{encode_hex(z)}_incorrect'
            yield f'verify_kzg_proof_case_{(hash(bytes(identifier, "utf-8"))[:8]).hex()}', {
                'input': {
                    'commitment': encode_hex(commitment),
                    'z': encode_hex(z),
                    'y': encode_hex(y),
                    'proof': encode_hex(proof),
                },
                'output': False
            }

    # Edge case: Invalid z
    blob, z = VALID_BLOBS[0], VALID_ZS[0]
    proof = spec.compute_kzg_proof(blob, z)
    commitment = spec.blob_to_kzg_commitment(blob)
    y = (
        spec.evaluate_polynomial_in_evaluation_form(spec.blob_to_polynomial(blob), spec.bytes_to_bls_field(z))
    ).to_bytes(32, spec.ENDIANNESS)
    z = INVALID_ZS[0]
    expect_exception(spec.verify_kzg_proof, commitment, z, y, proof)
    yield 'verify_kzg_proof_case_invalid_z', {
        'input': {
            'commitment': encode_hex(commitment),
            'z': encode_hex(z),
            'y': encode_hex(y),
            'proof': encode_hex(proof),
        },
        'output': None
    }

    # Edge case: Invalid y
    blob, z = VALID_BLOBS[1], VALID_ZS[1]
    proof = spec.compute_kzg_proof(blob, z)
    commitment = spec.blob_to_kzg_commitment(blob)
    y = INVALID_ZS[0]
    expect_exception(spec.verify_kzg_proof, commitment, z, y, proof)
    yield 'verify_kzg_proof_case_invalid_y', {
        'input': {
            'commitment': encode_hex(commitment),
            'z': encode_hex(z),
            'y': encode_hex(y),
            'proof': encode_hex(proof),
        },
        'output': None
    }

    # Edge case: Invalid proof, not in G1
    blob, z = VALID_BLOBS[2], VALID_ZS[0]
    proof = bytes.fromhex("8123456789abcdef0123456789abcdef0123456789abcdef" +
                          "0123456789abcdef0123456789abcdef0123456789abcdef")
    commitment = spec.blob_to_kzg_commitment(blob)
    y = VALID_ZS[1]
    expect_exception(spec.verify_kzg_proof, commitment, z, y, proof)
    yield 'verify_kzg_proof_case_proof_not_in_G1', {
        'input': {
            'commitment': encode_hex(commitment),
            'z': encode_hex(z),
            'y': encode_hex(y),
            'proof': encode_hex(proof),
        },
        'output': None
    }

    # Edge case: Invalid proof, not on curve
    blob, z = VALID_BLOBS[2], VALID_ZS[2]
    proof = bytes.fromhex("8123456789abcdef0123456789abcdef0123456789abcdef" +
                          "0123456789abcdef0123456789abcdef0123456789abcde0")
    commitment = spec.blob_to_kzg_commitment(blob)
    y = VALID_ZS[1]
    expect_exception(spec.verify_kzg_proof, commitment, z, y, proof)
    yield 'verify_kzg_proof_case_proof_not_on_curve', {
        'input': {
            'commitment': encode_hex(commitment),
            'z': encode_hex(z),
            'y': encode_hex(y),
            'proof': encode_hex(proof),
        },
        'output': None
    }

    # Edge case: Invalid commitment, not in G1
    blob, z = VALID_BLOBS[2], VALID_ZS[2]
    proof = spec.compute_kzg_proof(blob, z)
    commitment = bytes.fromhex("8123456789abcdef0123456789abcdef0123456789abcdef" +
                               "0123456789abcdef0123456789abcdef0123456789abcdef")
    y = VALID_ZS[1]
    expect_exception(spec.verify_kzg_proof, commitment, z, y, proof)
    yield 'verify_kzg_proof_case_commitment_not_in_G1', {
        'input': {
            'commitment': encode_hex(commitment),
            'z': encode_hex(z),
            'y': encode_hex(y),
            'proof': encode_hex(proof),
        },
        'output': None
    }

    # Edge case: Invalid commitment, not on curve
    blob, z = VALID_BLOBS[2], VALID_ZS[2]
    proof = spec.compute_kzg_proof(blob, z)
    commitment = bytes.fromhex("8123456789abcdef0123456789abcdef0123456789abcdef" +
                               "0123456789abcdef0123456789abcdef0123456789abcde0")
    y = VALID_ZS[1]
    expect_exception(spec.verify_kzg_proof, commitment, z, y, proof)
    yield 'verify_kzg_proof_case_commitment_not_on_curve', {
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
        proof = spec.compute_blob_kzg_proof(blob)
        identifier = f'{encode_hex(hash(blob))}'
        yield f'compute_blob_kzg_proof_case_{(hash(bytes(identifier, "utf-8"))[:8]).hex()}', {
            'input': {
                'blob': encode_hex(blob),
                'proof': encode_hex(proof),
            },
            'output': True
        }

    # Edge case: Invalid blob
    blob = BLOB_INVALID
    expect_exception(spec.compute_blob_kzg_proof, blob)
    yield 'compute_blob_kzg_proof_case_invalid_blob', {
        'input': {
            'blob': encode_hex(blob),
        },
        'output': None
    }


def case05_verify_blob_kzg_proof():
    # Valid cases
    for blob in VALID_BLOBS:
        proof = spec.compute_blob_kzg_proof(blob)
        commitment = spec.blob_to_kzg_commitment(blob)
        assert spec.verify_blob_kzg_proof(blob, commitment, proof)
        identifier = f'{encode_hex(hash(blob))}_correct'
        yield f'verify_blob_kzg_proof_case_{(hash(bytes(identifier, "utf-8"))[:8]).hex()}', {
            'input': {
                'blob': encode_hex(blob),
                'commitment': encode_hex(commitment),
                'proof': encode_hex(proof),
            },
            'output': True
        }

    # Incorrect proofs
    for blob in VALID_BLOBS:
        proof = bls.G1_to_bytes48(
            bls.add(bls.bytes48_to_G1(spec.compute_blob_kzg_proof(blob)), bls.G1())
        )
        commitment = spec.blob_to_kzg_commitment(blob)
        assert not spec.verify_blob_kzg_proof(blob, commitment, proof)
        identifier = f'{encode_hex(hash(blob))}_incorrect'
        yield f'verify_blob_kzg_proof_case_{(hash(bytes(identifier, "utf-8"))[:8]).hex()}', {
            'input': {
                'blob': encode_hex(blob),
                'commitment': encode_hex(commitment),
                'proof': encode_hex(proof),
            },
            'output': False
        }

    # Edge case: Invalid proof, not in G1
    blob = VALID_BLOBS[2]
    proof = bytes.fromhex("8123456789abcdef0123456789abcdef0123456789abcdef" +
                          "0123456789abcdef0123456789abcdef0123456789abcdef")
    commitment = bls.G1_to_bytes48(bls.G1())
    expect_exception(spec.verify_blob_kzg_proof, blob, commitment, proof)
    yield 'verify_blob_kzg_proof_case_proof_not_in_G1', {
        'input': {
            'blob': encode_hex(blob),
            'commitment': encode_hex(commitment),
            'proof': encode_hex(proof),
        },
        'output': None
    }

    # Edge case: Invalid proof, not on curve
    blob = VALID_BLOBS[1]
    proof = bytes.fromhex("8123456789abcdef0123456789abcdef0123456789abcdef" +
                          "0123456789abcdef0123456789abcdef0123456789abcde0")
    commitment = bls.G1_to_bytes48(bls.G1())
    expect_exception(spec.verify_blob_kzg_proof, blob, commitment, proof)
    yield 'verify_blob_kzg_proof_case_proof_not_on_curve', {
        'input': {
            'blob': encode_hex(blob),
            'commitment': encode_hex(commitment),
            'proof': encode_hex(proof),
        },
        'output': None
    }

    # Edge case: Invalid commitment, not in G1
    blob = VALID_BLOBS[0]
    proof = bls.G1_to_bytes48(bls.G1())
    commitment = bytes.fromhex("8123456789abcdef0123456789abcdef0123456789abcdef" +
                               "0123456789abcdef0123456789abcdef0123456789abcdef")
    expect_exception(spec.verify_blob_kzg_proof, blob, commitment, proof)
    yield 'verify_blob_kzg_proof_case_commitment_not_in_G1', {
        'input': {
            'blob': encode_hex(blob),
            'commitment': encode_hex(commitment),
            'proof': encode_hex(proof),
        },
        'output': None
    }

    # Edge case: Invalid commitment, not on curve
    blob = VALID_BLOBS[2]
    proof = bls.G1_to_bytes48(bls.G1())
    commitment = bytes.fromhex("8123456789abcdef0123456789abcdef0123456789abcdef" +
                               "0123456789abcdef0123456789abcdef0123456789abcde0")
    expect_exception(spec.verify_blob_kzg_proof, blob, commitment, proof)
    yield 'verify_blob_kzg_proof_case_commitment_not_on_curve', {
        'input': {
            'blob': encode_hex(blob),
            'commitment': encode_hex(commitment),
            'proof': encode_hex(proof),
        },
        'output': None
    }

    # Edge case: Invalid blob
    blob = BLOB_INVALID
    proof = bls.G1_to_bytes48(bls.G1())
    commitment = bls.G1_to_bytes48(bls.G1())
    expect_exception(spec.verify_blob_kzg_proof, blob, commitment, proof)
    yield 'verify_blob_kzg_proof_case_invalid_blob', {
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
        proofs.append(spec.compute_blob_kzg_proof(blob))
        commitments.append(spec.blob_to_kzg_commitment(blob))

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
    proof_incorrect = bls.G1_to_bytes48(
        bls.add(bls.bytes48_to_G1(proofs[0]), bls.G1())
    )
    proofs_incorrect = [proof_incorrect] + proofs[1:]
    assert not spec.verify_blob_kzg_proof_batch(VALID_BLOBS, commitments, proofs_incorrect)
    yield 'verify_blob_kzg_proof_batch_case_invalid_proof', {
        'input': {
            'blobs': encode_hex_list(VALID_BLOBS),
            'commitments': encode_hex_list(commitments),
            'proofs': encode_hex_list(proofs_incorrect),
        },
        'output': False
    }

    # Edge case: Invalid proof, not in G1
    proof_invalid_notG1 = bytes.fromhex("8123456789abcdef0123456789abcdef0123456789abcdef" +
                                        "0123456789abcdef0123456789abcdef0123456789abcdef")
    proofs_invalid_notG1 = [proof_invalid_notG1] + proofs[1:]
    expect_exception(spec.verify_blob_kzg_proof_batch, VALID_BLOBS, commitments, proofs_invalid_notG1)
    yield 'verify_blob_kzg_proof_batch_case_proof_not_in_G1', {
        'input': {
            'blob': encode_hex_list(VALID_BLOBS),
            'commitment': encode_hex_list(commitments),
            'proof': encode_hex_list(proofs_invalid_notG1),
        },
        'output': None
    }

    # Edge case: Invalid proof, not on curve
    proof_invalid_notCurve = bytes.fromhex("8123456789abcdef0123456789abcdef0123456789abcdef" +
                                           "0123456789abcdef0123456789abcdef0123456789abcde0")
    proofs_invalid_notCurve = proofs[:1] + [proof_invalid_notCurve] + proofs[2:]
    expect_exception(spec.verify_blob_kzg_proof_batch, VALID_BLOBS, commitments, proofs_invalid_notCurve)
    yield 'verify_blob_kzg_proof_batch_case_proof_not_on_curve', {
        'input': {
            'blob': encode_hex_list(VALID_BLOBS),
            'commitment': encode_hex_list(commitments),
            'proof': encode_hex_list(proofs_invalid_notCurve),
        },
        'output': None
    }

    # Edge case: Invalid commitment, not in G1
    commitment_invalid_notG1 = bytes.fromhex("8123456789abcdef0123456789abcdef0123456789abcdef" +
                                             "0123456789abcdef0123456789abcdef0123456789abcdef")
    commitments_invalid_notG1 = commitments[:2] + [commitment_invalid_notG1] + commitments[3:]
    expect_exception(spec.verify_blob_kzg_proof_batch, VALID_BLOBS, commitments, commitments_invalid_notG1)
    yield 'verify_blob_kzg_proof_batch_case_commitment_not_in_G1', {
        'input': {
            'blob': encode_hex_list(VALID_BLOBS),
            'commitment': encode_hex_list(commitments_invalid_notG1),
            'proof': encode_hex_list(proofs),
        },
        'output': None
    }

    # Edge case: Invalid commitment, not on curve
    commitment_invalid_notCurve = bytes.fromhex("8123456789abcdef0123456789abcdef0123456789abcdef" +
                                                "0123456789abcdef0123456789abcdef0123456789abcde0")
    commitments_invalid_notCurve = commitments[:3] + [commitment_invalid_notCurve] + commitments[4:]
    expect_exception(spec.verify_blob_kzg_proof_batch, VALID_BLOBS, commitments, commitments_invalid_notCurve)
    yield 'verify_blob_kzg_proof_batch_case_not_on_curve', {
        'input': {
            'blob': encode_hex_list(VALID_BLOBS),
            'commitment': encode_hex_list(commitments_invalid_notCurve),
            'proof': encode_hex_list(proofs),
        },
        'output': None
    }

    # Edge case: Invalid blob
    blobs_invalid = VALID_BLOBS[:4] + [BLOB_INVALID] + VALID_BLOBS[5:]
    expect_exception(spec.verify_blob_kzg_proof_batch, blobs_invalid, commitments, proofs)
    yield 'verify_blob_kzg_proof_batch_case_invalid_blob', {
        'input': {
            'blob': encode_hex_list(blobs_invalid),
            'commitment': encode_hex_list(commitments),
            'proof': encode_hex_list(proofs),
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
                runner_name='bls',
                handler_name=handler_name,
                suite_name='small',
                case_name=case_name,
                case_fn=lambda: [('data', 'data', case_content)]
            )

    return gen_typing.TestProvider(prepare=prepare_fn, make_cases=cases_fn)


if __name__ == "__main__":
    bls.use_arkworks()
    gen_runner.run_generator("bls", [
        # DENEB
        create_provider(DENEB, 'compute_kzg_proof', case01_compute_kzg_proof),
        create_provider(DENEB, 'blob_to_kzg_commitment', case02_blob_to_kzg_commitment),
        create_provider(DENEB, 'verify_kzg_proof', case03_verify_kzg_proof),
        create_provider(DENEB, 'compute_blob_kzg_proof', case04_compute_blob_kzg_proof),
        create_provider(DENEB, 'verify_blob_kzg_proof', case05_verify_blob_kzg_proof),
        create_provider(DENEB, 'verify_blob_kzg_proof_batch', case06_verify_blob_kzg_proof_batch),
    ])
