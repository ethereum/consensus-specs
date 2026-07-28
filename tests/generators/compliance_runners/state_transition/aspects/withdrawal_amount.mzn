% Realization aspect: withdrawal request amount.
%
% is_full_exit_request <-> amount == FULL_EXIT_REQUEST_AMOUNT (0). A zero amount
% requests a full exit; any positive amount is a partial withdrawal
% (specs/electra/beacon-chain.md process_withdrawal_request). Always applicable.

include "base.mzn";

var bool: is_full_exit_request;
