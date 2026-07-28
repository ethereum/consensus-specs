% Realization aspect: pending-partial-withdrawals queue capacity.
%
% partial_queue_full <-> len(state.pending_partial_withdrawals) == PENDING_PARTIAL_WITHDRAWALS_LIMIT
% (specs/electra/beacon-chain.md process_withdrawal_request). A full queue blocks
% partial requests only (full exits still process). Always applicable.

include "base.mzn";

var bool: partial_queue_full;
