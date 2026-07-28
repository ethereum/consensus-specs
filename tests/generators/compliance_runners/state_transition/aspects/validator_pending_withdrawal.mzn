% Realization aspect: validator pending partial withdrawals.
%
% has_pending_partial_withdrawal <-> get_pending_balance_to_withdraw(state, index) > 0
% (sum of pending_partial_withdrawals for the validator; specs/electra). Applicable
% when a validator is resolved.

include "base.mzn";

var bool: validator_pending_applicable;
var BOOLV_NA: has_pending_partial_withdrawal;
constraint (has_pending_partial_withdrawal == NA) <-> not validator_pending_applicable;
