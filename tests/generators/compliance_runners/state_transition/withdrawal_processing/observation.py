"""Observe withdrawal sources and sweep boundaries from the decoded pre-state."""


def observe_attributes(ctx):
    spec, pre = ctx.spec, ctx.pre
    epoch = spec.get_current_epoch(pre)
    expected = spec.get_expected_withdrawals(pre)
    processed_builders = int(expected.processed_builder_withdrawals_count)
    # Each builder queue entry emits one withdrawal. Remaining builder-indexed
    # outputs belong to the builder sweep, not its scanned-position count.
    swept_builders = (
        sum(spec.is_builder_index(w.validator_index) for w in expected.withdrawals)
        - processed_builders
    )
    return {
        "observed_parent_hash_matches": bool(
            pre.latest_block_hash == pre.latest_execution_payload_bid.block_hash
        ),
        "observed_builder_pending_count": len(pre.builder_pending_withdrawals),
        "observed_processed_builder_count": processed_builders,
        "observed_validator_pending_count": len(pre.pending_partial_withdrawals),
        "observed_eligible_validator_pending": any(
            w.withdrawable_epoch <= epoch for w in pre.pending_partial_withdrawals
        ),
        "observed_processed_partial_count": int(expected.processed_partial_withdrawals_count),
        "observed_builder_count": len(pre.builders),
        "observed_eligible_builder_count": sum(
            b.withdrawable_epoch <= epoch and b.balance > 0 for b in pre.builders
        ),
        "observed_swept_builder_count": swept_builders,
        "observed_next_builder_index": int(pre.next_withdrawal_builder_index),
        "observed_eligible_validator_sweep": any(
            spec.is_fully_withdrawable_validator(v, pre.balances[i], epoch)
            or spec.is_partially_withdrawable_validator(v, pre.balances[i])
            for i, v in enumerate(pre.validators)
        ),
        "observed_partial_validator_sweep": any(
            w.validator_index < len(pre.validators)
            and spec.is_partially_withdrawable_validator(
                pre.validators[w.validator_index], pre.balances[w.validator_index]
            )
            for w in expected.withdrawals
        ),
        "observed_total_withdrawals": len(expected.withdrawals),
    }
