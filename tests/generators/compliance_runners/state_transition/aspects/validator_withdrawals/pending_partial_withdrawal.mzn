% Aspect: validator pending partial withdrawal (get_pending_partial_withdrawals).
%
% Models a single pending partial withdrawal entry from
% state.pending_partial_withdrawals (specs/electra/beacon-chain.md
% process_withdrawal_request / get_pending_partial_withdrawals).
%
% pending_partial_withdrawal_constraints: the referenced validator is
% compounding, has sufficient effective balance (>= MIN_ACTIVATION_BALANCE),
% has not initiated exit, and has the pending withdrawal; the withdrawn amount
% is positive and the balance-vs-amount ordering is free (min() saturation).

include "../validator/validator.mzn";

type ValidatorPendingPartialWithdrawal = record(
    var Validator: validator,
    var BOOLV: withdrawable,
    var CMP: cmp_pending_amount_zero,
    var CMP: cmp_balance_amount,
);

predicate pending_partial_withdrawal_constraints(var ValidatorPendingPartialWithdrawal: w) =
    validator_constraints(w.validator)
    /\ (w.validator.exit_epoch_set == F)
    /\ (w.validator.has_pending_withdrawal == T)
    /\ (w.validator.withdrawal_credential == COMPOUNDING)
    /\ (w.validator.cmp_effective_balance_min_activation_balance in {EQ, GT})
    /\ (w.cmp_pending_amount_zero == GT)
    /\ (w.cmp_balance_amount in {LT, EQ, GT});
