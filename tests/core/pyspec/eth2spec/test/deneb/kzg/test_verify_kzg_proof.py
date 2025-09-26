###############################################################################
# Test cases for verify_kzg_proof
###############################################################################

from eth_utils import encode_hex

from eth2spec.test.context import only_generator, single_phase, spec_test, with_phases
from eth2spec.test.helpers.constants import DENEB
from eth2spec.test.utils.kzg_tests import (
    BLOB_ALL_TWOS,
    BLOB_ALL_ZEROS,
    BLOB_RANDOM_VALID1,
    bls_add_one,
    INVALID_FIELD_ELEMENTS,
    INVALID_G1_POINTS,
    VALID_BLOBS,
    VALID_FIELD_ELEMENTS,
)
from tests.infra.manifest import manifest
from tests.infra.template_test import template_test

def _run_verify_kzg_proof_test(spec, commitment, z, y, proof, expected_result=None, valid: bool = True):
    if valid:
        result = spec.verify_kzg_proof(commitment, z, y, proof)
        if expected_result is not None:
            assert result == expected_result
    else:
        try:
            result = spec.verify_kzg_proof(commitment, z, y, proof)
        except Exception:
            result = None
        assert result == None

    yield (
        "data",
        "data",
        {
            "input": {
                "commitment": encode_hex(commitment),
                "z": encode_hex(z),
                "y": encode_hex(y),
                "proof": encode_hex(proof),
            },
            "output": result,
        },
    )


@template_test
def _verify_kzg_proof_case_correct_proof(blob_index, z_index):
    blob = VALID_BLOBS[blob_index]
    z = VALID_FIELD_ELEMENTS[z_index]

    @manifest(preset_name="general", suite_name="kzg-mainnet")
    @only_generator("too slow")
    @with_phases([DENEB])
    @spec_test
    @single_phase
    def the_test(spec):
        proof, y = spec.compute_kzg_proof(blob, z)
        commitment = spec.blob_to_kzg_commitment(blob)
        yield from _run_verify_kzg_proof_test(spec, commitment, z, y, proof, expected_result=True)

    return (the_test, f"test_verify_kzg_proof_case_correct_proof_{blob_index}_{z_index}")


for blob_index in range(len(VALID_BLOBS)):
    for z_index in range(len(VALID_FIELD_ELEMENTS)):
        _verify_kzg_proof_case_correct_proof(blob_index, z_index)


@template_test
def _verify_kzg_proof_case_incorrect_proof(blob_index, z_index):
    blob = VALID_BLOBS[blob_index]
    z = VALID_FIELD_ELEMENTS[z_index]

    @manifest(preset_name="general", suite_name="kzg-mainnet")
    @only_generator("too slow")
    @with_phases([DENEB])
    @spec_test
    @single_phase
    def the_test(spec):
        proof_orig, y = spec.compute_kzg_proof(blob, z)
        proof = bls_add_one(proof_orig)
        commitment = spec.blob_to_kzg_commitment(blob)
        yield from _run_verify_kzg_proof_test(spec, commitment, z, y, proof, expected_result=False)

    return (the_test, f"test_verify_kzg_proof_case_incorrect_proof_{blob_index}_{z_index}")


for blob_index in range(len(VALID_BLOBS)):
    for z_index in range(len(VALID_FIELD_ELEMENTS)):
        _verify_kzg_proof_case_incorrect_proof(blob_index, z_index)


@template_test
def _verify_kzg_proof_case_incorrect_proof_point_at_infinity(z_index):
    z = VALID_FIELD_ELEMENTS[z_index]

    @manifest(preset_name="general", suite_name="kzg-mainnet")
    @only_generator("too slow")
    @with_phases([DENEB])
    @spec_test
    @single_phase
    def the_test(spec):
        blob = BLOB_RANDOM_VALID1
        _, y = spec.compute_kzg_proof(blob, z)
        commitment = spec.blob_to_kzg_commitment(blob)
        proof = spec.G1_POINT_AT_INFINITY
        yield from _run_verify_kzg_proof_test(spec, commitment, z, y, proof, expected_result=False)

    return (the_test, f"test_verify_kzg_proof_case_incorrect_proof_point_at_infinity_{z_index}")


for z_index in range(len(VALID_FIELD_ELEMENTS)):
    _verify_kzg_proof_case_incorrect_proof_point_at_infinity(z_index)


@template_test
def _verify_kzg_proof_case_correct_proof_point_at_infinity_for_zero_poly(z_index):
    z = VALID_FIELD_ELEMENTS[z_index]

    @manifest(preset_name="general", suite_name="kzg-mainnet")
    @only_generator("too slow")
    @with_phases([DENEB])
    @spec_test
    @single_phase
    def the_test(spec):
        blob = BLOB_ALL_ZEROS
        _, y = spec.compute_kzg_proof(blob, z)
        commitment = spec.blob_to_kzg_commitment(blob)
        proof = spec.G1_POINT_AT_INFINITY
        yield from _run_verify_kzg_proof_test(spec, commitment, z, y, proof, expected_result=True)

    return (
        the_test,
        f"test_verify_kzg_proof_case_correct_proof_point_at_infinity_for_zero_poly_{z_index}",
    )


