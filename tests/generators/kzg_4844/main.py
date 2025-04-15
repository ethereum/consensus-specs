"""
KZG test vectors generator for EIP-4844
"""

from typing import Tuple, Iterable, Any, Callable, Dict

from eth_utils import encode_hex

from eth2spec.deneb import spec
from eth2spec.gen_helpers.gen_base import gen_runner, gen_typing
from eth2spec.test.helpers.constants import DENEB
from eth2spec.test.helpers.typing import SpecForkName
from eth2spec.test.utils.kzg_tests import (
    BLOB_ALL_TWOS,
    BLOB_ALL_ZEROS,
    BLOB_RANDOM_VALID1,
    G1,
    INVALID_BLOBS,
    INVALID_FIELD_ELEMENTS,
    INVALID_G1_POINTS,
    VALID_BLOBS,
    VALID_FIELD_ELEMENTS,
    bls_add_one,
    encode_hex_list,
    expect_exception,
    field_element_bytes,
    hash,
)
from eth2spec.utils import bls


###############################################################################
# Test cases for blob_to_kzg_commitment
###############################################################################


def case01_blob_to_kzg_commitment():
    # Valid cases
    for blob in VALID_BLOBS:
        commitment = spec.blob_to_kzg_commitment(blob)
        identifier = f"{encode_hex(hash(blob))}"
        yield f'blob_to_kzg_commitment_case_valid_blob_{(hash(bytes(identifier, "utf-8"))[:8]).hex()}', {
            "input": {
                "blob": encode_hex(blob),
            },
            "output": encode_hex(commitment),
        }

    # Edge case: Invalid blobs
    for blob in INVALID_BLOBS:
        identifier = f"{encode_hex(hash(blob))}"
        expect_exception(spec.blob_to_kzg_commitment, blob)
        yield f'blob_to_kzg_commitment_case_invalid_blob_{(hash(bytes(identifier, "utf-8"))[:8]).hex()}', {
            "input": {"blob": encode_hex(blob)},
            "output": None,
        }


###############################################################################
# Test cases for compute_kzg_proof
###############################################################################


def case02_compute_kzg_proof():
    # Valid cases
    for blob in VALID_BLOBS:
        for z in VALID_FIELD_ELEMENTS:
            proof, y = spec.compute_kzg_proof(blob, z)
            identifier = f"{encode_hex(hash(blob))}_{encode_hex(z)}"
            yield f'compute_kzg_proof_case_valid_blob_{(hash(bytes(identifier, "utf-8"))[:8]).hex()}', {
                "input": {
                    "blob": encode_hex(blob),
                    "z": encode_hex(z),
                },
                "output": (encode_hex(proof), encode_hex(y)),
            }

    # Edge case: Invalid blobs
    for blob in INVALID_BLOBS:
        z = VALID_FIELD_ELEMENTS[0]
        expect_exception(spec.compute_kzg_proof, blob, z)
        identifier = f"{encode_hex(hash(blob))}"
        yield f'compute_kzg_proof_case_invalid_blob_{(hash(bytes(identifier, "utf-8"))[:8]).hex()}', {
            "input": {
                "blob": encode_hex(blob),
                "z": encode_hex(z),
            },
            "output": None,
        }

    # Edge case: Invalid z
    for z in INVALID_FIELD_ELEMENTS:
        blob = VALID_BLOBS[4]
        expect_exception(spec.compute_kzg_proof, blob, z)
        identifier = f"{encode_hex(hash(z))}"
        yield f'compute_kzg_proof_case_invalid_z_{(hash(bytes(identifier, "utf-8"))[:8]).hex()}', {
            "input": {
                "blob": encode_hex(blob),
                "z": encode_hex(z),
            },
            "output": None,
        }


###############################################################################
# Test cases for verify_kzg_proof
###############################################################################


