% Realization aspect: builder version.
%
% Spec: state.builders[builder_index].version == PAYLOAD_BUILDER_VERSION
% (specs/gloas/beacon-chain.md process_execution_payload_bid :1626)

include "base.mzn";

var bool: builder_version_applicable;
var BOOLV_NA: builder_version_valid;
constraint (builder_version_valid == NA) <-> not builder_version_applicable;
