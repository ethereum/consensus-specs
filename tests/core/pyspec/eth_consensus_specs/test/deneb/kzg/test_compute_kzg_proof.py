###############################################################################
# Test cases for compute_kzg_proof
###############################################################################

from eth_utils import encode_hex

from eth_consensus_specs.test.context import only_generator, single_phase, spec_test, with_phases
from eth_consensus_specs.test.helpers.constants import DENEB
from eth_consensus_specs.test.utils.kzg_tests import (
    INVALID_BLOBS,
    INVALID_FIELD_ELEMENTS,
    VALID_BLOBS,
    VALID_FIELD_ELEMENTS,
)
from tests.infra.manifest import manifest
from tests.infra.template_test import template_test


def _run_compute_kzg_proof_test(spec, blob, z, valid: bool):
    try:
        proof, y = spec.compute_kzg_proof(blob, z)
        result = (encode_hex(proof), encode_hex(y))
    except Exception:
        result = None

    assert (result is not None) == valid

    yield (
        "data",
        "data",
        {
            "input": {
                "blob": encode_hex(blob),
                "z": encode_hex(z),
            },
            "output": result,
        },
    )


@template_test
def _compute_kzg_proof_case_valid(blob_index, z_index):
    blob = VALID_BLOBS[blob_index]
    z = VALID_FIELD_ELEMENTS[z_index]

    @manifest(preset_name="general", suite_name="kzg-mainnet")
    @only_generator("too slow")
    @with_phases([DENEB])
    @spec_test
    @single_phase
    def the_test(spec):
        yield from _run_compute_kzg_proof_test(spec, blob, z, valid=True)

    return (the_test, f"test_compute_kzg_proof_case_valid_blob_{blob_index}_{z_index}")


for blob_index in range(len(VALID_BLOBS)):
    for z_index in range(len(VALID_FIELD_ELEMENTS)):
        _compute_kzg_proof_case_valid(blob_index, z_index)


@template_test
def _compute_kzg_proof_case_invalid_blob(blob_index):
    blob = INVALID_BLOBS[blob_index]
    z = VALID_FIELD_ELEMENTS[0]

    @manifest(preset_name="general", suite_name="kzg-mainnet")
    @only_generator("too slow")
    @with_phases([DENEB])
    @spec_test
    @single_phase
    def the_test(spec):
        yield from _run_compute_kzg_proof_test(spec, blob, z, valid=False)

    return (the_test, f"test_compute_kzg_proof_case_invalid_blob_{blob_index}")


for blob_index in range(len(INVALID_BLOBS)):
    _compute_kzg_proof_case_invalid_blob(blob_index)


@template_test
def _compute_kzg_proof_case_invalid_z(z_index):
    blob = VALID_BLOBS[4]
    z = INVALID_FIELD_ELEMENTS[z_index]

    @manifest(preset_name="general", suite_name="kzg-mainnet")
    @only_generator("too slow")
    @with_phases([DENEB])
    @spec_test
    @single_phase
    def the_test(spec):
        yield from _run_compute_kzg_proof_test(spec, blob, z, valid=False)

    return (the_test, f"test_compute_kzg_proof_case_invalid_z_{z_index}")


for z_index in range(len(INVALID_FIELD_ELEMENTS)):
    _compute_kzg_proof_case_invalid_z(z_index)
