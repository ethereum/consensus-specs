from eth2spec.test.context import (
    single_phase,
    spec_test,
    with_deneb_and_later,
    with_presets,
)
from eth2spec.test.helpers.constants import (
    MAINNET,
)
from eth2spec.test.helpers.forks import is_post_eip7732


@with_deneb_and_later
@spec_test
@single_phase
def test_networking(spec):
    for i in range(spec.MAX_BLOB_COMMITMENTS_PER_BLOCK):
        if is_post_eip7732(spec):
            inner_gindex = spec.get_generalized_index(
                spec.List[spec.KZGCommitment, spec.MAX_BLOB_COMMITMENTS_PER_BLOCK], i
            )
            outer_gindex = spec.get_generalized_index(
                spec.BeaconBlockBody,
                "signed_execution_payload_header",
                "message",
                "blob_kzg_commitments_root",
            )
            gindex = spec.concat_generalized_indices(outer_gindex, inner_gindex)
            assert spec.floorlog2(gindex) == spec.KZG_COMMITMENT_INCLUSION_PROOF_DEPTH_EIP7732
        else:
            gindex = spec.get_generalized_index(spec.BeaconBlockBody, "blob_kzg_commitments", i)
            assert spec.floorlog2(gindex) == spec.KZG_COMMITMENT_INCLUSION_PROOF_DEPTH


@with_deneb_and_later
@spec_test
@single_phase
@with_presets([MAINNET], reason="to have fork epoch number")
def test_blob_schedule(spec):
    for entry in spec.config.BLOB_SCHEDULE:
        # Check that all epochs are post-Deneb
        assert entry["EPOCH"] >= spec.config.DENEB_FORK_EPOCH
        # Check that all blob counts are less than the limit
        assert entry["MAX_BLOBS_PER_BLOCK"] <= spec.MAX_BLOB_COMMITMENTS_PER_BLOCK