def case03_verify_kzg_proof():
    # Valid cases
    for blob in VALID_BLOBS:
        for z in VALID_FIELD_ELEMENTS:
            proof, y = spec.compute_kzg_proof(blob, z)
            commitment = spec.blob_to_kzg_commitment(blob)
            assert spec.verify_kzg_proof(commitment, z, y, proof)
            identifier = f"{encode_hex(hash(blob))}_{encode_hex(z)}"
            yield f'verify_kzg_proof_case_correct_proof_{(hash(bytes(identifier, "utf-8"))[:8]).hex()}', {
                "input": {
                    "commitment": encode_hex(commitment),
                    "z": encode_hex(z),
                    "y": encode_hex(y),
                    "proof": encode_hex(proof),
                },
                "output": True,
            }

    # Incorrect proofs
    for blob in VALID_BLOBS:
        for z in VALID_FIELD_ELEMENTS:
            proof_orig, y = spec.compute_kzg_proof(blob, z)
            proof = bls_add_one(proof_orig)
            commitment = spec.blob_to_kzg_commitment(blob)
            assert not spec.verify_kzg_proof(commitment, z, y, proof)
            identifier = f"{encode_hex(hash(blob))}_{encode_hex(z)}"
            yield f'verify_kzg_proof_case_incorrect_proof_{(hash(bytes(identifier, "utf-8"))[:8]).hex()}', {
                "input": {
                    "commitment": encode_hex(commitment),
                    "z": encode_hex(z),
                    "y": encode_hex(y),
                    "proof": encode_hex(proof),
                },
                "output": False,
            }

    # Incorrect `G1_POINT_AT_INFINITY` proof
    blob = BLOB_RANDOM_VALID1
    for z in VALID_FIELD_ELEMENTS:
        _, y = spec.compute_kzg_proof(blob, z)
        commitment = spec.blob_to_kzg_commitment(blob)
        proof = spec.G1_POINT_AT_INFINITY
        assert not spec.verify_kzg_proof(commitment, z, y, proof)
        prefix = "verify_kzg_proof_case_incorrect_proof_point_at_infinity"
        identifier = f"{encode_hex(hash(blob))}_{encode_hex(z)}"
        yield f'{prefix}_{(hash(bytes(identifier, "utf-8"))[:8]).hex()}', {
            "input": {
                "commitment": encode_hex(commitment),
                "z": encode_hex(z),
                "y": encode_hex(y),
                "proof": encode_hex(proof),
            },
            "output": False,
        }

    # Correct `G1_POINT_AT_INFINITY` proof for zero poly
    blob = BLOB_ALL_ZEROS
    for z in VALID_FIELD_ELEMENTS:
        _, y = spec.compute_kzg_proof(blob, z)
        commitment = spec.blob_to_kzg_commitment(blob)
        proof = spec.G1_POINT_AT_INFINITY
        assert spec.verify_kzg_proof(commitment, z, y, proof)
        prefix = "verify_kzg_proof_case_correct_proof_point_at_infinity_for_zero_poly"
        identifier = f"{encode_hex(hash(blob))}_{encode_hex(z)}"
        yield f'{prefix}_{(hash(bytes(identifier, "utf-8"))[:8]).hex()}', {
            "input": {
                "commitment": encode_hex(commitment),
                "z": encode_hex(z),
                "y": encode_hex(y),
                "proof": encode_hex(proof),
            },
            "output": True,
        }

    # Correct `G1_POINT_AT_INFINITY` proof for poly of all twos
    blob = BLOB_ALL_TWOS
    for z in VALID_FIELD_ELEMENTS:
        _, y = spec.compute_kzg_proof(blob, z)
        commitment = spec.blob_to_kzg_commitment(blob)
        proof = spec.G1_POINT_AT_INFINITY
        assert spec.verify_kzg_proof(commitment, z, y, proof)
        assert y == field_element_bytes(2)
        prefix = "verify_kzg_proof_case_correct_proof_point_at_infinity_for_twos_poly"
        identifier = f"{encode_hex(hash(blob))}_{encode_hex(z)}"
        yield f'{prefix}_{(hash(bytes(identifier, "utf-8"))[:8]).hex()}', {
            "input": {
                "commitment": encode_hex(commitment),
                "z": encode_hex(z),
                "y": encode_hex(y),
                "proof": encode_hex(proof),
            },
            "output": True,
        }

    # Edge case: Invalid commitment
    for commitment in INVALID_G1_POINTS:
        blob, z = VALID_BLOBS[2], VALID_FIELD_ELEMENTS[1]
        proof, y = spec.compute_kzg_proof(blob, z)
        expect_exception(spec.verify_kzg_proof, commitment, z, y, proof)
        identifier = f"{encode_hex(commitment)}"
        yield f'verify_kzg_proof_case_invalid_commitment_{(hash(bytes(identifier, "utf-8"))[:8]).hex()}', {
            "input": {
                "commitment": encode_hex(commitment),
                "z": encode_hex(z),
                "y": encode_hex(y),
                "proof": encode_hex(proof),
            },
            "output": None,
        }

    # Edge case: Invalid z
    for z in INVALID_FIELD_ELEMENTS:
        blob, validz = VALID_BLOBS[4], VALID_FIELD_ELEMENTS[1]
        proof, y = spec.compute_kzg_proof(blob, validz)
        commitment = spec.blob_to_kzg_commitment(blob)
        expect_exception(spec.verify_kzg_proof, commitment, z, y, proof)
        identifier = f"{encode_hex(z)}"
        yield f'verify_kzg_proof_case_invalid_z_{(hash(bytes(identifier, "utf-8"))[:8]).hex()}', {
            "input": {
                "commitment": encode_hex(commitment),
                "z": encode_hex(z),
                "y": encode_hex(y),
                "proof": encode_hex(proof),
            },
            "output": None,
        }

    # Edge case: Invalid y
    for y in INVALID_FIELD_ELEMENTS:
        blob, z = VALID_BLOBS[4], VALID_FIELD_ELEMENTS[1]
        proof, _ = spec.compute_kzg_proof(blob, z)
        commitment = spec.blob_to_kzg_commitment(blob)
        expect_exception(spec.verify_kzg_proof, commitment, z, y, proof)
        identifier = f"{encode_hex(y)}"
        yield f'verify_kzg_proof_case_invalid_y_{(hash(bytes(identifier, "utf-8"))[:8]).hex()}', {
            "input": {
                "commitment": encode_hex(commitment),
                "z": encode_hex(z),
                "y": encode_hex(y),
                "proof": encode_hex(proof),
            },
            "output": None,
        }

    # Edge case: Invalid proof
    for proof in INVALID_G1_POINTS:
        blob, z = VALID_BLOBS[2], VALID_FIELD_ELEMENTS[1]
        _, y = spec.compute_kzg_proof(blob, z)
        commitment = spec.blob_to_kzg_commitment(blob)
        expect_exception(spec.verify_kzg_proof, commitment, z, y, proof)
        identifier = f"{encode_hex(proof)}"
        yield f'verify_kzg_proof_case_invalid_proof_{(hash(bytes(identifier, "utf-8"))[:8]).hex()}', {
            "input": {
                "commitment": encode_hex(commitment),
                "z": encode_hex(z),
                "y": encode_hex(y),
                "proof": encode_hex(proof),
            },
            "output": None,
        }


