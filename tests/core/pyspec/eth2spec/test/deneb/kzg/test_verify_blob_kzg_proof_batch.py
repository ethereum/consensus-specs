###############################################################################
# Test cases for verify_blob_kzg_proof_batch
###############################################################################

from eth2spec.test.context import only_generator, single_phase, spec_test, with_phases
from eth2spec.test.helpers.constants import DENEB
from eth2spec.test.utils.kzg_tests import (
    BLOB_RANDOM_VALID1,
    bls_add_one,
    encode_hex_list,
    INVALID_BLOBS,
    INVALID_G1_POINTS,
    VALID_BLOBS,
)
from tests.infra.manifest import manifest
from tests.infra.template_test import template_test


@template_test
def _verify_blob_kzg_proof_batch_case(length):
    @manifest(preset_name="general", suite_name="kzg-mainnet")
    @only_generator("too slow")
    @with_phases([DENEB])
    @spec_test
    @single_phase
    def the_test(spec):
        blobs = VALID_BLOBS[:length]
        commitments = [spec.blob_to_kzg_commitment(blob) for blob in blobs]
        proofs = [spec.compute_blob_kzg_proof(blob, commitments[i]) for i, blob in enumerate(blobs)]

        assert spec.verify_blob_kzg_proof_batch(blobs, commitments, proofs)

        yield (
            "data",
            "data",
            {
                "input": {
                    "blobs": encode_hex_list(blobs),
                    "commitments": encode_hex_list(commitments),
                    "proofs": encode_hex_list(proofs),
                },
                "output": True,
            },
        )

    return (the_test, f"test_verify_blob_kzg_proof_batch_case_{length}")


for length in range(len(VALID_BLOBS)):
    _verify_blob_kzg_proof_batch_case(length)


@manifest(preset_name="general", suite_name="kzg-mainnet")
@only_generator("too slow")
@with_phases([DENEB])
@spec_test
@single_phase
def test_verify_blob_kzg_proof_batch_case_incorrect_proof_add_one(spec):
    blobs = VALID_BLOBS
    commitments = [spec.blob_to_kzg_commitment(blob) for blob in blobs]
    proofs = [spec.compute_blob_kzg_proof(blob, commitments[i]) for i, blob in enumerate(blobs)]
    # Add one to the first proof, so that it's incorrect
    proofs = [bls_add_one(proofs[0])] + proofs[1:]

    assert not spec.verify_blob_kzg_proof_batch(blobs, commitments, proofs)

    yield (
        "data",
        "data",
        {
            "input": {
                "blobs": encode_hex_list(blobs),
                "commitments": encode_hex_list(commitments),
                "proofs": encode_hex_list(proofs),
            },
            "output": False,
        },
    )


@manifest(preset_name="general", suite_name="kzg-mainnet")
@only_generator("too slow")
@with_phases([DENEB])
@spec_test
@single_phase
def test_verify_blob_kzg_proof_batch_case_incorrect_proof_point_at_infinity(spec):
    blobs = [BLOB_RANDOM_VALID1]
    commitments = [spec.blob_to_kzg_commitment(blob) for blob in blobs]
    # Use the wrong proof
    proofs = [spec.G1_POINT_AT_INFINITY]

    assert not spec.verify_blob_kzg_proof_batch(blobs, commitments, proofs)

    yield (
        "data",
        "data",
        {
            "input": {
                "blobs": encode_hex_list(blobs),
                "commitments": encode_hex_list(commitments),
                "proofs": encode_hex_list(proofs),
            },
            "output": False,
        },
    )


@template_test
def _verify_blob_kzg_proof_batch_case_invalid_blob(blob_index):
    invalid_blob = INVALID_BLOBS[blob_index]

    @manifest(preset_name="general", suite_name="kzg-mainnet")
    @only_generator("too slow")
    @with_phases([DENEB])
    @spec_test
    @single_phase
    def the_test(spec):
        blobs = VALID_BLOBS
        commitments = [spec.blob_to_kzg_commitment(blob) for blob in blobs]
        proofs = [spec.compute_blob_kzg_proof(blob, commitments[i]) for i, blob in enumerate(blobs)]
        # Insert an invalid blob into the middle
        blobs = VALID_BLOBS[:4] + [invalid_blob] + VALID_BLOBS[5:]

        try:
            spec.verify_blob_kzg_proof_batch(blobs, commitments, proofs)
            assert False, "Expected exception"
        except Exception:
            pass  # Expected exception

        yield (
            "data",
            "data",
            {
                "input": {
                    "blobs": encode_hex_list(blobs),
                    "commitments": encode_hex_list(commitments),
                    "proofs": encode_hex_list(proofs),
                },
                "output": None,
            },
        )

    return (the_test, f"test_verify_blob_kzg_proof_batch_case_invalid_blob_{blob_index}")


for blob_index in range(len(INVALID_BLOBS)):
    _verify_blob_kzg_proof_batch_case_invalid_blob(blob_index)


