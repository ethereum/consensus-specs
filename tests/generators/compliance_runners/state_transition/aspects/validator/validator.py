from dataclasses import dataclass

from tests.generators.compliance_runners.state_transition.aspects.base import (
    Bool,
    Cmp,
    constraint,
    predicate,
    Record,
    ValidatorCredentialKind,
)


@dataclass
class Validator(Record):
    withdrawal_credential: ValidatorCredentialKind
    cmp_state_epoch_activation_epoch: Cmp
    cmp_state_epoch_exit_epoch: Cmp
    cmp_state_epoch_withdrawal_epoch: Cmp
    cmp_finalized_epoch_activation_eligibility_epoch: Cmp
    withdrawable_epoch_set: Bool
    exit_epoch_set: Bool
    cmp_balance_zero: Cmp
    cmp_effective_balance_min_activation_balance: Cmp
    has_pending_withdrawal: Bool


@predicate
def is_withdrawable_validator(v: Validator) -> bool:
    return v.cmp_state_epoch_withdrawal_epoch in {Cmp.EQ, Cmp.GT}


@predicate
def is_active_validator(v: Validator) -> bool:
    return (
        v.cmp_state_epoch_activation_epoch in {Cmp.EQ, Cmp.GT}
        and v.cmp_state_epoch_exit_epoch == Cmp.LT
    )


@predicate
def has_pending_withdrawal(v: Validator) -> bool:
    return v.has_pending_withdrawal == Bool.T


@predicate
def is_fully_withdrawable_validator(v: Validator) -> bool:
    return (
        v.withdrawal_credential != ValidatorCredentialKind.BLS
        and is_withdrawable_validator(v)
        and v.cmp_balance_zero == Cmp.GT
    )


@constraint
def validator_constraints(v: Validator) -> None:
    # `initiate_validator_exit` assigns the exit and withdrawable epochs together —
    # both are FAR_FUTURE_EPOCH before exit and both are set after.
    # (specs/phase0/beacon-chain.md initiate_validator_exit)
    assert v.exit_epoch_set == v.withdrawable_epoch_set

    # The balance of a validator is never negative.
    assert v.cmp_balance_zero in {Cmp.GT, Cmp.EQ}

    # Exit requires prior activation: `initiate_validator_exit` is only reached
    # for an active (or slashable) validator, so the activation epoch must have
    # been reached once exit is initiated.
    if v.exit_epoch_set == Bool.T:
        assert v.cmp_state_epoch_activation_epoch in {Cmp.EQ, Cmp.GT}

    # Activation requires finalized eligibility: `is_eligible_for_activation`
    # requires `activation_eligibility_epoch <= finalized_checkpoint.epoch`, so a
    # validator is only activated after its queue placement is finalized.
    if v.cmp_state_epoch_activation_epoch in {Cmp.EQ, Cmp.GT}:
        assert v.cmp_finalized_epoch_activation_eligibility_epoch in {Cmp.EQ, Cmp.GT}

    # Strict epoch ordering `activation_epoch < exit_epoch < withdrawable_epoch`:
    # reaching a later epoch implies the earlier one is strictly in the past.
    if v.cmp_state_epoch_exit_epoch in {Cmp.EQ, Cmp.GT}:
        assert v.cmp_state_epoch_activation_epoch == Cmp.GT
    if v.cmp_state_epoch_withdrawal_epoch in {Cmp.EQ, Cmp.GT}:
        assert v.cmp_state_epoch_exit_epoch == Cmp.GT

    # A non-compounding validator's effective balance is capped at
    # MIN_ACTIVATION_BALANCE (`get_max_effective_balance` returns
    # MIN_ACTIVATION_BALANCE unless the validator is compounding).
    if v.withdrawal_credential != ValidatorCredentialKind.COMPOUNDING:
        assert v.cmp_effective_balance_min_activation_balance in {Cmp.EQ, Cmp.LT}

    # A pending partial withdrawal requires an execution (ETH1/COMPOUNDING)
    # credential (specs/electra/beacon-chain.md is_eligible_for_partial_withdrawals).
    if v.has_pending_withdrawal == Bool.T:
        assert v.withdrawal_credential != ValidatorCredentialKind.BLS

    # An unset (FAR_FUTURE_EPOCH) withdrawable/exit epoch is strictly after the
    # current epoch.
    if v.withdrawable_epoch_set == Bool.F:
        assert v.cmp_state_epoch_withdrawal_epoch == Cmp.LT
    if v.exit_epoch_set == Bool.F:
        assert v.cmp_state_epoch_exit_epoch == Cmp.LT
