"""Observe consolidation-request roles, balances, queue inputs, and post effects."""

from tests.generators.compliance_runners.state_transition.aspects_helpers.queue_churn import (
    queue_churn_variant,
)
from tests.generators.compliance_runners.state_transition.aspects_helpers.withdrawal_credential import (
    withdrawal_credentials_profile,
)


def observe_attributes(ctx):
    spec, pre, request, post = ctx.spec, ctx.pre, ctx.operation, ctx.post
    current = spec.get_current_epoch(pre)
    pubkeys = [v.pubkey for v in pre.validators]
    source = pubkeys.index(request.source_pubkey) if request.source_pubkey in pubkeys else None
    target = pubkeys.index(request.target_pubkey) if request.target_pubkey in pubkeys else None
    same = request.source_pubkey == request.target_pubkey
    values = {
        "same_source_target": same,
        "queue_length": len(pre.pending_consolidations),
        "consolidation_churn": int(spec.get_consolidation_churn_limit(pre)),
        "validator_pubkey_found": source is not None,
        "validator_credential": "BLS",
        "source_address_matches": False,
        "validator_active": False,
        "validator_exiting": False,
        "validator_old_enough": False,
        "has_pending_partial_withdrawal": False,
        "source_balance": 0,
        "churn_variant": "RESET_FIT",
        "target_found": target is not None,
        "target_credential": "BLS",
        "target_active": False,
        "target_exiting": False,
        "switch_excess_queued": False,
        "state_effected": False,
    }
    if source is not None:
        validator = pre.validators[source]
        balance = int(pre.balances[source])
        values.update(
            validator_credential=withdrawal_credentials_profile(
                spec, validator.withdrawal_credentials
            ),
            source_address_matches=validator.withdrawal_credentials[12:] == request.source_address,
            validator_active=bool(spec.is_active_validator(validator, current)),
            validator_exiting=validator.exit_epoch != spec.FAR_FUTURE_EPOCH,
            validator_old_enough=int(current)
            >= int(validator.activation_epoch) + int(spec.config.SHARD_COMMITTEE_PERIOD),
            has_pending_partial_withdrawal=int(
                spec.get_pending_balance_to_withdraw(pre, spec.ValidatorIndex(source))
            )
            > 0,
            source_balance=balance,
            churn_variant=queue_churn_variant(
                spec.compute_activation_exit_epoch(current),
                pre.earliest_consolidation_epoch,
                validator.effective_balance,
                pre.consolidation_balance_to_consume,
            ),
        )
        if post is not None:
            switched = (
                same
                and validator.withdrawal_credentials[:1] == spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX
                and post.validators[source].withdrawal_credentials
                == spec.COMPOUNDING_WITHDRAWAL_PREFIX + validator.withdrawal_credentials[1:]
            )
            if len(post.pending_deposits) == len(pre.pending_deposits) + 1:
                deposit = post.pending_deposits[-1]
                values["switch_excess_queued"] = bool(
                    switched
                    and balance > int(spec.MIN_ACTIVATION_BALANCE)
                    and int(post.balances[source]) == int(spec.MIN_ACTIVATION_BALANCE)
                    and deposit.pubkey == validator.pubkey
                    and deposit.withdrawal_credentials
                    == post.validators[source].withdrawal_credentials
                    and int(deposit.amount) == balance - int(spec.MIN_ACTIVATION_BALANCE)
                    and deposit.signature == spec.bls.G2_POINT_AT_INFINITY
                    and deposit.slot == spec.GENESIS_SLOT
                )
            consolidated = False
            if (
                not same
                and target is not None
                and len(post.pending_consolidations) == len(pre.pending_consolidations) + 1
            ):
                appended = post.pending_consolidations[-1]
                consolidated = (
                    appended.source_index == source
                    and appended.target_index == target
                    and validator.exit_epoch == spec.FAR_FUTURE_EPOCH
                    and post.validators[source].exit_epoch != spec.FAR_FUTURE_EPOCH
                    and post.validators[source].withdrawable_epoch
                    == post.validators[source].exit_epoch
                    + spec.config.MIN_VALIDATOR_WITHDRAWABILITY_DELAY
                )
            values["state_effected"] = bool(switched or consolidated)
    if not same and target is not None:
        validator = pre.validators[target]
        values.update(
            target_credential=withdrawal_credentials_profile(
                spec, validator.withdrawal_credentials
            ),
            target_active=bool(spec.is_active_validator(validator, current)),
            target_exiting=validator.exit_epoch != spec.FAR_FUTURE_EPOCH,
        )
    return {f"observed_{name}": value for name, value in values.items()}
