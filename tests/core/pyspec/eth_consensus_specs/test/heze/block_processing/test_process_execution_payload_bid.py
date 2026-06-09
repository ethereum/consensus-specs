from eth_consensus_specs.test.context import (
    always_bls,
    spec_state_test,
    with_heze_and_later,
)
from eth_consensus_specs.test.gloas.block_processing.test_process_execution_payload_bid import (
    prepare_block_with_non_proposer_builder,
)
from eth_consensus_specs.test.helpers.execution_payload_bid import (
    prepare_signed_execution_payload_bid,
    run_execution_payload_bid_processing,
)
from eth_consensus_specs.test.helpers.state import next_epoch_with_full_participation


@with_heze_and_later
@spec_state_test
@always_bls
def test_process_execution_payload_bid_valid_builder_with_non_default_inclusion_list_bits(
    spec, state
):
    """
    Test valid builder bid with non-default ``inclusion_list_bits``.
    """
    next_epoch_with_full_participation(spec, state)
    next_epoch_with_full_participation(spec, state)
    next_epoch_with_full_participation(spec, state)
    next_epoch_with_full_participation(spec, state)
    assert state.finalized_checkpoint.epoch == 2

    block, builder_index = prepare_block_with_non_proposer_builder(spec, state)
    assert spec.is_active_builder(state, builder_index) is True

    inclusion_list_bits = spec.Bitvector[spec.INCLUSION_LIST_COMMITTEE_SIZE]()
    inclusion_list_bits[0] = True

    signed_bid = prepare_signed_execution_payload_bid(
        spec,
        state,
        builder_index=builder_index,
        value=spec.Gwei(1000000),
        slot=block.slot,
        parent_block_root=block.parent_root,
        inclusion_list_bits=inclusion_list_bits,
    )

    block.body.signed_execution_payload_bid = signed_bid

    yield from run_execution_payload_bid_processing(spec, state, block)

    assert state.latest_execution_payload_bid == signed_bid.message
