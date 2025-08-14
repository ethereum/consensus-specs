from eth2spec.test.context import (
    single_phase,
    spec_test,
    with_eip7732_and_later,
)


@with_eip7732_and_later
@spec_test
@single_phase
def test_networking(spec):
    gindex = spec.get_generalized_index(
        spec.BeaconBlockBody,
        "signed_execution_payload_header",
        "message",
        "blob_kzg_commitments_root",
    )
    assert spec.floorlog2(gindex) == spec.KZG_COMMITMENTS_INCLUSION_PROOF_DEPTH_GLOAS
