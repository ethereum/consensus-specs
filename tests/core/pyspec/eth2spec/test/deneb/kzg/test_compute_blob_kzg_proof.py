###############################################################################
# Test cases for compute_blob_kzg_proof
###############################################################################

from eth_utils.hexadecimal import encode_hex

from eth2spec.test.context import only_generator, single_phase, spec_test, with_phases
from eth2spec.test.helpers.constants import DENEB
from eth2spec.test.utils.kzg_tests import G1, INVALID_BLOBS, INVALID_G1_POINTS, VALID_BLOBS
from tests.infra.manifest import manifest
from tests.infra.template_test import template_test


@template_test
def _compute_blob_kzg_proof_case_valid_blob(blob_index):
    blob = VALID_BLOBS[blob_index]

    @manifest(preset_name="general", suite_name="kzg-mainnet")
    @only_generator("too slow")
    @with_phases([DENEB])
    @spec_test
    @single_phase
    def the_test(spec):
        commitment = spec.blob_to_kzg_commitment(blob)
        proof = spec.compute_blob_kzg_proof(blob, commitment)

        yield (
            "data",
            "data",
            {
                "input": {
                    "blob": encode_hex(blob),
                    "commitment": encode_hex(commitment),
                },
                "output": encode_hex(proof),
            },
        )

    return (the_test, f"test_compute_blob_kzg_proof_case_valid_blob_{blob_index}")


for blob_index in range(len(VALID_BLOBS)):
    _compute_blob_kzg_proof_case_valid_blob(blob_index)


@template_test
def _compute_blob_kzg_proof_case_invalid_blob(blob_index):
    blob = INVALID_BLOBS[blob_index]
    commitment = G1

    @manifest(preset_name="general", suite_name="kzg-mainnet")
    @only_generator("too slow")
    @with_phases([DENEB])
    @spec_test
    @single_phase
    def the_test(spec):
        try:
            proof = spec.compute_blob_kzg_proof(blob, commitment)
        except Exception:
            proof = None

        # assert exception is thrown
        assert proof == None

        yield (
            "data",
            "data",
            {
                "input": {
                    "blob": encode_hex(blob),
                    "commitment": encode_hex(commitment),
                },
                "output": None,
            },
        )

    return (the_test, f"test_compute_blob_kzg_proof_case_invalid_blob_{blob_index}")


for blob_index in range(len(INVALID_BLOBS)):
    _compute_blob_kzg_proof_case_invalid_blob(blob_index)


@template_test
def _compute_blob_kzg_proof_case_invalid_commitment(commitment_index):
    blob = VALID_BLOBS[1]
    commitment = INVALID_G1_POINTS[commitment_index]

    @manifest(preset_name="general", suite_name="kzg-mainnet")
    @only_generator("too slow")
    @with_phases([DENEB])
    @spec_test
    @single_phase
    def the_test(spec):
        try:
            proof = spec.compute_blob_kzg_proof(blob, commitment)
        except Exception:
            proof = None

        # assert exception is thrown
        assert proof == None

        yield (
            "data",
            "data",
            {
                "input": {
                    "blob": encode_hex(blob),
                    "commitment": encode_hex(commitment),
                },
                "output": None,
            },
        )

    return (the_test, f"test_compute_blob_kzg_proof_case_invalid_commitment_{commitment_index}")


for commitment_index in range(len(INVALID_G1_POINTS)):
    _compute_blob_kzg_proof_case_invalid_commitment(commitment_index)
