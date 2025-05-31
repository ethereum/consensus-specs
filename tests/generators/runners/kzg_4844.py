"""
KZG test vectors generator for EIP-4844
"""

from functools import lru_cache
from typing import Iterable

from eth_utils import encode_hex

from eth2spec.deneb import spec
from eth2spec.gen_helpers.gen_base.gen_typing import TestCase
from eth2spec.test.helpers.constants import DENEB
from eth2spec.test.utils.kzg_tests import (
    BLOB_ALL_TWOS,
    BLOB_ALL_ZEROS,
    BLOB_RANDOM_VALID1,
    bls_add_one,
    encode_hex_list,
    G1,
    INVALID_BLOBS,
    INVALID_FIELD_ELEMENTS,
    INVALID_G1_POINTS,
    VALID_BLOBS,
    VALID_FIELD_ELEMENTS,
)

###############################################################################
# Test helpers
###############################################################################


@lru_cache(maxsize=None)
def cached_blob_to_kzg_commitment(blob):
    return spec.blob_to_kzg_commitment(blob)


@lru_cache(maxsize=None)
def cached_compute_blob_kzg_proof(blob, commitment):
    return spec.compute_blob_kzg_proof(blob, commitment)


###############################################################################
# Test cases for blob_to_kzg_commitment
###############################################################################


def case_blob_to_kzg_commitment():
    def get_test_runner(blob):
        def _runner():
            try:
                commitment = None
                commitment = cached_blob_to_kzg_commitment(blob)
            except Exception:
                pass
            return [
                (
                    "data",
                    "data",
                    {
                        "input": {"blob": encode_hex(blob)},
                        "output": encode_hex(commitment) if commitment is not None else None,
                    },
                )
            ]

        return _runner

    # Valid cases
    for index, blob in enumerate(VALID_BLOBS):
        yield f"blob_to_kzg_commitment_case_valid_blob_{index}", get_test_runner(blob)

    # Edge case: Invalid blobs
    for index, blob in enumerate(INVALID_BLOBS):
        yield f"blob_to_kzg_commitment_case_invalid_blob_{index}", get_test_runner(blob)


###############################################################################
# Test cases for compute_kzg_proof
###############################################################################


def case_compute_kzg_proof():
    def get_test_runner(blob, z):
        def _runner():
            try:
                proof, y = None, None
                proof, y = spec.compute_kzg_proof(blob, z)
            except Exception:
                pass
            return [
                (
                    "data",
                    "data",
                    {
                        "input": {
                            "blob": encode_hex(blob),
                            "z": encode_hex(z),
                        },
                        "output": (encode_hex(proof), encode_hex(y)) if proof is not None else None,
                    },
                )
            ]

        return _runner

    # Valid cases
    for i, blob in enumerate(VALID_BLOBS):
        for j, z in enumerate(VALID_FIELD_ELEMENTS):
            yield f"compute_kzg_proof_case_valid_blob_{i}_{j}", get_test_runner(blob, z)

    # Edge case: Invalid blobs
    for index, blob in enumerate(INVALID_BLOBS):
        z = VALID_FIELD_ELEMENTS[0]
        yield f"compute_kzg_proof_case_invalid_blob_{index}", get_test_runner(blob, z)

    # Edge case: Invalid z
    for index, z in enumerate(INVALID_FIELD_ELEMENTS):
        blob = VALID_BLOBS[4]
        yield f"compute_kzg_proof_case_invalid_z_{index}", get_test_runner(blob, z)


###############################################################################
# Test cases for verify_kzg_proof
###############################################################################


