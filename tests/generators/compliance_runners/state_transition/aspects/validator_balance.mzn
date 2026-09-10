% Realization aspect: validator balance thresholds (partial withdrawal).
%
% `effective_balance_to_min_activation` compares effective balance with the
% activation threshold; `balance_to_required` compares balance with
% MIN_ACTIVATION_BALANCE + pending_balance_to_withdraw. Derived predicates
% preserve the handler's >= and > gates.
% (specs/electra/beacon-chain.md process_withdrawal_request). Applicable when a
% validator is resolved.

include "base.mzn";

var bool: validator_balance_applicable;
var CMP_NA: effective_balance_to_min_activation;
var CMP_NA: balance_to_required;
constraint (effective_balance_to_min_activation == NA) <-> not validator_balance_applicable;
constraint (balance_to_required == NA)                 <-> not validator_balance_applicable;

var BOOLV_NA: sufficient_effective_balance;
var BOOLV_NA: has_excess_balance;
constraint (sufficient_effective_balance == T) <-> effective_balance_to_min_activation in {EQ, GT};
constraint (sufficient_effective_balance == F) <-> effective_balance_to_min_activation == LT;
constraint (sufficient_effective_balance == NA) <-> effective_balance_to_min_activation == NA;
constraint (has_excess_balance == T) <-> balance_to_required == GT;
constraint (has_excess_balance == F) <-> balance_to_required in {LT, EQ};
constraint (has_excess_balance == NA) <-> balance_to_required == NA;
