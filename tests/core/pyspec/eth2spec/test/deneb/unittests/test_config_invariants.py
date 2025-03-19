from eth2spec.test.context import (
    single_phase,
    spec_test,
    with_deneb_and_later,
)


def latest_kzg_commitment_inclusion_proof_depth(spec):
    if hasattr(spec, 'KZG_COMMITMENT_INCLUSION_PROOF_DEPTH_ELECTRA'):
        return spec.KZG_COMMITMENT_INCLUSION_PROOF_DEPTH_ELECTRA
    return spec.KZG_COMMITMENT_INCLUSION_PROOF_DEPTH


@with_deneb_and_later
@spec_test
@single_phase
def test_length(spec):
    assert spec.config.MAX_BLOBS_PER_BLOCK < spec.MAX_BLOB_COMMITMENTS_PER_BLOCK


@with_deneb_and_later
@spec_test
@single_phase
def test_networking(spec):
    assert spec.config.MAX_BLOBS_PER_BLOCK < spec.MAX_BLOB_COMMITMENTS_PER_BLOCK
    assert (
        spec.config.MAX_REQUEST_BLOB_SIDECARS ==
        spec.config.MAX_REQUEST_BLOCKS_DENEB * spec.config.MAX_BLOBS_PER_BLOCK
    )
    # Start with the same size, but `BLOB_SIDECAR_SUBNET_COUNT` could potentially increase later.
    assert spec.config.BLOB_SIDECAR_SUBNET_COUNT == spec.config.MAX_BLOBS_PER_BLOCK
    for i in range(spec.MAX_BLOB_COMMITMENTS_PER_BLOCK):
        gindex = spec.get_generalized_index(spec.BeaconBlockBody, 'blob_kzg_commitments', i)
        assert spec.floorlog2(gindex) == latest_kzg_commitment_inclusion_proof_depth(spec)
