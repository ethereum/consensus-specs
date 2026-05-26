###############################################################################
# Test cases for blob_to_kzg_commitment
###############################################################################

from eth_utils import encode_hex

from eth_consensus_specs.test.context import only_generator, single_phase, spec_test, with_phases
from eth_consensus_specs.test.helpers.constants import DENEB
from eth_consensus_specs.test.utils.kzg_tests import (
    INVALID_BLOBS,
    VALID_BLOBS,
)
from tests.infra.manifest import manifest
from tests.infra.template_test import template_test


@template_test
def _blob_to_kzg_commitment_case_valid_blob(index):
    blob = VALID_BLOBS[index]

    @manifest(preset_name="general", suite_name="kzg-mainnet")
    @only_generator("too slow")
    @with_phases([DENEB])
    @spec_test
    @single_phase
    def the_test(spec):
        commitment = spec.blob_to_kzg_commitment(blob)

        yield (
            "data",
            "data",
            {
                "input": {"blob": encode_hex(blob)},
                "output": encode_hex(commitment),
            },
        )

    return (the_test, f"test_blob_to_kzg_commitment_case_valid_blob_{index}")


for index in range(0, len(VALID_BLOBS)):
    _blob_to_kzg_commitment_case_valid_blob(index)


@template_test
def _blob_to_kzg_commitment_case_invalid_blob(index):
    blob = INVALID_BLOBS[index]

    @manifest(preset_name="general", suite_name="kzg-mainnet")
    @only_generator("too slow")
    @with_phases([DENEB])
    @spec_test
    @single_phase
    def the_test(spec):
        commitment = None
        try:
            commitment = spec.blob_to_kzg_commitment(blob)
        except Exception:
            pass

        # exception is thrown
        assert commitment is None

        yield (
            "data",
            "data",
            {
                "input": {"blob": encode_hex(blob)},
                "output": None,
            },
        )

    return (the_test, f"test_blob_to_kzg_commitment_case_invalid_blob_{index}")


for index in range(0, len(INVALID_BLOBS)):
    _blob_to_kzg_commitment_case_invalid_blob(index)
