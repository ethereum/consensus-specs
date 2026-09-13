% Realization aspect: pending-consolidations queue capacity.
%
% `pending_consolidations_capacity` distinguishes an empty queue, an available
% non-empty queue, and a full queue. `pending_consolidations_full` is the
% derived handler gate. A full queue satisfies
% len(state.pending_consolidations) == PENDING_CONSOLIDATIONS_LIMIT
% (specs/electra/beacon-chain.md process_consolidation_request). Always applicable.

include "queue_capacity.mzn";

var QueueCapacity: pending_consolidations_capacity;
var bool: pending_consolidations_full;
constraint queue_capacity_ok(pending_consolidations_capacity, pending_consolidations_full);
