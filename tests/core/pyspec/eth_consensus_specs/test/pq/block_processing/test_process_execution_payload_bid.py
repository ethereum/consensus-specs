from eth_consensus_specs.test.context import (
    spec_state_test,
    with_pq_and_later,
)
from eth_consensus_specs.test.helpers.blob import (
    get_sample_blob_tx,
)
from eth_consensus_specs.test.helpers.block import build_empty_block_for_next_slot
from eth_consensus_specs.test.helpers.execution_payload_bid import (
    prepare_signed_execution_payload_bid,
    run_execution_payload_bid_processing,
)


@with_pq_and_later
@spec_state_test
def test_process_execution_payload_bid_blobs_disabled(spec, state):
    """
    Test that a bid with a blob kzg commitment is rejected.
    """
    block = build_empty_block_for_next_slot(spec, state)
    _, _, blob_kzg_commitments, _ = get_sample_blob_tx(spec, blob_count=1)

    signed_bid = prepare_signed_execution_payload_bid(
        spec,
        state,
        builder_index=spec.BUILDER_INDEX_SELF_BUILD,
        slot=block.slot,
        parent_block_root=block.parent_root,
        blob_kzg_commitments=spec.BlobKZGCommitments(data=blob_kzg_commitments),
    )

    block.body.signed_execution_payload_bid = signed_bid

    yield from run_execution_payload_bid_processing(spec, state, block, valid=False)
