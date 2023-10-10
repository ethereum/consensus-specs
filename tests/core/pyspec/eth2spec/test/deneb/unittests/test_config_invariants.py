from eth2spec.test.context import (
    single_phase,
    spec_test,
    with_deneb_and_later,
)


@with_deneb_and_later
@spec_test
@single_phase
def test_length(spec):
    assert spec.MAX_BLOBS_PER_BLOCK < spec.MAX_BLOB_COMMITMENTS_PER_BLOCK


@with_deneb_and_later
@spec_test
@single_phase
def test_networking(spec):
    assert spec.MAX_BLOBS_PER_BLOCK < spec.MAX_BLOB_COMMITMENTS_PER_BLOCK
    assert spec.config.MAX_REQUEST_BLOB_SIDECARS == spec.config.MAX_REQUEST_BLOCKS_DENEB * spec.MAX_BLOBS_PER_BLOCK
    # Start with the same size, but `BLOB_SIDECAR_SUBNET_COUNT` could potentially increase later.
    assert spec.config.BLOB_SIDECAR_SUBNET_COUNT == spec.MAX_BLOBS_PER_BLOCK