def case_verify_kzg_proof():
    def get_test_runner(input_getter):
        def _runner():
            commitment, z, y, proof = input_getter()
            try:
                ok = None
                ok = spec.verify_kzg_proof(commitment, z, y, proof)
            except Exception:
                pass
            return [
                (
                    "data",
                    "data",
                    {
                        "input": {
                            "commitment": encode_hex(commitment),
                            "z": encode_hex(z),
                            "y": encode_hex(y),
                            "proof": encode_hex(proof),
                        },
                        "output": ok if ok is not None else None,
                    },
                )
            ]

        return _runner

    # Valid cases
    for i, blob in enumerate(VALID_BLOBS):
        for j, z in enumerate(VALID_FIELD_ELEMENTS):

            def get_inputs(blob=blob, z=z):
                proof, y = spec.compute_kzg_proof(blob, z)
                commitment = cached_blob_to_kzg_commitment(blob)
                return commitment, z, y, proof

            yield f"verify_kzg_proof_case_correct_proof_{i}_{j}", get_test_runner(get_inputs)

    # Incorrect proofs
    for i, blob in enumerate(VALID_BLOBS):
        for j, z in enumerate(VALID_FIELD_ELEMENTS):

            def get_inputs(blob=blob, z=z):
                proof_orig, y = spec.compute_kzg_proof(blob, z)
                proof = bls_add_one(proof_orig)
                commitment = cached_blob_to_kzg_commitment(blob)
                return commitment, z, y, proof

            yield f"verify_kzg_proof_case_incorrect_proof_{i}_{j}", get_test_runner(get_inputs)

    # Incorrect `G1_POINT_AT_INFINITY` proof
    for index, z in enumerate(VALID_FIELD_ELEMENTS):

        def get_inputs(z=z):
            blob = BLOB_RANDOM_VALID1
            _, y = spec.compute_kzg_proof(blob, z)
            commitment = cached_blob_to_kzg_commitment(blob)
            proof = spec.G1_POINT_AT_INFINITY
            return commitment, z, y, proof

        yield (
            f"verify_kzg_proof_case_incorrect_proof_point_at_infinity_{index}",
            get_test_runner(get_inputs),
        )

    # Correct `G1_POINT_AT_INFINITY` proof for zero poly
    for index, z in enumerate(VALID_FIELD_ELEMENTS):

        def get_inputs(z=z):
            blob = BLOB_ALL_ZEROS
            _, y = spec.compute_kzg_proof(blob, z)
            commitment = cached_blob_to_kzg_commitment(blob)
            proof = spec.G1_POINT_AT_INFINITY
            return commitment, z, y, proof

        yield (
            f"verify_kzg_proof_case_correct_proof_point_at_infinity_for_zero_poly_{index}",
            get_test_runner(get_inputs),
        )

    # Correct `G1_POINT_AT_INFINITY` proof for poly of all twos
    for index, z in enumerate(VALID_FIELD_ELEMENTS):

        def get_inputs(z=z):
            blob = BLOB_ALL_TWOS
            _, y = spec.compute_kzg_proof(blob, z)
            commitment = cached_blob_to_kzg_commitment(blob)
            proof = spec.G1_POINT_AT_INFINITY
            return commitment, z, y, proof

        yield (
            f"verify_kzg_proof_case_correct_proof_point_at_infinity_for_twos_poly_{index}",
            get_test_runner(get_inputs),
        )

    # Edge case: Invalid commitment
    for index, commitment in enumerate(INVALID_G1_POINTS):

        def get_inputs(commitment=commitment):
            blob, z = VALID_BLOBS[2], VALID_FIELD_ELEMENTS[1]
            proof, y = spec.compute_kzg_proof(blob, z)
            return commitment, z, y, proof

        yield f"verify_kzg_proof_case_invalid_commitment_{index}", get_test_runner(get_inputs)

    # Edge case: Invalid z
    for index, z in enumerate(INVALID_FIELD_ELEMENTS):

        def get_inputs(z=z):
            blob, validz = VALID_BLOBS[4], VALID_FIELD_ELEMENTS[1]
            proof, y = spec.compute_kzg_proof(blob, validz)
            commitment = cached_blob_to_kzg_commitment(blob)
            return commitment, z, y, proof

        yield f"verify_kzg_proof_case_invalid_z_{index}", get_test_runner(get_inputs)

    # Edge case: Invalid y
    for index, y in enumerate(INVALID_FIELD_ELEMENTS):

        def get_inputs(y=y):
            blob, z = VALID_BLOBS[4], VALID_FIELD_ELEMENTS[1]
            proof, _ = spec.compute_kzg_proof(blob, z)
            commitment = cached_blob_to_kzg_commitment(blob)
            return commitment, z, y, proof

        yield f"verify_kzg_proof_case_invalid_y_{index}", get_test_runner(get_inputs)

    # Edge case: Invalid proof
    for index, proof in enumerate(INVALID_G1_POINTS):

        def get_inputs(proof=proof):
            blob, z = VALID_BLOBS[2], VALID_FIELD_ELEMENTS[1]
            _, y = spec.compute_kzg_proof(blob, z)
            commitment = cached_blob_to_kzg_commitment(blob)
            return commitment, z, y, proof

        yield f"verify_kzg_proof_case_invalid_proof_{index}", get_test_runner(get_inputs)


