% Realization aspect: consolidation target validator.
%
% The target only exists as a role on the consolidation path (source != target).
% Its gates: target must exist, be compounding, active, and not exiting
% (specs/electra/beacon-chain.md process_consolidation_request).
%
% Note: this is a compact, single-instance target view. The full validator
% family (validator_lifecycle/credential/...) is bound to the SOURCE; binding it
% to the target too would require parameterized (record) aspects. See README.

include "base.mzn";

var bool: target_role_applicable;               % bound to: not same_source_target
var BOOLV_NA: target_found;
var BOOLV_NA: target_compounding;
var BOOLV_NA: target_active;
var BOOLV_NA: target_exiting;

constraint (target_found == NA) <-> not target_role_applicable;
constraint (target_compounding == NA) <-> not (target_role_applicable /\ target_found == T);
constraint (target_active == NA)      <-> not (target_role_applicable /\ target_found == T);
constraint (target_exiting == NA)     <-> not (target_role_applicable /\ target_found == T);
