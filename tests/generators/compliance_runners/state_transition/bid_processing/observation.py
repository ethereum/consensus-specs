"""Observe bid predicates from the operation and pre-state, without claims."""

from tests.generators.compliance_runners.state_transition.validation_helpers import bls_enabled


def observe_attributes(ctx):
    spec, pre, signed = ctx.spec, ctx.pre, ctx.operation
    bid = signed.message
    index = int(bid.builder_index)
    is_self = index == spec.BUILDER_INDEX_SELF_BUILD
    found = not is_self and index < len(pre.builders)
    builder = pre.builders[index] if found else None
    epoch = spec.get_current_epoch(pre)
    with bls_enabled():
        if signed.signature == spec.bls.G2_POINT_AT_INFINITY:
            signature = "INF"
        elif found and spec.verify_execution_payload_bid_signature(pre, signed):
            signature = "VALID"
        else:
            signature = "INVALID"
    past = pre.slot > spec.GENESIS_SLOT
    return {
        "observed_builder_type": "SELF" if is_self else "EXTERNAL" if found else "NON_EXISTING",
        "observed_bid_signature": signature,
        "observed_bid_value": int(bid.value),
        "observed_builder_balance": int(builder.balance) if found else 0,
        "observed_pending_balance": int(
            spec.get_pending_balance_to_withdraw_for_builder(pre, bid.builder_index)
        )
        if found
        else 0,
        "observed_current_epoch": int(epoch),
        "observed_deposit_epoch": int(builder.deposit_epoch) if found else 0,
        "observed_withdrawable_epoch": int(builder.withdrawable_epoch) if found else 0,
        "observed_finalized_epoch": int(pre.finalized_checkpoint.epoch),
        "observed_payload_builder_version": bool(
            found and builder.version == spec.PAYLOAD_BUILDER_VERSION
        ),
        "observed_has_pending_payments": bool(
            found
            and any(
                p.withdrawal.builder_index == index and p.withdrawal.amount > 0
                for p in pre.builder_pending_payments
            )
        ),
        "observed_has_pending_withdrawals": bool(
            found
            and any(
                w.builder_index == index and w.amount > 0 for w in pre.builder_pending_withdrawals
            )
        ),
        "observed_kzg_commitment_count": len(bid.blob_kzg_commitments),
        "observed_max_blobs": int(spec.get_blob_parameters(epoch).max_blobs_per_block),
        "observed_state_slot": int(pre.slot),
        "observed_bid_slot": int(bid.slot),
        "observed_parent_block_hash_match": bool(bid.parent_block_hash == pre.latest_block_hash),
        "observed_parent_block_root_match": bool(
            past
            and bid.parent_block_root
            == spec.get_block_root_at_slot(pre, spec.Slot(int(pre.slot) - 1))
        ),
        "observed_prev_randao_match": bool(bid.prev_randao == spec.get_randao_mix(pre, epoch)),
    }