###############################################################################
# Test cases for compute_blob_kzg_proof
###############################################################################


def case04_compute_blob_kzg_proof():
    # Valid cases
    for blob in VALID_BLOBS:
        commitment = spec.blob_to_kzg_commitment(blob)
        proof = spec.compute_blob_kzg_proof(blob, commitment)
        identifier = f"{encode_hex(hash(blob))}"
        yield f'compute_blob_kzg_proof_case_valid_blob_{(hash(bytes(identifier, "utf-8"))[:8]).hex()}', {
            "input": {
                "blob": encode_hex(blob),
                "commitment": encode_hex(commitment),
            },
            "output": encode_hex(proof),
        }

    # Edge case: Invalid blob
    for blob in INVALID_BLOBS:
        commitment = G1
        expect_exception(spec.compute_blob_kzg_proof, blob, commitment)
        identifier = f"{encode_hex(hash(blob))}"
        yield f'compute_blob_kzg_proof_case_invalid_blob_{(hash(bytes(identifier, "utf-8"))[:8]).hex()}', {
            "input": {
                "blob": encode_hex(blob),
                "commitment": encode_hex(commitment),
            },
            "output": None,
        }

    # Edge case: Invalid commitment
    for commitment in INVALID_G1_POINTS:
        blob = VALID_BLOBS[1]
        expect_exception(spec.compute_blob_kzg_proof, blob, commitment)
        identifier = f"{encode_hex(hash(commitment))}"
        yield f'compute_blob_kzg_proof_case_invalid_commitment_{(hash(bytes(identifier, "utf-8"))[:8]).hex()}', {
            "input": {
                "blob": encode_hex(blob),
                "commitment": encode_hex(commitment),
            },
            "output": None,
        }


