from eth_consensus_specs.test.context import (
    DENEB,
    ELECTRA,
    GLOAS,
    single_phase,
    spec_test,
    with_all_phases_from_to,
)


@with_all_phases_from_to(DENEB, ELECTRA)
@spec_test
@single_phase
def test_length(spec):
    assert spec.config.MAX_BLOBS_PER_BLOCK < spec.MAX_BLOB_COMMITMENTS_PER_BLOCK


@with_all_phases_from_to(DENEB, GLOAS)
@spec_test
@single_phase
def test_networking(spec):
    for i in range(spec.MAX_BLOB_COMMITMENTS_PER_BLOCK):
        gindex = spec.get_generalized_index(spec.BeaconBlockBody, "blob_kzg_commitments", i)
        assert spec.floorlog2(gindex) == spec.KZG_COMMITMENT_INCLUSION_PROOF_DEPTH
