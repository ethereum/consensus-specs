from dataclasses import dataclass

from tests.generators.compliance_runners.state_transition.aspects.base import (
    Bool,
    Cmp,
    constraint,
    Record,
    ValidatorCredentialKind,
)
from tests.generators.compliance_runners.state_transition.aspects.validator.validator import (
    Validator,
    validator_constraints,
)


@dataclass
class ValidatorPendingPartialWithdrawal(Record):
    validator: Validator
    # Whether the pending partial withdrawal is withdrawable at the current
    # state epoch (get_pending_partial_withdrawals:
    #   is_withdrawable = withdrawal.withdrawable_epoch <= epoch).
    withdrawable: Bool
    # Pending partial withdrawal amount vs 0 (amount > 0 by construction)
    cmp_pending_amount_zero: Cmp
    # Validator balance vs pending partial withdrawal amount (saturation in
    # get_pending_partial_withdrawals:
    #   withdrawal_amount = min(balance - MIN_ACTIVATION_BALANCE, amount))
    cmp_balance_amount: Cmp


@constraint
def pending_partial_withdrawal_constraints(w: ValidatorPendingPartialWithdrawal) -> None:
    # Apply validator_constraints transitively
    validator_constraints(w.validator)
    # Partial withdrawals only for validators whose exit has not been initiated
    # (is_eligible_for_partial_withdrawals requires exit_epoch == FAR_FUTURE_EPOCH).
    assert w.validator.exit_epoch_set == Bool.F
    # The validator must have a pending partial withdrawal.
    assert w.validator.has_pending_withdrawal == Bool.T
    # Pending partial withdrawals are only created for compounding validators
    # (process_withdrawal_request: "Only allow partial withdrawals with
    # compounding withdrawal credentials").
    assert w.validator.withdrawal_credential == ValidatorCredentialKind.COMPOUNDING
    # The validator must have sufficient effective balance
    # (process_withdrawal_request: effective_balance >= MIN_ACTIVATION_BALANCE).
    assert w.validator.cmp_effective_balance_min_activation_balance in {Cmp.EQ, Cmp.GT}
    # All pending partial withdrawals have amount > 0 (creation guards in spec).
    assert w.cmp_pending_amount_zero == Cmp.GT
    # Balance vs amount: the min() saturation in get_pending_partial_withdrawals
    # allows any ordering.
    assert w.cmp_balance_amount in {Cmp.LT, Cmp.EQ, Cmp.GT}
