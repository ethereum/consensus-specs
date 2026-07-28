% Realization aspect: validator lifecycle.
%
%   active     <-> is_active_validator (activation_epoch <= epoch < exit_epoch)
%   exiting    <-> exit_epoch != FAR_FUTURE_EPOCH
%   old_enough <-> current_epoch >= activation_epoch + SHARD_COMMITTEE_PERIOD
% (specs/phase0 + electra). Applicable when a validator is resolved.
% Shared by withdrawal_request and consolidation_request.

include "base.mzn";

var bool: validator_lifecycle_applicable;
var BOOLV_NA: validator_active;
var BOOLV_NA: validator_exiting;
var BOOLV_NA: validator_old_enough;
constraint (validator_active == NA)     <-> not validator_lifecycle_applicable;
constraint (validator_exiting == NA)    <-> not validator_lifecycle_applicable;
constraint (validator_old_enough == NA) <-> not validator_lifecycle_applicable;

% Coherence: an activated, non-exiting validator is active — so old_enough
% (which implies activated) together with not-exiting forces active.
constraint (validator_old_enough == T /\ validator_exiting == F) -> (validator_active == T);
