###############################################################################
# Test cases for compute_challenge
###############################################################################

from eth_utils.hexadecimal import encode_hex

from eth2spec.test.context import only_generator, single_phase, spec_test, with_phases
from eth2spec.test.helpers.constants import DENEB
from eth2spec.test.utils.kzg_tests import VALID_BLOBS
from tests.infra.manifest import manifest
from tests.infra.template_test import template_test


@template_test
def _compute_challenge_case_valid(blob_index):
    blob = VALID_BLOBS[blob_index]

    @manifest(preset_name="general", suite_name="kzg-mainnet")
    @only_generator("too slow")
    @with_phases([DENEB])
    @spec_test
    @single_phase
    def the_test(spec):
        commitment = spec.blob_to_kzg_commitment(blob)
        challenge = spec.compute_challenge(blob, commitment)

        yield (
            "data",
            "data",
            {
                "input": {
                    "blob": encode_hex(blob),
                    "commitment": encode_hex(commitment),
                },
                "output": encode_hex(spec.bls_field_to_bytes(challenge)),
            },
        )

    return (the_test, f"test_compute_challenge_case_valid_{blob_index}")


for blob_index in range(len(VALID_BLOBS)):
    _compute_challenge_case_valid(blob_index)


@manifest(preset_name="general", suite_name="kzg-mainnet")
@only_generator("too slow")
@with_phases([DENEB])
@spec_test
@single_phase
def test_compute_challenge_case_mismatched_commitment(spec):
    # Use commitment from a different blob
    commitment = spec.blob_to_kzg_commitment(VALID_BLOBS[4])
    blob = VALID_BLOBS[3]
    challenge = spec.compute_challenge(blob, commitment)

    yield (
        "data",
        "data",
        {
            "input": {
                "blob": encode_hex(blob),
                "commitment": encode_hex(commitment),
            },
            "output": encode_hex(spec.bls_field_to_bytes(challenge)),
        },
    )


@manifest(preset_name="general", suite_name="kzg-mainnet")
@only_generator("too slow")
@with_phases([DENEB])
@spec_test
@single_phase
def test_compute_challenge_case_commitment_at_infinity(spec):
    commitment = spec.G1_POINT_AT_INFINITY
    blob = VALID_BLOBS[4]
    challenge = spec.compute_challenge(blob, commitment)

    yield (
        "data",
        "data",
        {
            "input": {
                "blob": encode_hex(blob),
                "commitment": encode_hex(commitment),
            },
            "output": encode_hex(spec.bls_field_to_bytes(challenge)),
        },
    )
