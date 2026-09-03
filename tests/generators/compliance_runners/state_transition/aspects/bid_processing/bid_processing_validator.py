from tests.generators.compliance_runners.state_transition.aspects.base import (
    _to_bool,
    _to_cmp,
    BuilderType,
    SignatureType,
    validator,
)
from tests.generators.compliance_runners.state_transition.aspects.bid_processing.bid_processing import (
    ExecutionPayloadBidProcessing,
)
from tests.generators.compliance_runners.state_transition.aspects.builder.builder_validator import (
    builder_validator,
)


@validator
def bid_processing_validator(
    spec,
    beacon_state,
    solution: ExecutionPayloadBidProcessing,
    builder_index: int,
    signed_execution_payload_bid,
) -> bool:
    """
    - `builder_index` is an index in `beacon_state.builders` list corresponding
    to the instance of the builder materialized from the `solution.builder`.
    - `signed_execution_payload_bid` is an instance of SignedExecutionPayloadBid
    materialized from the `solution`.
    """
    # Validate builder (self-build: builder_validator returns True immediately)
    if not builder_validator(spec, beacon_state, solution.builder, builder_index):
        return False

    # Materializer must start from at least Slot(1)
    if beacon_state.slot < spec.Slot(1):
        return False

    bid = signed_execution_payload_bid.message
    cmp_bid_value_zero = _to_cmp(int(bid.value), 0)

    if solution.builder_type == BuilderType.SELF:
        cmp_builder_balance_to_bid_value_plus_min_balance = _to_cmp(0, int(bid.value))
    else:
        builder_balance = beacon_state.builders[builder_index].balance
        pending_withdrawals_amount = sum(
            withdrawal.amount
            for withdrawal in beacon_state.builder_pending_withdrawals
            if withdrawal.builder_index == builder_index
        ) + sum(
            payment.withdrawal.amount
            for payment in beacon_state.builder_pending_payments
            if payment.withdrawal.builder_index == builder_index
        )
        min_balance = spec.MIN_DEPOSIT_AMOUNT + pending_withdrawals_amount
        cmp_builder_balance_to_bid_value_plus_min_balance = _to_cmp(
            int(builder_balance), int(bid.value + min_balance)
        )

    cmp_len_kzg_commitments_max_blobs = _to_cmp(
        len(bid.blob_kzg_commitments),
        spec.get_blob_parameters(spec.get_current_epoch(beacon_state)).max_blobs_per_block,
    )
    cmp_state_slot_bid_slot = _to_cmp(int(beacon_state.slot), int(bid.slot))
    parent_block_hash_match = _to_bool(bid.parent_block_hash == beacon_state.latest_block_hash)
    parent_block_root_match = _to_bool(
        bid.parent_block_root
        == spec.get_block_root_at_slot(beacon_state, spec.Slot(int(beacon_state.slot) - 1))
    )
    prev_randao_match = _to_bool(
        bid.prev_randao == spec.get_randao_mix(beacon_state, spec.get_current_epoch(beacon_state))
    )

    if signed_execution_payload_bid.signature == spec.bls.G2_POINT_AT_INFINITY:
        bid_signature = SignatureType.INF
    elif solution.builder_type == BuilderType.SELF:
        bid_signature = SignatureType.INVALID
    elif spec.verify_execution_payload_bid_signature(beacon_state, signed_execution_payload_bid):
        bid_signature = SignatureType.VALID
    else:
        bid_signature = SignatureType.INVALID

    materialized_solution = ExecutionPayloadBidProcessing(
        builder_type=solution.builder_type,
        builder=solution.builder,
        cmp_bid_value_zero=cmp_bid_value_zero,
        bid_signature=bid_signature,
        cmp_builder_balance_to_bid_value_plus_min_balance=cmp_builder_balance_to_bid_value_plus_min_balance,
        cmp_len_kzg_commitments_max_blobs=cmp_len_kzg_commitments_max_blobs,
        cmp_state_slot_bid_slot=cmp_state_slot_bid_slot,
        parent_block_hash_match=parent_block_hash_match,
        parent_block_root_match=parent_block_root_match,
        prev_randao_match=prev_randao_match,
    )

    return materialized_solution == solution
