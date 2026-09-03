% Aspect: builder pending withdrawal processing (process_withdrawals pending path).
%
% Self-contained bundle of the builder_pending_withdrawal_processing model and
% its transitive dependencies (builder_withdrawals/pending_withdrawal and
% builder/builder), inlined into a single file.
%
% state_latest_block_hash_match is fixed to T in this test; the embedded
% pending-withdrawal entry applies pending_withdrawal_constraints transitively
% (which itself applies builder_constraints).

enum OpCmp = { LT, EQ, GT, NA_CMP };
enum OpBool = { F, T, NA_BOOL };

set of OpCmp: CMP = { LT, EQ, GT };

% --- builder/builder ---

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

% --- builder_withdrawals/pending_withdrawal ---

type BuilderPendingWithdrawal = record(
    var Builder: builder,
    var CMP:     cmp_pending_amount_zero,
    var CMP:     cmp_builder_balance_amount,
);

predicate pending_withdrawal_constraints(var BuilderPendingWithdrawal: w) =
    builder_constraints(w.builder)
    /\ is_external_builder(w.builder)
    /\ (w.builder.has_pending_withdrawals == T)
    /\ (w.builder.payload_builder_version == T)
    /\ (w.cmp_pending_amount_zero == GT)
    /\ (w.cmp_builder_balance_amount in CMP);

% --- withdrawal_processing/builder_pending_withdrawal_processing ---

type BuilderPendingWithdrawalProcessing = record(
    var {F, T}: state_latest_block_hash_match,
    var BuilderPendingWithdrawal: pending_withdrawal,
);

var BuilderPendingWithdrawalProcessing: p;

predicate builder_pending_withdrawal_processing_constraints(var BuilderPendingWithdrawalProcessing: p) =
    pending_withdrawal_constraints(p.pending_withdrawal)
    /\ (p.state_latest_block_hash_match == T);

constraint builder_pending_withdrawal_processing_constraints(p);
