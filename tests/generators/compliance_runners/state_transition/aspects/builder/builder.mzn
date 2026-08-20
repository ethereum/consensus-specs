% Aspect: builder (aggregate record).
%
% Bundles a referenced builder's coverage dimensions
% (specs/gloas/beacon-chain.md process_execution_payload_bid).
% is_self_builder: every dimension NA (self-build path, no builder resolved).
% is_external_builder: every dimension non-NA (existing builder resolved).
% is_active_builder: finalized_epoch < deposit_epoch and not withdrawable.
% has_pending_withdrawals: pending payments or pending withdrawals present.
% builder_constraints: when not a self-builder, state/epoch and balance
% comparisons must be >= (EQ or GT); pending withdrawals require an active
% builder with a strictly positive balance gap to min_balance; when the
% withdrawable epoch is unset, the current epoch must precede it.

enum OpCmp = { LT, EQ, GT, NA_CMP };
enum OpBool = { F, T, NA_BOOL };

type Builder = record(
    var OpBool: payload_builder_version,
    var OpCmp:  cmp_state_epoch_deposit_epoch,
    var OpCmp:  cmp_state_epoch_withdrawal_epoch,
    var OpCmp:  cmp_finalized_epoch_deposit_epoch,
    var OpBool: withdrawable_epoch_set,
    var OpCmp:  cmp_balance_zero,
    var OpCmp:  cmp_balance_min_deposit,
    var OpBool: has_pending_payments,
    var OpBool: has_pending_withdrawals,
);

predicate is_self_builder(var Builder: b) =
    b.payload_builder_version == NA_BOOL
    /\ b.cmp_state_epoch_deposit_epoch == NA_CMP
    /\ b.cmp_state_epoch_withdrawal_epoch == NA_CMP
    /\ b.cmp_finalized_epoch_deposit_epoch == NA_CMP
    /\ b.withdrawable_epoch_set == NA_BOOL
    /\ b.cmp_balance_zero == NA_CMP
    /\ b.cmp_balance_min_deposit == NA_CMP
    /\ b.has_pending_payments == NA_BOOL
    /\ b.has_pending_withdrawals == NA_BOOL;

predicate is_external_builder(var Builder: b) =
    b.payload_builder_version != NA_BOOL
    /\ b.cmp_state_epoch_deposit_epoch != NA_CMP
    /\ b.cmp_state_epoch_withdrawal_epoch != NA_CMP
    /\ b.cmp_finalized_epoch_deposit_epoch != NA_CMP
    /\ b.withdrawable_epoch_set != NA_BOOL
    /\ b.cmp_balance_zero != NA_CMP
    /\ b.cmp_balance_min_deposit != NA_CMP
    /\ b.has_pending_payments != NA_BOOL
    /\ b.has_pending_withdrawals != NA_BOOL;

predicate is_active_builder(var Builder: b) =
    b.cmp_finalized_epoch_deposit_epoch == GT
    /\ b.withdrawable_epoch_set == F;

predicate has_pending_withdrawals(var Builder: b) =
    b.has_pending_payments == T
    \/ b.has_pending_withdrawals == T;

predicate builder_constraints(var Builder: b) =
    (not is_self_builder(b)) <-> is_external_builder(b)
    /\ (not is_self_builder(b) -> (b.cmp_state_epoch_deposit_epoch in {EQ, GT}))
    /\ (not is_self_builder(b) -> (b.cmp_balance_zero in {EQ, GT}))
    /\ (not is_self_builder(b) -> ((b.cmp_balance_zero == EQ) <-> (b.cmp_balance_min_deposit == LT)))
    /\ (not is_self_builder(b) -> (has_pending_withdrawals(b) -> is_active_builder(b)))
    /\ (not is_self_builder(b) -> (is_active_builder(b) -> (b.cmp_balance_min_deposit in {EQ, GT})))
    /\ (not is_self_builder(b) -> (has_pending_withdrawals(b) -> (b.cmp_balance_min_deposit == GT)))
    /\ (not is_self_builder(b) -> ((b.withdrawable_epoch_set == F) -> (b.cmp_state_epoch_withdrawal_epoch == LT)));
