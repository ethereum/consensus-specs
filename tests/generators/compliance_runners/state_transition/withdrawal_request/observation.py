"""Observe withdrawal-request inputs and effects independently of coverage claims."""

from tests.generators.compliance_runners.state_transition.aspects_helpers.queue_churn import (
    queue_churn_variant,
)
from tests.generators.compliance_runners.state_transition.aspects_helpers.withdrawal_credential import (
    withdrawal_credentials_profile,
)


def observe_attributes(ctx):
    spec, pre, request, post = ctx.spec, ctx.pre, ctx.operation, ctx.post
    current = spec.get_current_epoch(pre)
    index = next(
        (
            i
            for i, validator in enumerate(pre.validators)
            if validator.pubkey == request.validator_pubkey
        ),
        None,
    )
    values = {
        "is_full_exit_request": int(request.amount) == int(spec.FULL_EXIT_REQUEST_AMOUNT),
        "queue_length": len(pre.pending_partial_withdrawals),
        "validator_pubkey_found": index is not None,
        "validator_credential": "BLS",
        "source_address_matches": False,
        "validator_active": False,
        "validator_exiting": False,
        "validator_old_enough": False,
        "has_pending_partial_withdrawal": False,
        "effective_balance": 0,
        "balance": 0,
        "required_balance": int(spec.MIN_ACTIVATION_BALANCE),
        "churn_variant": "RESET_FIT",
        "exit_initiated": False,
        "partial_withdrawal_queued": False,
    }
    if index is not None:
        validator = pre.validators[index]
        pending = int(spec.get_pending_balance_to_withdraw(pre, spec.ValidatorIndex(index)))
        values.update(
            validator_credential=withdrawal_credentials_profile(
                spec, validator.withdrawal_credentials
            ),
            source_address_matches=validator.withdrawal_credentials[12:] == request.source_address,
            validator_active=bool(spec.is_active_validator(validator, current)),
            validator_exiting=validator.exit_epoch != spec.FAR_FUTURE_EPOCH,
            validator_old_enough=int(current)
            >= int(validator.activation_epoch) + int(spec.config.SHARD_COMMITTEE_PERIOD),
            has_pending_partial_withdrawal=pending > 0,
            effective_balance=int(validator.effective_balance),
            balance=int(pre.balances[index]),
            required_balance=int(spec.MIN_ACTIVATION_BALANCE) + pending,
            churn_variant=queue_churn_variant(
                spec.compute_activation_exit_epoch(current),
                pre.earliest_exit_epoch,
                validator.effective_balance,
                pre.exit_balance_to_consume,
            ),
            exit_initiated=post is not None
            and validator.exit_epoch == spec.FAR_FUTURE_EPOCH
            and post.validators[index].exit_epoch != spec.FAR_FUTURE_EPOCH,
        )
        if (
            post is not None
            and len(post.pending_partial_withdrawals) == len(pre.pending_partial_withdrawals) + 1
        ):
            appended = post.pending_partial_withdrawals[-1]
            expected_amount = min(
                int(request.amount),
                max(0, int(pre.balances[index]) - int(spec.MIN_ACTIVATION_BALANCE) - pending),
            )
            values["partial_withdrawal_queued"] = (
                appended.validator_index == index
                and int(appended.amount) == expected_amount
                and expected_amount > 0
            )
    values["withdrawal_effected"] = values.pop("exit_initiated") | values.pop(
        "partial_withdrawal_queued"
    )
    return {f"observed_{name}": value for name, value in values.items()}
