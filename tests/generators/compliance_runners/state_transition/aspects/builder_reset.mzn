% Realization aspect: swept-builder reset condition (builder_deposit_request).
%
% On a top-up to an exited, drained builder — withdrawable_epoch != FAR_FUTURE
% and balance == 0 — the withdrawable epoch is reset before crediting the
% deposit (specs/gloas/beacon-chain.md process_builder_deposit_request).
%
% Note: `builder_withdrawable_epoch_set` is the same predicate as in
% builder_lifecycle; a future refactor could factor it into a shared
% builder-exit-status aspect. Applicable only when a builder is resolved.

include "base.mzn";

var bool: builder_reset_applicable;
var BOOLV_NA: builder_withdrawable_epoch_set;
var BOOLV_NA: builder_balance_zero;
constraint (builder_withdrawable_epoch_set == NA) <-> not builder_reset_applicable;
constraint (builder_balance_zero == NA)            <-> not builder_reset_applicable;

var bool: reset_applies;
constraint reset_applies <->
    (builder_withdrawable_epoch_set == T /\ builder_balance_zero == T);
