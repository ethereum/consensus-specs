from eth_utils import encode_hex

from eth_consensus_specs.test.context import (
    expect_assertion_error,
    only_generator,
    single_phase,
    spec_test,
    with_phases,
)
from eth_consensus_specs.test.helpers.constants import FULU
from eth_consensus_specs.test.utils.kzg_tests import (
    encode_hex_list,
    INVALID_BLOBS,
    VALID_BLOBS,
)
from tests.infra.manifest import manifest
from tests.infra.template_test import template_test


@template_test
def _compute_cells_and_kzg_proofs_case_valid(blob_index):
    blob = VALID_BLOBS[blob_index]

    @manifest(preset_name="general", suite_name="kzg-mainnet")
    @only_generator("too slow")
    @with_phases([FULU])
    @spec_test
    @single_phase
    def the_test(spec):
        cells, proofs = spec.compute_cells_and_kzg_proofs(blob)

        yield (
            "data",
            "data",
            {
                "input": {
                    "blob": encode_hex(blob),
                },
                "output": (encode_hex_list(cells), encode_hex_list(proofs)),
            },
        )

    return (the_test, f"test_compute_cells_and_kzg_proofs_case_valid_{blob_index}")


for blob_index in range(len(VALID_BLOBS)):
    _compute_cells_and_kzg_proofs_case_valid(blob_index)


@template_test
def _compute_cells_and_kzg_proofs_case_invalid_blob(blob_index):
    blob = INVALID_BLOBS[blob_index]

    @manifest(preset_name="general", suite_name="kzg-mainnet")
    @only_generator("too slow")
    @with_phases([FULU])
    @spec_test
    @single_phase
    def the_test(spec):
        expect_assertion_error(lambda: spec.compute_cells_and_kzg_proofs(blob))

        yield (
            "data",
            "data",
            {
                "input": {
                    "blob": encode_hex(blob),
                },
                "output": None,
            },
        )

    return (the_test, f"test_compute_cells_and_kzg_proofs_case_invalid_blob_{blob_index}")


for blob_index in range(len(INVALID_BLOBS)):
    _compute_cells_and_kzg_proofs_case_invalid_blob(blob_index)
