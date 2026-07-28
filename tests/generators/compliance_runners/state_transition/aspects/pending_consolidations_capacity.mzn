% Realization aspect: pending-consolidations queue capacity.
%
% pending_consolidations_full <-> len(state.pending_consolidations) == PENDING_CONSOLIDATIONS_LIMIT
% (specs/electra/beacon-chain.md process_consolidation_request). Always applicable.

include "base.mzn";

var bool: pending_consolidations_full;
