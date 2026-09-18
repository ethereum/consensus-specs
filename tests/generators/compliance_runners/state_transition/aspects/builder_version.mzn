% Realization aspect: builder version (parameterized).
%
% state.builders[builder_index].version == PAYLOAD_BUILDER_VERSION
% (specs/gloas/beacon-chain.md process_execution_payload_bid). Single guarded
% boolean; the handler exposes the coverage dimension var and applies the guard.

include "base.mzn";

predicate builder_version_ok(var Dim: valid, var bool: applicable) =
    (valid == NA <-> not applicable);
