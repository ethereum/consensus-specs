% Realization aspect: builder lifecycle (is_active_builder).
%
% Spec: is_active_builder(state, builder_index) =
%   builder.deposit_epoch < state.finalized_checkpoint.epoch
%   and builder.withdrawable_epoch == FAR_FUTURE_EPOCH
% (specs/gloas/beacon-chain.md, is_active_builder)
%
% Shared with builder_exit_request, which gates on the same predicate.

include "base.mzn";

% Applicability: bound by the handler (a resolved, existing builder).
var bool: builder_lifecycle_applicable;

% Coverage dimensions.
var CMP_NA:   builder_deposit_to_finalized_epoch;  % compare(deposit_epoch, finalized_epoch)
var BOOLV_NA: builder_withdrawable_epoch_set;       % withdrawable_epoch != FAR_FUTURE_EPOCH

constraint (builder_deposit_to_finalized_epoch == NA) <-> not builder_lifecycle_applicable;
constraint (builder_withdrawable_epoch_set == NA)     <-> not builder_lifecycle_applicable;

% Derived: active iff placement finalized and no exit initiated.
var bool: builder_active;
constraint builder_active <->
    (builder_deposit_to_finalized_epoch == LT /\ builder_withdrawable_epoch_set == F);
