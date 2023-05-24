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
