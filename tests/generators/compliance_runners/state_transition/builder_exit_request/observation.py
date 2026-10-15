"""Observe builder-exit inputs and the exit effect from concrete vectors."""

from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import NA


def observe_attributes(ctx):
    spec, pre, request = ctx.spec, ctx.pre, ctx.operation
    pubkeys = [builder.pubkey for builder in pre.builders]
    found = request.pubkey in pubkeys
    result = {
        "observed_builder_pubkey_found": found,
        "observed_finalized_epoch": int(pre.finalized_checkpoint.epoch),
        "observed_builder_active": False,
        "observed_builder_has_pending_balance": False,
        "observed_exit_initiated": False,
    }
    if found:
        index = spec.BuilderIndex(pubkeys.index(request.pubkey))
        builder = pre.builders[index]
        result.update(
            observed_builder_deposit_epoch=int(builder.deposit_epoch),
            observed_builder_withdrawable_epoch_set=bool(
                builder.withdrawable_epoch != spec.FAR_FUTURE_EPOCH
            ),
            observed_builder_has_pending_withdrawal=any(
                withdrawal.builder_index == index and int(withdrawal.amount) > 0
                for withdrawal in pre.builder_pending_withdrawals
            ),
            observed_builder_has_pending_payment=any(
                payment.withdrawal.builder_index == index and int(payment.withdrawal.amount) > 0
                for payment in pre.builder_pending_payments
            ),
            observed_source_address_matches=bool(
                builder.execution_address == request.source_address
            ),
            observed_builder_active=bool(spec.is_active_builder(pre, index)),
            observed_builder_has_pending_balance=bool(
                spec.get_pending_balance_to_withdraw_for_builder(pre, index) != 0
            ),
            observed_exit_initiated=bool(
                ctx.post is not None
                and builder.withdrawable_epoch == spec.FAR_FUTURE_EPOCH
                and ctx.post.builders[index].withdrawable_epoch != spec.FAR_FUTURE_EPOCH
            ),
        )
    else:
        result.update(
            dict.fromkeys(
                (
                    "observed_builder_deposit_epoch",
                    "observed_builder_withdrawable_epoch_set",
                    "observed_builder_has_pending_withdrawal",
                    "observed_builder_has_pending_payment",
                    "observed_source_address_matches",
                ),
                NA,
            )
        )
    return result