for z_index in range(len(VALID_FIELD_ELEMENTS)):
    _verify_kzg_proof_case_correct_proof_point_at_infinity_for_zero_poly(z_index)


@template_test
def _verify_kzg_proof_case_correct_proof_point_at_infinity_for_twos_poly(z_index):
    z = VALID_FIELD_ELEMENTS[z_index]

    @manifest(preset_name="general", suite_name="kzg-mainnet")
    @only_generator("too slow")
    @with_phases([DENEB])
    @spec_test
    @single_phase
    def the_test(spec):
        blob = BLOB_ALL_TWOS
        _, y = spec.compute_kzg_proof(blob, z)
        commitment = spec.blob_to_kzg_commitment(blob)
        proof = spec.G1_POINT_AT_INFINITY
        yield from _run_verify_kzg_proof_test(spec, commitment, z, y, proof, expected_result=True)

    return (
        the_test,
        f"test_verify_kzg_proof_case_correct_proof_point_at_infinity_for_twos_poly_{z_index}",
    )


for z_index in range(len(VALID_FIELD_ELEMENTS)):
    _verify_kzg_proof_case_correct_proof_point_at_infinity_for_twos_poly(z_index)


@template_test
def _verify_kzg_proof_case_invalid_commitment(commitment_index):
    commitment = INVALID_G1_POINTS[commitment_index]

    @manifest(preset_name="general", suite_name="kzg-mainnet")
    @only_generator("too slow")
    @with_phases([DENEB])
    @spec_test
    @single_phase
    def the_test(spec):
        blob, z = VALID_BLOBS[2], VALID_FIELD_ELEMENTS[1]
        proof, y = spec.compute_kzg_proof(blob, z)
        yield from _run_verify_kzg_proof_test(spec, commitment, z, y, proof, valid=False)

    return (the_test, f"test_verify_kzg_proof_case_invalid_commitment_{commitment_index}")


for commitment_index in range(len(INVALID_G1_POINTS)):
    _verify_kzg_proof_case_invalid_commitment(commitment_index)


@template_test
def _verify_kzg_proof_case_invalid_z(z_index):
    z = INVALID_FIELD_ELEMENTS[z_index]

    @manifest(preset_name="general", suite_name="kzg-mainnet")
    @only_generator("too slow")
    @with_phases([DENEB])
    @spec_test
    @single_phase
    def the_test(spec):
        blob, validz = VALID_BLOBS[4], VALID_FIELD_ELEMENTS[1]
        proof, y = spec.compute_kzg_proof(blob, validz)
        commitment = spec.blob_to_kzg_commitment(blob)
        yield from _run_verify_kzg_proof_test(spec, commitment, z, y, proof, valid=False)

    return (the_test, f"test_verify_kzg_proof_case_invalid_z_{z_index}")


for z_index in range(len(INVALID_FIELD_ELEMENTS)):
    _verify_kzg_proof_case_invalid_z(z_index)


@template_test
def _verify_kzg_proof_case_invalid_y(y_index):
    y = INVALID_FIELD_ELEMENTS[y_index]

    @manifest(preset_name="general", suite_name="kzg-mainnet")
    @only_generator("too slow")
    @with_phases([DENEB])
    @spec_test
    @single_phase
    def the_test(spec):
        blob, z = VALID_BLOBS[4], VALID_FIELD_ELEMENTS[1]
        proof, _ = spec.compute_kzg_proof(blob, z)
        commitment = spec.blob_to_kzg_commitment(blob)
        yield from _run_verify_kzg_proof_test(spec, commitment, z, y, proof, valid=False)

    return (the_test, f"test_verify_kzg_proof_case_invalid_y_{y_index}")


for y_index in range(len(INVALID_FIELD_ELEMENTS)):
    _verify_kzg_proof_case_invalid_y(y_index)


@template_test
def _verify_kzg_proof_case_invalid_proof(proof_index):
    proof = INVALID_G1_POINTS[proof_index]

    @manifest(preset_name="general", suite_name="kzg-mainnet")
    @only_generator("too slow")
    @with_phases([DENEB])
    @spec_test
    @single_phase
    def the_test(spec):
        blob, z = VALID_BLOBS[2], VALID_FIELD_ELEMENTS[1]
        _, y = spec.compute_kzg_proof(blob, z)
        commitment = spec.blob_to_kzg_commitment(blob)
        yield from _run_verify_kzg_proof_test(spec, commitment, z, y, proof, valid=False)

    return (the_test, f"test_verify_kzg_proof_case_invalid_proof_{proof_index}")


for proof_index in range(len(INVALID_G1_POINTS)):
    _verify_kzg_proof_case_invalid_proof(proof_index)