###############################################################################
# Test cases for compute_blob_kzg_proof
###############################################################################


def case_compute_blob_kzg_proof():
    def get_test_runner(input_getter):
        def _runner():
            blob, commitment = input_getter()
            try:
                proof = None
                proof = cached_compute_blob_kzg_proof(blob, commitment)
            except Exception:
                pass
            return [
                (
                    "data",
                    "data",
                    {
                        "input": {
                            "blob": encode_hex(blob),
                            "commitment": encode_hex(commitment),
                        },
                        "output": encode_hex(proof) if proof is not None else None,
                    },
                )
            ]

        return _runner

    # Valid cases
    for index, blob in enumerate(VALID_BLOBS):

        def get_inputs(blob=blob):
            commitment = cached_blob_to_kzg_commitment(blob)
            return blob, commitment

        yield f"compute_blob_kzg_proof_case_valid_blob_{index}", get_test_runner(get_inputs)

    # Edge case: Invalid blob
    for index, blob in enumerate(INVALID_BLOBS):

        def get_inputs(blob=blob):
            commitment = G1
            return blob, commitment

        yield f"compute_blob_kzg_proof_case_invalid_blob_{index}", get_test_runner(get_inputs)

    # Edge case: Invalid commitment
    for index, commitment in enumerate(INVALID_G1_POINTS):

        def get_inputs(commitment=commitment):
            blob = VALID_BLOBS[1]
            return blob, commitment

        yield f"compute_blob_kzg_proof_case_invalid_commitment_{index}", get_test_runner(get_inputs)


###############################################################################
# Test cases for verify_blob_kzg_proof
###############################################################################


def case_verify_blob_kzg_proof():
    def get_test_runner(input_getter):
        def _runner():
            blob, commitment, proof = input_getter()
            try:
                ok = None
                ok = spec.verify_blob_kzg_proof(blob, commitment, proof)
            except Exception:
                pass
            return [
                (
                    "data",
                    "data",
                    {
                        "input": {
                            "blob": encode_hex(blob),
                            "commitment": encode_hex(commitment),
                            "proof": encode_hex(proof),
                        },
                        "output": ok if ok is not None else None,
                    },
                )
            ]

        return _runner

    # Valid cases
    for index, blob in enumerate(VALID_BLOBS):

        def get_inputs(blob=blob):
            commitment = cached_blob_to_kzg_commitment(blob)
            proof = cached_compute_blob_kzg_proof(blob, commitment)
            return blob, commitment, proof

        yield f"verify_blob_kzg_proof_case_correct_proof_{index}", get_test_runner(get_inputs)

    # Incorrect proofs
    for index, blob in enumerate(VALID_BLOBS):

        def get_inputs(blob=blob):
            commitment = cached_blob_to_kzg_commitment(blob)
            proof = bls_add_one(cached_compute_blob_kzg_proof(blob, commitment))
            return blob, commitment, proof

        yield f"verify_blob_kzg_proof_case_incorrect_proof_{index}", get_test_runner(get_inputs)

    # Incorrect `G1_POINT_AT_INFINITY` proof
    if True:

        def get_inputs():
            blob = BLOB_RANDOM_VALID1
            commitment = cached_blob_to_kzg_commitment(blob)
            proof = spec.G1_POINT_AT_INFINITY
            return blob, commitment, proof

        yield (
            "verify_blob_kzg_proof_case_incorrect_proof_point_at_infinity",
            get_test_runner(get_inputs),
        )

    # Correct `G1_POINT_AT_INFINITY` proof and commitment for zero poly
    if True:

        def get_inputs():
            blob = BLOB_ALL_ZEROS
            commitment = cached_blob_to_kzg_commitment(blob)
            proof = spec.G1_POINT_AT_INFINITY
            return blob, commitment, proof

        yield (
            "verify_blob_kzg_proof_case_correct_proof_point_at_infinity_for_zero_poly",
            get_test_runner(get_inputs),
        )

    # Correct `G1_POINT_AT_INFINITY` proof for all twos poly
    if True:

        def get_inputs():
            blob = BLOB_ALL_TWOS
            commitment = cached_blob_to_kzg_commitment(blob)
            proof = spec.G1_POINT_AT_INFINITY
            return blob, commitment, proof

        yield (
            "verify_blob_kzg_proof_case_correct_proof_point_at_infinity_for_twos_poly",
            get_test_runner(get_inputs),
        )

    # Edge case: Invalid blob
    for index, blob in enumerate(INVALID_BLOBS):

        def get_inputs(blob=blob):
            proof = G1
            commitment = G1
            return blob, commitment, proof

        yield f"verify_blob_kzg_proof_case_invalid_blob_{index}", get_test_runner(get_inputs)

    # Edge case: Invalid commitment
    for index, commitment in enumerate(INVALID_G1_POINTS):

        def get_inputs(commitment=commitment):
            blob = VALID_BLOBS[1]
            proof = G1
            return blob, commitment, proof

        yield f"verify_blob_kzg_proof_case_invalid_commitment_{index}", get_test_runner(get_inputs)

    # Edge case: Invalid proof
    for index, proof in enumerate(INVALID_G1_POINTS):

        def get_inputs(proof=proof):
            blob = VALID_BLOBS[1]
            commitment = G1
            return blob, commitment, proof

        yield f"verify_blob_kzg_proof_case_invalid_proof_{index}", get_test_runner(get_inputs)


