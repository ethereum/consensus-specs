% Realization aspect: builder pending balance / queues.
%
% Spec: get_pending_balance_to_withdraw_for_builder sums builder_pending_withdrawals
% and builder_pending_payments for the builder (specs/gloas/beacon-chain.md :720).
% Feeds the min-balance offset of the funds aspect.
%
% Shared with builder_exit_request (which gates on pending balance == 0).

include "base.mzn";

var bool: builder_pending_applicable;
var BOOLV_NA: builder_has_pending_withdrawal;
var BOOLV_NA: builder_has_pending_payment;
constraint (builder_has_pending_withdrawal == NA) <-> not builder_pending_applicable;
constraint (builder_has_pending_payment == NA)    <-> not builder_pending_applicable;

var bool: builder_has_pending_balance;
constraint builder_has_pending_balance <->
    (builder_has_pending_withdrawal == T \/ builder_has_pending_payment == T);
