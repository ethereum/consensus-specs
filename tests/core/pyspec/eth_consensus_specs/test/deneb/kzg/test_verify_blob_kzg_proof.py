###############################################################################
# Test cases for verify_blob_kzg_proof
###############################################################################

from eth_utils.hexadecimal import encode_hex

from eth_consensus_specs.test.context import only_generator, single_phase, spec_test, with_phases
from eth_consensus_specs.test.helpers.constants import DENEB
from eth_consensus_specs.test.utils.kzg_tests import (
    BLOB_ALL_TWOS,
    BLOB_ALL_ZEROS,
    BLOB_RANDOM_VALID1,
    bls_add_one,
    G1,
    INVALID_BLOBS,
    INVALID_G1_POINTS,
    VALID_BLOBS,
)
from tests.infra.manifest import manifest
from tests.infra.template_test import template_test


def _run_verify_blob_kzg_proof_test(
    spec, blob, commitment, proof, expected_result=None, valid: bool = True
):
    if valid:
        result = spec.verify_blob_kzg_proof(blob, commitment, proof)
        if expected_result is not None:
            assert result == expected_result
    else:
        try:
            result = spec.verify_blob_kzg_proof(blob, commitment, proof)
        except Exception:
            result = None
        assert result == None

    yield (
        "data",
        "data",
        {
            "input": {
                "blob": encode_hex(blob),
                "commitment": encode_hex(commitment),
                "proof": encode_hex(proof),
            },
            "output": result,
        },
    )


@template_test
def _verify_blob_kzg_proof_case_correct_proof(blob_index):
    blob = VALID_BLOBS[blob_index]

    @manifest(preset_name="general", suite_name="kzg-mainnet")
    @only_generator("too slow")
    @with_phases([DENEB])
    @spec_test
    @single_phase
    def the_test(spec):
        commitment = spec.blob_to_kzg_commitment(blob)
        proof = spec.compute_blob_kzg_proof(blob, commitment)
        yield from _run_verify_blob_kzg_proof_test(
            spec, blob, commitment, proof, expected_result=True
        )

    return (the_test, f"test_verify_blob_kzg_proof_case_correct_proof_{blob_index}")


for blob_index in range(len(VALID_BLOBS)):
    _verify_blob_kzg_proof_case_correct_proof(blob_index)


@template_test
def _verify_blob_kzg_proof_case_incorrect_proof(blob_index):
    blob = VALID_BLOBS[blob_index]

    @manifest(preset_name="general", suite_name="kzg-mainnet")
    @only_generator("too slow")
    @with_phases([DENEB])
    @spec_test
    @single_phase
    def the_test(spec):
        commitment = spec.blob_to_kzg_commitment(blob)
        proof_orig = spec.compute_blob_kzg_proof(blob, commitment)
        proof = bls_add_one(proof_orig)
        yield from _run_verify_blob_kzg_proof_test(
            spec, blob, commitment, proof, expected_result=False
        )

    return (the_test, f"test_verify_blob_kzg_proof_case_incorrect_proof_{blob_index}")


for blob_index in range(len(VALID_BLOBS)):
    _verify_blob_kzg_proof_case_incorrect_proof(blob_index)


@manifest(preset_name="general", suite_name="kzg-mainnet")
@only_generator("too slow")
@with_phases([DENEB])
@spec_test
@single_phase
def test_verify_blob_kzg_proof_case_incorrect_proof_point_at_infinity(spec):
    blob = BLOB_RANDOM_VALID1
    commitment = spec.blob_to_kzg_commitment(blob)
    proof = spec.G1_POINT_AT_INFINITY
    yield from _run_verify_blob_kzg_proof_test(spec, blob, commitment, proof, expected_result=False)


@manifest(preset_name="general", suite_name="kzg-mainnet")
@only_generator("too slow")
@with_phases([DENEB])
@spec_test
@single_phase
def test_verify_blob_kzg_proof_case_correct_proof_point_at_infinity_for_zero_poly(spec):
    blob = BLOB_ALL_ZEROS
    commitment = spec.blob_to_kzg_commitment(blob)
    proof = spec.G1_POINT_AT_INFINITY
    yield from _run_verify_blob_kzg_proof_test(spec, blob, commitment, proof, expected_result=True)


@manifest(preset_name="general", suite_name="kzg-mainnet")
@only_generator("too slow")
@with_phases([DENEB])
@spec_test
@single_phase
def test_verify_blob_kzg_proof_case_correct_proof_point_at_infinity_for_twos_poly(spec):
    blob = BLOB_ALL_TWOS
    commitment = spec.blob_to_kzg_commitment(blob)
    proof = spec.G1_POINT_AT_INFINITY
    yield from _run_verify_blob_kzg_proof_test(spec, blob, commitment, proof, expected_result=True)


@template_test
def _verify_blob_kzg_proof_case_invalid_blob(blob_index):
    blob = INVALID_BLOBS[blob_index]
    proof = G1
    commitment = G1

    @manifest(preset_name="general", suite_name="kzg-mainnet")
    @only_generator("too slow")
    @with_phases([DENEB])
    @spec_test
    @single_phase
    def the_test(spec):
        yield from _run_verify_blob_kzg_proof_test(spec, blob, commitment, proof, valid=False)

    return (the_test, f"test_verify_blob_kzg_proof_case_invalid_blob_{blob_index}")


for blob_index in range(len(INVALID_BLOBS)):
    _verify_blob_kzg_proof_case_invalid_blob(blob_index)


@template_test
def _verify_blob_kzg_proof_case_invalid_commitment(commitment_index):
    blob = VALID_BLOBS[1]
    commitment = INVALID_G1_POINTS[commitment_index]
    proof = G1

    @manifest(preset_name="general", suite_name="kzg-mainnet")
    @only_generator("too slow")
    @with_phases([DENEB])
    @spec_test
    @single_phase
    def the_test(spec):
        yield from _run_verify_blob_kzg_proof_test(spec, blob, commitment, proof, valid=False)

    return (the_test, f"test_verify_blob_kzg_proof_case_invalid_commitment_{commitment_index}")


for commitment_index in range(len(INVALID_G1_POINTS)):
    _verify_blob_kzg_proof_case_invalid_commitment(commitment_index)


@template_test
def _verify_blob_kzg_proof_case_invalid_proof(proof_index):
    blob = VALID_BLOBS[1]
    commitment = G1
    proof = INVALID_G1_POINTS[proof_index]

    @manifest(preset_name="general", suite_name="kzg-mainnet")
    @only_generator("too slow")
    @with_phases([DENEB])
    @spec_test
    @single_phase
    def the_test(spec):
        yield from _run_verify_blob_kzg_proof_test(spec, blob, commitment, proof, valid=False)

    return (the_test, f"test_verify_blob_kzg_proof_case_invalid_proof_{proof_index}")


for proof_index in range(len(INVALID_G1_POINTS)):
    _verify_blob_kzg_proof_case_invalid_proof(proof_index)