###############################################################################
# Test cases for verify_blob_kzg_proof_batch
###############################################################################


def case_verify_blob_kzg_proof_batch():
    def get_test_runner(input_getter):
        def _runner():
            blobs, commitments, proofs = input_getter()
            try:
                ok = None
                ok = spec.verify_blob_kzg_proof_batch(blobs, commitments, proofs)
            except Exception:
                pass
            return [
                (
                    "data",
                    "data",
                    {
                        "input": {
                            "blobs": encode_hex_list(blobs),
                            "commitments": encode_hex_list(commitments),
                            "proofs": encode_hex_list(proofs),
                        },
                        "output": ok if ok is not None else None,
                    },
                )
            ]

        return _runner

    # Valid cases
    for length in range(len(VALID_BLOBS)):

        def get_inputs(length=length):
            blobs = VALID_BLOBS[:length]
            commitments = [cached_blob_to_kzg_commitment(blob) for blob in blobs]
            proofs = [
                cached_compute_blob_kzg_proof(blob, commitments[i]) for i, blob in enumerate(blobs)
            ]
            return blobs, commitments, proofs

        yield f"verify_blob_kzg_proof_batch_case_{length}", get_test_runner(get_inputs)

    # Incorrect proof
    if True:

        def get_inputs():
            blobs = VALID_BLOBS
            commitments = [cached_blob_to_kzg_commitment(blob) for blob in blobs]
            proofs = [
                cached_compute_blob_kzg_proof(blob, commitments[i]) for i, blob in enumerate(blobs)
            ]
            # Add one to the first proof, so that it's incorrect
            proofs = [bls_add_one(proofs[0])] + proofs[1:]
            return blobs, commitments, proofs

        yield (
            "verify_blob_kzg_proof_batch_case_incorrect_proof_add_one",
            get_test_runner(get_inputs),
        )

    # Incorrect `G1_POINT_AT_INFINITY` proof
    if True:

        def get_inputs():
            blobs = [BLOB_RANDOM_VALID1]
            commitments = [cached_blob_to_kzg_commitment(blob) for blob in blobs]
            # Use the wrong proof
            proofs = [spec.G1_POINT_AT_INFINITY]
            return blobs, commitments, proofs

        yield (
            "verify_blob_kzg_proof_batch_case_incorrect_proof_point_at_infinity",
            get_test_runner(get_inputs),
        )

    # Edge case: Invalid blobs
    for index, blob in enumerate(INVALID_BLOBS):

        def get_inputs(blob=blob):
            blobs = VALID_BLOBS
            commitments = [cached_blob_to_kzg_commitment(blob) for blob in blobs]
            proofs = [
                cached_compute_blob_kzg_proof(blob, commitments[i]) for i, blob in enumerate(blobs)
            ]
            # Insert an invalid blob into the middle
            blobs = VALID_BLOBS[:4] + [blob] + VALID_BLOBS[5:]
            return blobs, commitments, proofs

        yield f"verify_blob_kzg_proof_batch_case_invalid_blob_{index}", get_test_runner(get_inputs)

    # Edge case: Invalid commitment
    for index, commitment in enumerate(INVALID_G1_POINTS):

        def get_inputs(commitment=commitment):
            blobs = VALID_BLOBS
            commitments = [cached_blob_to_kzg_commitment(blob) for blob in blobs]
            proofs = [
                cached_compute_blob_kzg_proof(blob, commitments[i]) for i, blob in enumerate(blobs)
            ]
            # Replace first commitment with an invalid commitment
            commitments = [commitment] + commitments[1:]
            return blobs, commitments, proofs

        yield (
            f"verify_blob_kzg_proof_batch_case_invalid_commitment_{index}",
            get_test_runner(get_inputs),
        )

    # Edge case: Invalid proof
    for index, proof in enumerate(INVALID_G1_POINTS):

        def get_inputs(proof=proof):
            blobs = VALID_BLOBS
            commitments = [cached_blob_to_kzg_commitment(blob) for blob in blobs]
            proofs = [
                cached_compute_blob_kzg_proof(blob, commitments[i]) for i, blob in enumerate(blobs)
            ]
            # Replace first proof with an invalid proof
            proofs = [proof] + proofs[1:]
            return blobs, commitments, proofs

        yield f"verify_blob_kzg_proof_batch_case_invalid_proof_{index}", get_test_runner(get_inputs)

    # Edge case: Blob length different
    if True:

        def get_inputs():
            blobs = VALID_BLOBS
            commitments = [cached_blob_to_kzg_commitment(blob) for blob in blobs]
            proofs = [
                cached_compute_blob_kzg_proof(blob, commitments[i]) for i, blob in enumerate(blobs)
            ]
            # Delete the last blob
            blobs = blobs[:-1]
            return blobs, commitments, proofs

        yield "verify_blob_kzg_proof_batch_case_blob_length_different", get_test_runner(get_inputs)

    # Edge case: Commitment length different
    if True:

        def get_inputs():
            blobs = VALID_BLOBS
            commitments = [cached_blob_to_kzg_commitment(blob) for blob in blobs]
            proofs = [
                cached_compute_blob_kzg_proof(blob, commitments[i]) for i, blob in enumerate(blobs)
            ]
            # Delete the last commitment
            commitments = commitments[:-1]
            return blobs, commitments, proofs

        yield (
            "verify_blob_kzg_proof_batch_case_commitment_length_different",
            get_test_runner(get_inputs),
        )

    # Edge case: Proof length different
    if True:

        def get_inputs():
            blobs = VALID_BLOBS
            commitments = [cached_blob_to_kzg_commitment(blob) for blob in blobs]
            proofs = [
                cached_compute_blob_kzg_proof(blob, commitments[i]) for i, blob in enumerate(blobs)
            ]
            # Delete the last proof
            proofs = proofs[:-1]
            return blobs, commitments, proofs

        yield "verify_blob_kzg_proof_batch_case_proof_length_different", get_test_runner(get_inputs)


###############################################################################
# Main logic
###############################################################################


def get_test_cases() -> Iterable[TestCase]:
    test_case_fns = [
        ("blob_to_kzg_commitment", case_blob_to_kzg_commitment),
        ("compute_kzg_proof", case_compute_kzg_proof),
        ("verify_kzg_proof", case_verify_kzg_proof),
        ("compute_blob_kzg_proof", case_compute_blob_kzg_proof),
        ("verify_blob_kzg_proof", case_verify_blob_kzg_proof),
        ("verify_blob_kzg_proof_batch", case_verify_blob_kzg_proof_batch),
    ]

    test_cases = []
    for handler_name, test_case_fn in test_case_fns:
        for case_name, case_fn in test_case_fn():
            test_cases.append(
                TestCase(
                    fork_name=DENEB,
                    preset_name="general",
                    runner_name="kzg",
                    handler_name=handler_name,
                    suite_name="kzg-mainnet",
                    case_name=case_name,
                    case_fn=case_fn,
                )
            )
    return test_cases
