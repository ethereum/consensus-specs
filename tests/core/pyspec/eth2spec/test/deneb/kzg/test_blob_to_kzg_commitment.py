###############################################################################
# Test cases for blob_to_kzg_commitment
###############################################################################

from eth_utils import encode_hex

from eth2spec.test.context import single_phase, spec_test, with_phases
from eth2spec.test.utils.kzg_tests import (
    INVALID_BLOBS,
    VALID_BLOBS,
)
from tests.core.pyspec.eth2spec.test.helpers.constants import DENEB
from tests.infra.spec_cache import spec_cache
from tests.infra.template_test import template_test
from tests.infra.manifest import manifest


@template_test
def _blob_to_kzg_commitment_case_valid_blob(index):
    blob = VALID_BLOBS[index]

    @manifest(preset_name="general", suite_name="kzg-mainnet")
    @with_phases([DENEB])
    @spec_test
    @single_phase
    @spec_cache(["blob_to_kzg_commitment"])
    def the_test(spec):
        commitment = spec.blob_to_kzg_commitment(blob)
        # assert exception is not thrown with valid blob

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
    @with_phases([DENEB])
    @spec_test
    @single_phase
    @spec_cache(["blob_to_kzg_commitment"])
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
