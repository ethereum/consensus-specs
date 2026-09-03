% Aspect: validator (aggregate record).
%
% Bundles a referenced validator's coverage dimensions for the Gloas
% process_withdrawals / process_registry_updates handlers
% (specs/phase0|capella|electra/beacon-chain.md).
%
% Strict epoch ordering activation_epoch < exit_epoch < withdrawable_epoch;
% exit and withdrawable epochs are set together by initiate_validator_exit;
% activation requires finalized eligibility; non-compounding validators cap
% their effective balance at MIN_ACTIVATION_BALANCE; a pending partial
% withdrawal requires an execution (ETH1/COMPOUNDING) credential.

include "../base.mzn";

enum ValidatorCredentialKind = { BLS, ETH1, COMPOUNDING };

type Validator = record(
    var ValidatorCredentialKind: withdrawal_credential,
    var CMP: cmp_state_epoch_activation_epoch,
    var CMP: cmp_state_epoch_exit_epoch,
    var CMP: cmp_state_epoch_withdrawal_epoch,
    var CMP: cmp_finalized_epoch_activation_eligibility_epoch,
    var BOOLV: withdrawable_epoch_set,
    var BOOLV: exit_epoch_set,
    var CMP: cmp_balance_zero,
    var CMP: cmp_effective_balance_min_activation_balance,
    var BOOLV: has_pending_withdrawal,
);

predicate is_withdrawable_validator(var Validator: v) =
    v.cmp_state_epoch_withdrawal_epoch in {EQ, GT};

predicate is_active_validator(var Validator: v) =
    v.cmp_state_epoch_activation_epoch in {EQ, GT}
    /\ v.cmp_state_epoch_exit_epoch == LT;

predicate has_pending_withdrawal(var Validator: v) =
    v.has_pending_withdrawal == T;

predicate is_fully_withdrawable_validator(var Validator: v) =
    v.withdrawal_credential != BLS
    /\ is_withdrawable_validator(v)
    /\ v.cmp_balance_zero == GT;

predicate validator_constraints(var Validator: v) =
    % initiate_validator_exit assigns the exit and withdrawable epochs together.
    v.exit_epoch_set == v.withdrawable_epoch_set
    % The balance of a validator is never negative.
    /\ v.cmp_balance_zero in {GT, EQ}
    % Exit requires prior activation.
    /\ (v.exit_epoch_set == T ->
            v.cmp_state_epoch_activation_epoch in {EQ, GT})
    % Activation requires finalized eligibility.
    /\ (v.cmp_state_epoch_activation_epoch in {EQ, GT} ->
            v.cmp_finalized_epoch_activation_eligibility_epoch in {EQ, GT})
    % Strict epoch ordering: activation < exit < withdrawable.
    /\ (v.cmp_state_epoch_exit_epoch in {EQ, GT} ->
            v.cmp_state_epoch_activation_epoch == GT)
    /\ (v.cmp_state_epoch_withdrawal_epoch in {EQ, GT} ->
            v.cmp_state_epoch_exit_epoch == GT)
    % Non-compounding validators cap effective balance at MIN_ACTIVATION_BALANCE.
    /\ (v.withdrawal_credential != COMPOUNDING ->
            v.cmp_effective_balance_min_activation_balance in {EQ, LT})
    % A pending partial withdrawal requires an execution credential.
    /\ (v.has_pending_withdrawal == T ->
            v.withdrawal_credential != BLS)
    % An unset (FAR_FUTURE_EPOCH) epoch is strictly after the current epoch.
    /\ (v.withdrawable_epoch_set == F ->
            v.cmp_state_epoch_withdrawal_epoch == LT)
    /\ (v.exit_epoch_set == F ->
            v.cmp_state_epoch_exit_epoch == LT);