###############################################################################
# Test cases for verify_blob_kzg_proof
###############################################################################


def case05_verify_blob_kzg_proof():
    # Valid cases
    for blob in VALID_BLOBS:
        commitment = spec.blob_to_kzg_commitment(blob)
        proof = spec.compute_blob_kzg_proof(blob, commitment)
        assert spec.verify_blob_kzg_proof(blob, commitment, proof)
        identifier = f"{encode_hex(hash(blob))}"
        yield f'verify_blob_kzg_proof_case_correct_proof_{(hash(bytes(identifier, "utf-8"))[:8]).hex()}', {
            "input": {
                "blob": encode_hex(blob),
                "commitment": encode_hex(commitment),
                "proof": encode_hex(proof),
            },
            "output": True,
        }

    # Incorrect proofs
    for blob in VALID_BLOBS:
        commitment = spec.blob_to_kzg_commitment(blob)
        proof = bls_add_one(spec.compute_blob_kzg_proof(blob, commitment))
        assert not spec.verify_blob_kzg_proof(blob, commitment, proof)
        identifier = f"{encode_hex(hash(blob))}"
        yield f'verify_blob_kzg_proof_case_incorrect_proof_{(hash(bytes(identifier, "utf-8"))[:8]).hex()}', {
            "input": {
                "blob": encode_hex(blob),
                "commitment": encode_hex(commitment),
                "proof": encode_hex(proof),
            },
            "output": False,
        }

    # Incorrect `G1_POINT_AT_INFINITY` proof
    blob = BLOB_RANDOM_VALID1
    commitment = spec.blob_to_kzg_commitment(blob)
    proof = spec.G1_POINT_AT_INFINITY
    assert not spec.verify_blob_kzg_proof(blob, commitment, proof)
    yield "verify_blob_kzg_proof_case_incorrect_proof_point_at_infinity", {
        "input": {
            "blob": encode_hex(blob),
            "commitment": encode_hex(commitment),
            "proof": encode_hex(proof),
        },
        "output": False,
    }

    # Correct `G1_POINT_AT_INFINITY` proof and commitment for zero poly
    blob = BLOB_ALL_ZEROS
    commitment = spec.blob_to_kzg_commitment(blob)
    proof = spec.G1_POINT_AT_INFINITY
    assert commitment == spec.G1_POINT_AT_INFINITY
    assert spec.verify_blob_kzg_proof(blob, commitment, proof)
    yield "verify_blob_kzg_proof_case_correct_proof_point_at_infinity_for_zero_poly", {
        "input": {
            "blob": encode_hex(blob),
            "commitment": encode_hex(commitment),
            "proof": encode_hex(proof),
        },
        "output": True,
    }

    # Correct `G1_POINT_AT_INFINITY` proof for all twos poly
    blob = BLOB_ALL_TWOS
    commitment = spec.blob_to_kzg_commitment(blob)
    proof = spec.G1_POINT_AT_INFINITY
    assert commitment != spec.G1_POINT_AT_INFINITY
    assert spec.verify_blob_kzg_proof(blob, commitment, proof)
    yield "verify_blob_kzg_proof_case_correct_proof_point_at_infinity_for_twos_poly", {
        "input": {
            "blob": encode_hex(blob),
            "commitment": encode_hex(commitment),
            "proof": encode_hex(proof),
        },
        "output": True,
    }

    # Edge case: Invalid blob
    for blob in INVALID_BLOBS:
        proof = G1
        commitment = G1
        expect_exception(spec.verify_blob_kzg_proof, blob, commitment, proof)
        identifier = f"{encode_hex(hash(blob))}"
        yield f'verify_blob_kzg_proof_case_invalid_blob_{(hash(bytes(identifier, "utf-8"))[:8]).hex()}', {
            "input": {
                "blob": encode_hex(blob),
                "commitment": encode_hex(commitment),
                "proof": encode_hex(proof),
            },
            "output": None,
        }

    # Edge case: Invalid commitment
    for commitment in INVALID_G1_POINTS:
        blob = VALID_BLOBS[1]
        proof = G1
        expect_exception(spec.verify_blob_kzg_proof, blob, commitment, proof)
        identifier = f"{encode_hex(hash(commitment))}"
        yield f'verify_blob_kzg_proof_case_invalid_commitment_{(hash(bytes(identifier, "utf-8"))[:8]).hex()}', {
            "input": {
                "blob": encode_hex(blob),
                "commitment": encode_hex(commitment),
                "proof": encode_hex(proof),
            },
            "output": None,
        }

    # Edge case: Invalid proof
    for proof in INVALID_G1_POINTS:
        blob = VALID_BLOBS[1]
        commitment = G1
        expect_exception(spec.verify_blob_kzg_proof, blob, commitment, proof)
        identifier = f"{encode_hex(hash(proof))}"
        yield f'verify_blob_kzg_proof_case_invalid_proof_{(hash(bytes(identifier, "utf-8"))[:8]).hex()}', {
            "input": {
                "blob": encode_hex(blob),
                "commitment": encode_hex(commitment),
                "proof": encode_hex(proof),
            },
            "output": None,
        }


