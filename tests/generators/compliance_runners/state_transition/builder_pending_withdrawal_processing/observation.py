"""Observe one pending builder withdrawal and its concrete balance/queue effects."""


def observe_attributes(ctx):
    spec, pre = ctx.spec, ctx.pre
    withdrawal = pre.builder_pending_withdrawals[0]
    index = int(withdrawal.builder_index)
    builder = pre.builders[index]
    amount, balance = int(withdrawal.amount), int(builder.balance)
    values = {
        "parent_hash_matches": bool(
            pre.latest_block_hash == pre.latest_execution_payload_bid.block_hash
        ),
        "pending_amount": amount,
        "builder_balance": balance,
        "version_valid": bool(builder.version == spec.PAYLOAD_BUILDER_VERSION),
        "current_epoch": int(spec.get_current_epoch(pre)),
        "deposit_epoch": int(builder.deposit_epoch),
        "withdrawable_epoch": int(builder.withdrawable_epoch),
        "finalized_epoch": int(pre.finalized_checkpoint.epoch),
        "withdrawable_epoch_set": bool(builder.withdrawable_epoch != spec.FAR_FUTURE_EPOCH),
        "has_pending_payments": any(
            payment.withdrawal.builder_index == index and int(payment.withdrawal.amount) > 0
            for payment in pre.builder_pending_payments
        ),
        "has_pending_withdrawals": any(
            entry.builder_index == index and int(entry.amount) > 0
            for entry in pre.builder_pending_withdrawals
        ),
        "balance_applied": bool(
            ctx.post is not None
            and int(ctx.post.builders[index].balance) == max(0, balance - amount)
        ),
        "queue_consumed": bool(ctx.post is not None and not ctx.post.builder_pending_withdrawals),
    }

    return {f"observed_{name}": value for name, value in values.items()}
