"""Observe pending-deposit queue roles, numeric boundaries, and loop outcomes."""

from typing import Any

from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import NA
from tests.generators.compliance_runners.state_transition.validation_helpers import bls_enabled


def _role(spec: Any, state: Any, deposit: Any, next_epoch: Any) -> str:
    pubkeys = [validator.pubkey for validator in state.validators]
    if deposit.pubkey not in pubkeys:
        with bls_enabled():
            valid = spec.is_valid_deposit_signature(
                deposit.pubkey, deposit.withdrawal_credentials, deposit.amount, deposit.signature
            )
        return "NEW_VALID" if valid else "NEW_INVALID"
    validator = state.validators[pubkeys.index(deposit.pubkey)]
    if validator.withdrawable_epoch < next_epoch:
        return "WITHDRAWN"
    if validator.exit_epoch < spec.FAR_FUTURE_EPOCH:
        return "EXITING"
    return "ACTIVE"


def replay(spec: Any, pre: Any) -> dict[str, Any]:
    """Recover the handler's loop trace without invoking the handler itself."""
    next_epoch = spec.Epoch(spec.get_current_epoch(pre) + 1)
    available = pre.deposit_balance_to_consume + spec.get_activation_churn_limit(pre)
    finalized_slot = spec.compute_start_slot_at_epoch(pre.finalized_checkpoint.epoch)
    processed_amount = 0
    consumed = 0
    postponed: list[Any] = []
    applied: list[Any] = []
    gate = "EMPTY"

    for deposit in pre.pending_deposits:
        if deposit.slot > finalized_slot:
            gate = "UNFINALIZED"
            break
        if consumed >= spec.MAX_PENDING_DEPOSITS_PER_EPOCH:
            gate = "PER_EPOCH_LIMIT"
            break
        role = _role(spec, pre, deposit, next_epoch)
        if role == "WITHDRAWN":
            applied.append(deposit)
        elif role == "EXITING":
            postponed.append(deposit)
        else:
            if processed_amount + deposit.amount > available:
                gate = "CHURN_LIMIT"
                break
            processed_amount += deposit.amount
            if role != "NEW_INVALID":
                applied.append(deposit)
        consumed += 1
    else:
        gate = "EXHAUSTED"

    return {
        "gate": gate,
        "consumed": consumed,
        "processed_amount": processed_amount,
        "postponed": postponed,
        "applied": applied,
        "expected_queue": list(pre.pending_deposits[consumed:]) + postponed,
        "expected_churn": available - processed_amount if gate == "CHURN_LIMIT" else 0,
    }


def observe_attributes(ctx):
    spec, pre = ctx.spec, ctx.pre
    trace = replay(spec, pre)
    deposits = pre.pending_deposits
    next_epoch = int(spec.get_current_epoch(pre)) + 1
    available = int(pre.deposit_balance_to_consume + spec.get_activation_churn_limit(pre))
    result = {
        "observed_initial_churn": int(pre.deposit_balance_to_consume),
        "observed_next_epoch": next_epoch,
        "observed_available_churn": available,
        "observed_churn_retained": bool(
            ctx.post is not None and ctx.post.deposit_balance_to_consume
        ),
        "observed_outcome": {
            "UNFINALIZED": "STOP_UNFINALIZED",
            "PER_EPOCH_LIMIT": "STOP_PER_EPOCH_LIMIT",
            "CHURN_LIMIT": "STOP_CHURN_LIMIT",
        }.get(trace["gate"], "PROCESSED" if deposits else "EMPTY_QUEUE"),
    }
    if not deposits:
        result.update(
            observed_queue_layout="EMPTY",
            observed_primary_role="ROLE_NA",
            observed_validator_pubkey_found=False,
            observed_validator_active=NA,
            observed_validator_exiting=NA,
            observed_deposit_signature_valid=NA,
            observed_withdrawable_epoch=NA,
            observed_primary_amount=NA,
            observed_second_amount=NA,
            observed_remaining_churn=NA,
        )
        return result
    candidate = (
        deposits[int(spec.MAX_PENDING_DEPOSITS_PER_EPOCH)]
        if trace["gate"] == "PER_EPOCH_LIMIT"
        else deposits[0]
    )
    next_epoch = spec.Epoch(spec.get_current_epoch(pre) + 1)
    role = _role(spec, pre, candidate, next_epoch)
    finalized_slot = spec.compute_start_slot_at_epoch(pre.finalized_checkpoint.epoch)
    if trace["gate"] == "PER_EPOCH_LIMIT":
        prefix = deposits[: int(spec.MAX_PENDING_DEPOSITS_PER_EPOCH)]
        layout = (
            "LIMIT_AFTER_WITHDRAWN"
            if len(prefix) == int(spec.MAX_PENDING_DEPOSITS_PER_EPOCH)
            and all(_role(spec, pre, deposit, next_epoch) == "WITHDRAWN" for deposit in prefix)
            and role == "WITHDRAWN"
            else "INVALID_LAYOUT"
        )
    elif deposits[0].slot > finalized_slot:
        layout = "FIRST_UNFINALIZED"
    elif role == "EXITING" and len(deposits) > 1:
        second = deposits[1]
        layout = (
            "POSTPONE_THEN_ACTIVE"
            if second.slot <= finalized_slot and _role(spec, pre, second, next_epoch) == "ACTIVE"
            else "INVALID_LAYOUT"
        )
    elif len(deposits) > 1 and deposits[1].slot > finalized_slot:
        layout = (
            "ACTIVE_THEN_UNFINALIZED"
            if role in {"ACTIVE", "NEW_VALID", "NEW_INVALID"}
            else "INVALID_LAYOUT"
        )
    elif len(deposits) == 2 and role in {"ACTIVE", "NEW_VALID", "NEW_INVALID"}:
        second = deposits[1]
        second_role = _role(spec, pre, second, next_epoch)
        if second.slot <= finalized_slot and second_role == "ACTIVE":
            layout = "INVALID_THEN_PROCESSABLE" if role == "NEW_INVALID" else "TWO_PROCESSABLE"
        else:
            layout = "INVALID_LAYOUT"
    else:
        layout = "SINGLE"
    found = role in {"ACTIVE", "EXITING", "WITHDRAWN"}
    validator = (
        pre.validators[[v.pubkey for v in pre.validators].index(candidate.pubkey)]
        if found
        else None
    )
    two_entries = layout in {"TWO_PROCESSABLE", "INVALID_THEN_PROCESSABLE"}
    result.update(
        observed_queue_layout=layout,
        observed_primary_role=role,
        observed_validator_pubkey_found=found,
        observed_validator_active=(
            bool(spec.is_active_validator(validator, spec.get_current_epoch(pre))) if found else NA
        ),
        observed_validator_exiting=(
            bool(validator.exit_epoch != spec.FAR_FUTURE_EPOCH) if found else NA
        ),
        observed_deposit_signature_valid=(role == "NEW_VALID" if role.startswith("NEW_") else NA),
        observed_withdrawable_epoch=int(validator.withdrawable_epoch) if found else NA,
        observed_primary_amount=int(candidate.amount),
        observed_second_amount=int(deposits[1].amount) if two_entries else NA,
        observed_remaining_churn=available - int(candidate.amount) if two_entries else NA,
    )
    return result