###############################################################################
# Test cases for verify_blob_kzg_proof_batch
###############################################################################


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
            "input": {
                "blobs": encode_hex_list(VALID_BLOBS[:i]),
                "commitments": encode_hex_list(commitments[:i]),
                "proofs": encode_hex_list(proofs[:i]),
            },
            "output": True,
        }

    # Incorrect proof
    proofs_incorrect = [bls_add_one(proofs[0])] + proofs[1:]
    assert not spec.verify_blob_kzg_proof_batch(VALID_BLOBS, commitments, proofs_incorrect)
    yield "verify_blob_kzg_proof_batch_case_incorrect_proof_add_one", {
        "input": {
            "blobs": encode_hex_list(VALID_BLOBS),
            "commitments": encode_hex_list(commitments),
            "proofs": encode_hex_list(proofs_incorrect),
        },
        "output": False,
    }

    # Incorrect `G1_POINT_AT_INFINITY` proof
    blob = BLOB_RANDOM_VALID1
    commitment = spec.blob_to_kzg_commitment(blob)
    proof = spec.G1_POINT_AT_INFINITY
    assert not spec.verify_blob_kzg_proof_batch([blob], [commitment], [proof])
    yield "verify_blob_kzg_proof_batch_case_incorrect_proof_point_at_infinity", {
        "input": {
            "blobs": encode_hex_list([blob]),
            "commitments": encode_hex_list([commitment]),
            "proofs": encode_hex_list([proof]),
        },
        "output": False,
    }

    # Edge case: Invalid blobs
    for blob in INVALID_BLOBS:
        blobs_invalid = VALID_BLOBS[:4] + [blob] + VALID_BLOBS[5:]
        expect_exception(spec.verify_blob_kzg_proof_batch, blobs_invalid, commitments, proofs)
        identifier = f"{encode_hex(hash(blob))}"
        yield f'verify_blob_kzg_proof_batch_case_invalid_blob_{(hash(bytes(identifier, "utf-8"))[:8]).hex()}', {
            "input": {
                "blobs": encode_hex_list(blobs_invalid),
                "commitments": encode_hex_list(commitments),
                "proofs": encode_hex_list(proofs),
            },
            "output": None,
        }

    # Edge case: Invalid commitment
    for commitment in INVALID_G1_POINTS:
        blobs = VALID_BLOBS
        commitments_invalid = [commitment] + commitments[1:]
        expect_exception(spec.verify_blob_kzg_proof_batch, blobs, commitments_invalid, proofs)
        identifier = f"{encode_hex(hash(commitment))}"
        yield f'verify_blob_kzg_proof_batch_case_invalid_commitment_{(hash(bytes(identifier, "utf-8"))[:8]).hex()}', {
            "input": {
                "blobs": encode_hex_list(blobs),
                "commitments": encode_hex_list(commitments_invalid),
                "proofs": encode_hex_list(proofs),
            },
            "output": None,
        }

    # Edge case: Invalid proof
    for proof in INVALID_G1_POINTS:
        blobs = VALID_BLOBS
        proofs_invalid = [proof] + proofs[1:]
        expect_exception(spec.verify_blob_kzg_proof_batch, blobs, commitments, proofs_invalid)
        identifier = f"{encode_hex(hash(proof))}"
        yield f'verify_blob_kzg_proof_batch_case_invalid_proof_{(hash(bytes(identifier, "utf-8"))[:8]).hex()}', {
            "input": {
                "blobs": encode_hex_list(blobs),
                "commitments": encode_hex_list(commitments),
                "proofs": encode_hex_list(proofs_invalid),
            },
            "output": None,
        }

    # Edge case: Blob length different
    expect_exception(spec.verify_blob_kzg_proof_batch, VALID_BLOBS[:-1], commitments, proofs)
    yield "verify_blob_kzg_proof_batch_case_blob_length_different", {
        "input": {
            "blobs": encode_hex_list(VALID_BLOBS[:-1]),
            "commitments": encode_hex_list(commitments),
            "proofs": encode_hex_list(proofs),
        },
        "output": None,
    }

    # Edge case: Commitment length different
    expect_exception(spec.verify_blob_kzg_proof_batch, VALID_BLOBS, commitments[:-1], proofs)
    yield "verify_blob_kzg_proof_batch_case_commitment_length_different", {
        "input": {
            "blobs": encode_hex_list(VALID_BLOBS),
            "commitments": encode_hex_list(commitments[:-1]),
            "proofs": encode_hex_list(proofs),
        },
        "output": None,
    }

    # Edge case: Proof length different
    expect_exception(spec.verify_blob_kzg_proof_batch, VALID_BLOBS, commitments, proofs[:-1])
    yield "verify_blob_kzg_proof_batch_case_proof_length_different", {
        "input": {
            "blobs": encode_hex_list(VALID_BLOBS),
            "commitments": encode_hex_list(commitments),
            "proofs": encode_hex_list(proofs[:-1]),
        },
        "output": None,
    }


