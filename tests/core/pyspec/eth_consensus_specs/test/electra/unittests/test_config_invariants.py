from eth_consensus_specs.test.context import (
    single_phase,
    spec_test,
    with_electra_and_later,
)


@with_electra_and_later
@spec_test
@single_phase
def test_processing_pending_partial_withdrawals(spec):
    assert spec.MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP < spec.MAX_WITHDRAWALS_PER_PAYLOAD


@with_electra_and_later
@spec_test
@single_phase
def test_networking(spec):
    assert spec.config.MAX_BLOBS_PER_BLOCK_ELECTRA <= spec.MAX_BLOB_COMMITMENTS_PER_BLOCK
    # Start with the same size, but `BLOB_SIDECAR_SUBNET_COUNT` could potentially increase later.
    assert spec.config.BLOB_SIDECAR_SUBNET_COUNT_ELECTRA == spec.config.MAX_BLOBS_PER_BLOCK_ELECTRA
