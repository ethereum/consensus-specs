% Realization aspect: validator balance thresholds (partial withdrawal).
%
%   sufficient_effective_balance <-> effective_balance >= MIN_ACTIVATION_BALANCE
%   has_excess_balance <-> balance > MIN_ACTIVATION_BALANCE + pending_balance_to_withdraw
% (specs/electra/beacon-chain.md process_withdrawal_request). Applicable when a
% validator is resolved.

include "base.mzn";

var bool: validator_balance_applicable;
var BOOLV_NA: sufficient_effective_balance;
var BOOLV_NA: has_excess_balance;
constraint (sufficient_effective_balance == NA) <-> not validator_balance_applicable;
constraint (has_excess_balance == NA)            <-> not validator_balance_applicable;
