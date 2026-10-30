"""Observe request counts, parent delivery, payment selection, and post-state effects."""

REQUEST_FIELDS = ("withdrawals", "consolidations", "builder_deposits", "builder_exits")


def observe_attributes(ctx):
    spec, pre, block, post = ctx.spec, ctx.pre, ctx.operation, ctx.post
    parent_bid = pre.latest_execution_payload_bid
    bid = block.body.signed_execution_payload_bid.message
    requests = block.body.parent_execution_requests
    parent_slot = int(pre.latest_block_header.slot)
    parent_epoch = int(spec.compute_epoch_at_slot(parent_slot))
    current_epoch = int(spec.get_current_epoch(pre))
    payment_index = None
    if parent_epoch == current_epoch:
        settlement = "CURRENT_EPOCH"
        payment_index = int(spec.SLOTS_PER_EPOCH) + parent_slot % int(spec.SLOTS_PER_EPOCH)
    elif parent_epoch == int(spec.get_previous_epoch(pre)):
        settlement = "PREVIOUS_EPOCH"
        payment_index = parent_slot % int(spec.SLOTS_PER_EPOCH)
    else:
        settlement = "EVICTED"
    payment_value = int(
        parent_bid.value
        if payment_index is None
        else pre.builder_pending_payments[payment_index].withdrawal.amount
    )
    values = {f"observed_{field}_count": len(getattr(requests, field)) for field in REQUEST_FIELDS}
    values.update(
        observed_parent_payload_revealed=bool(bid.parent_block_hash == parent_bid.block_hash),
        observed_requests_empty=bool(requests == spec.ExecutionRequests()),
        observed_requests_root_matches=bool(
            spec.hash_tree_root(requests) == parent_bid.execution_requests_root
        ),
        observed_deposit_count=len(requests.deposits),
        observed_payment_settlement=settlement,
        observed_payment_value=payment_value,
        observed_accepted=post is not None,
        observed_state_effected=bool(
            post is not None and post.hash_tree_root() != pre.hash_tree_root()
        ),
        observed_payment_withdrawal_appended=bool(
            post is not None
            and len(post.builder_pending_withdrawals) > len(pre.builder_pending_withdrawals)
        ),
        observed_payment_slot_cleared=bool(
            post is not None
            and payment_index is not None
            and pre.builder_pending_payments[payment_index] != spec.BuilderPendingPayment()
            and post.builder_pending_payments[payment_index] == spec.BuilderPendingPayment()
        ),
    )
    return values