@template_test
def _verify_blob_kzg_proof_batch_case_invalid_commitment(commitment_index):
    invalid_commitment = INVALID_G1_POINTS[commitment_index]

    @manifest(preset_name="general", suite_name="kzg-mainnet")
    @only_generator("too slow")
    @with_phases([DENEB])
    @spec_test
    @single_phase
    def the_test(spec):
        blobs = VALID_BLOBS
        commitments = [spec.blob_to_kzg_commitment(blob) for blob in blobs]
        proofs = [spec.compute_blob_kzg_proof(blob, commitments[i]) for i, blob in enumerate(blobs)]
        # Replace first commitment with an invalid commitment
        commitments = [invalid_commitment] + commitments[1:]

        try:
            spec.verify_blob_kzg_proof_batch(blobs, commitments, proofs)
            assert False, "Expected exception"
        except Exception:
            pass  # Expected exception

        yield (
            "data",
            "data",
            {
                "input": {
                    "blobs": encode_hex_list(blobs),
                    "commitments": encode_hex_list(commitments),
                    "proofs": encode_hex_list(proofs),
                },
                "output": None,
            },
        )

    return (
        the_test,
        f"test_verify_blob_kzg_proof_batch_case_invalid_commitment_{commitment_index}",
    )


for commitment_index in range(len(INVALID_G1_POINTS)):
    _verify_blob_kzg_proof_batch_case_invalid_commitment(commitment_index)


@template_test
def _verify_blob_kzg_proof_batch_case_invalid_proof(proof_index):
    invalid_proof = INVALID_G1_POINTS[proof_index]

    @manifest(preset_name="general", suite_name="kzg-mainnet")
    @only_generator("too slow")
    @with_phases([DENEB])
    @spec_test
    @single_phase
    def the_test(spec):
        blobs = VALID_BLOBS
        commitments = [spec.blob_to_kzg_commitment(blob) for blob in blobs]
        proofs = [spec.compute_blob_kzg_proof(blob, commitments[i]) for i, blob in enumerate(blobs)]
        # Replace first proof with an invalid proof
        proofs = [invalid_proof] + proofs[1:]

        try:
            spec.verify_blob_kzg_proof_batch(blobs, commitments, proofs)
            assert False, "Expected exception"
        except Exception:
            pass  # Expected exception

        yield (
            "data",
            "data",
            {
                "input": {
                    "blobs": encode_hex_list(blobs),
                    "commitments": encode_hex_list(commitments),
                    "proofs": encode_hex_list(proofs),
                },
                "output": None,
            },
        )

    return (the_test, f"test_verify_blob_kzg_proof_batch_case_invalid_proof_{proof_index}")


for proof_index in range(len(INVALID_G1_POINTS)):
    _verify_blob_kzg_proof_batch_case_invalid_proof(proof_index)


@manifest(preset_name="general", suite_name="kzg-mainnet")
@only_generator("too slow")
@with_phases([DENEB])
@spec_test
@single_phase
def test_verify_blob_kzg_proof_batch_case_blob_length_different(spec):
    blobs = VALID_BLOBS
    commitments = [spec.blob_to_kzg_commitment(blob) for blob in blobs]
    proofs = [spec.compute_blob_kzg_proof(blob, commitments[i]) for i, blob in enumerate(blobs)]
    # Delete the last blob
    blobs = blobs[:-1]

    try:
        spec.verify_blob_kzg_proof_batch(blobs, commitments, proofs)
        assert False, "Expected exception"
    except Exception:
        pass  # Expected exception

    yield (
        "data",
        "data",
        {
            "input": {
                "blobs": encode_hex_list(blobs),
                "commitments": encode_hex_list(commitments),
                "proofs": encode_hex_list(proofs),
            },
            "output": None,
        },
    )


@manifest(preset_name="general", suite_name="kzg-mainnet")
@only_generator("too slow")
@with_phases([DENEB])
@spec_test
@single_phase
def test_verify_blob_kzg_proof_batch_case_commitment_length_different(spec):
    blobs = VALID_BLOBS
    commitments = [spec.blob_to_kzg_commitment(blob) for blob in blobs]
    proofs = [spec.compute_blob_kzg_proof(blob, commitments[i]) for i, blob in enumerate(blobs)]
    # Delete the last commitment
    commitments = commitments[:-1]

    try:
        spec.verify_blob_kzg_proof_batch(blobs, commitments, proofs)
        assert False, "Expected exception"
    except Exception:
        pass  # Expected exception

    yield (
        "data",
        "data",
        {
            "input": {
                "blobs": encode_hex_list(blobs),
                "commitments": encode_hex_list(commitments),
                "proofs": encode_hex_list(proofs),
            },
            "output": None,
        },
    )


@manifest(preset_name="general", suite_name="kzg-mainnet")
@only_generator("too slow")
@with_phases([DENEB])
@spec_test
@single_phase
def test_verify_blob_kzg_proof_batch_case_proof_length_different(spec):
    blobs = VALID_BLOBS
    commitments = [spec.blob_to_kzg_commitment(blob) for blob in blobs]
    proofs = [spec.compute_blob_kzg_proof(blob, commitments[i]) for i, blob in enumerate(blobs)]
    # Delete the last proof
    proofs = proofs[:-1]

    try:
        spec.verify_blob_kzg_proof_batch(blobs, commitments, proofs)
        assert False, "Expected exception"
    except Exception:
        pass  # Expected exception

    yield (
        "data",
        "data",
        {
            "input": {
                "blobs": encode_hex_list(blobs),
                "commitments": encode_hex_list(commitments),
                "proofs": encode_hex_list(proofs),
            },
            "output": None,
        },
    )