###############################################################################
# Main logic
###############################################################################


def create_provider(
    fork_name: SpecForkName,
    handler_name: str,
    test_case_fn: Callable[[], Iterable[Tuple[str, Dict[str, Any]]]],
) -> gen_typing.TestProvider:

    def prepare_fn() -> None:
        # Nothing to load / change in spec. Maybe in future forks.
        # Put the tests into the general config category, to not require any particular configuration.
        return

    def cases_fn() -> Iterable[gen_typing.TestCase]:
        for data in test_case_fn():
            (case_name, case_content) = data
            yield gen_typing.TestCase(
                fork_name=fork_name,
                preset_name="general",
                runner_name="kzg",
                handler_name=handler_name,
                suite_name="kzg-mainnet",
                case_name=case_name,
                case_fn=lambda: [("data", "data", case_content)],
            )

    return gen_typing.TestProvider(prepare=prepare_fn, make_cases=cases_fn)


if __name__ == "__main__":
    bls.use_arkworks()
    gen_runner.run_generator(
        "kzg",
        [
            create_provider(DENEB, "blob_to_kzg_commitment", case01_blob_to_kzg_commitment),
            create_provider(DENEB, "compute_kzg_proof", case02_compute_kzg_proof),
            create_provider(DENEB, "verify_kzg_proof", case03_verify_kzg_proof),
            create_provider(DENEB, "compute_blob_kzg_proof", case04_compute_blob_kzg_proof),
            create_provider(DENEB, "verify_blob_kzg_proof", case05_verify_blob_kzg_proof),
            create_provider(
                DENEB, "verify_blob_kzg_proof_batch", case06_verify_blob_kzg_proof_batch
            ),
        ],
    )
