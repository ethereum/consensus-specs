"""Independent semantic validation for pending-deposit compliance vectors."""

from __future__ import annotations

from ..validation import Check, decode

from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from eth_consensus_specs.gloas import minimal as spec

_YAML = YAML(typ="safe")

def _role(state: Any, deposit: Any, next_epoch: Any) -> str:
    pubkeys = [validator.pubkey for validator in state.validators]
    if deposit.pubkey not in pubkeys:
        return (
            "NEW_VALID"
            if spec.is_valid_deposit_signature(
                deposit.pubkey, deposit.withdrawal_credentials, deposit.amount, deposit.signature
            )
            else "NEW_INVALID"
        )
    validator = state.validators[pubkeys.index(deposit.pubkey)]
    if validator.withdrawable_epoch < next_epoch:
        return "WITHDRAWN"
    if validator.exit_epoch < spec.FAR_FUTURE_EPOCH:
        return "EXITING"
    return "ACTIVE"

def replay(pre: Any) -> dict[str, Any]:
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
        role = _role(pre, deposit, next_epoch)
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

def recover_dimensions(pre: Any, trace: dict[str, Any]) -> dict[str, Any]:
    deposits = pre.pending_deposits
    if not deposits:
        return {
            "queue_layout": "EMPTY",
            "secondary_role": "SECOND_NONE",
            "primary_reached": False,
            "primary_role": "ROLE_NA",
            "deposit_signature_valid": "NA",
            "validator_pubkey_found": False,
            "validator_active": "NA",
            "validator_exiting": "NA",
            "withdrawable_epoch_to_next_epoch": "NA",
            "initial_churn": "CARRY_NONZERO" if pre.deposit_balance_to_consume else "CARRY_ZERO",
            "primary_amount_to_available": "NA",
            "second_amount_to_remaining": "NA",
            "churn_effect": "CHURN_CLEARED",
            "outcome": "EMPTY_QUEUE",
        }
    candidate = (
        deposits[int(spec.MAX_PENDING_DEPOSITS_PER_EPOCH)]
        if trace["gate"] == "PER_EPOCH_LIMIT"
        else deposits[0]
    )
    next_epoch = spec.Epoch(spec.get_current_epoch(pre) + 1)
    role = _role(pre, candidate, next_epoch)
    finalized_slot = spec.compute_start_slot_at_epoch(pre.finalized_checkpoint.epoch)
    if trace["gate"] == "PER_EPOCH_LIMIT":
        prefix = deposits[: int(spec.MAX_PENDING_DEPOSITS_PER_EPOCH)]
        layout = (
            "LIMIT_AFTER_WITHDRAWN"
            if len(prefix) == int(spec.MAX_PENDING_DEPOSITS_PER_EPOCH)
            and all(_role(pre, deposit, next_epoch) == "WITHDRAWN" for deposit in prefix)
            and role == "WITHDRAWN"
            else "INVALID_LAYOUT"
        )
    elif deposits[0].slot > finalized_slot:
        layout = "FIRST_UNFINALIZED"
    elif role == "EXITING" and len(deposits) > 1:
        second = deposits[1]
        layout = (
            "POSTPONE_THEN_ACTIVE"
            if second.slot <= finalized_slot and _role(pre, second, next_epoch) == "ACTIVE"
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
        second_role = _role(pre, second, next_epoch)
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
    withdrawable = "NA"
    if validator is not None:
        withdrawable = (
            "LT"
            if validator.withdrawable_epoch < next_epoch
            else ("EQ" if validator.withdrawable_epoch == next_epoch else "GT")
        )
    available = pre.deposit_balance_to_consume + spec.get_activation_churn_limit(pre)
    comparison = (
        "NA"
        if role in {"EXITING", "WITHDRAWN"}
        else (
            "LT"
            if candidate.amount < available
            else "EQ"
            if candidate.amount == available
            else "GT"
        )
    )
    second_comparison = "NA"
    if layout in {"TWO_PROCESSABLE", "INVALID_THEN_PROCESSABLE"}:
        remaining = available - candidate.amount
        second_amount = deposits[1].amount
        second_comparison = (
            "LT" if second_amount < remaining else "EQ" if second_amount == remaining else "GT"
        )
    outcome = {
        "UNFINALIZED": "STOP_UNFINALIZED",
        "PER_EPOCH_LIMIT": "STOP_PER_EPOCH_LIMIT",
        "CHURN_LIMIT": "STOP_CHURN_LIMIT",
        "EMPTY": "EMPTY_QUEUE",
    }.get(trace["gate"], "PROCESSED")
    return {
        "queue_layout": layout,
        "secondary_role": "SECOND_ACTIVE"
        if layout == "POSTPONE_THEN_ACTIVE"
        else (
            "SECOND_UNFINALIZED"
            if layout == "ACTIVE_THEN_UNFINALIZED"
            else "SECOND_PROCESSABLE"
            if layout in {"TWO_PROCESSABLE", "INVALID_THEN_PROCESSABLE"}
            else "SECOND_NONE"
        ),
        "primary_reached": layout not in {"EMPTY", "FIRST_UNFINALIZED", "LIMIT_AFTER_WITHDRAWN"},
        "primary_role": role,
        "deposit_signature_valid": "T"
        if role == "NEW_VALID"
        else "F"
        if role == "NEW_INVALID"
        else "NA",
        "validator_pubkey_found": found,
        "validator_active": "T" if role == "ACTIVE" else "F" if found else "NA",
        "validator_exiting": "T" if role in {"EXITING", "WITHDRAWN"} else "F" if found else "NA",
        "withdrawable_epoch_to_next_epoch": withdrawable
        if role in {"EXITING", "WITHDRAWN"}
        else "NA",
        "initial_churn": "CARRY_NONZERO" if pre.deposit_balance_to_consume else "CARRY_ZERO",
        "primary_amount_to_available": comparison,
        "second_amount_to_remaining": second_comparison,
        "churn_effect": "CHURN_RETAINED" if trace["gate"] == "CHURN_LIMIT" else "CHURN_CLEARED",
        "outcome": outcome,
    }

def validate_case(case_dir: Path) -> list[Check]:
    pre = decode(case_dir / "pre.ssz_snappy", spec.BeaconState)
    claimed = _YAML.load((case_dir / "dimensions.yaml").read_text())["claimed"]
    trace = replay(pre)
    actual = recover_dimensions(pre, trace)
    checks = [
        Check(name, value, actual.get(name), "ok" if actual.get(name) == value else "mismatch")
        for name, value in claimed.items()
    ]
    return checks
