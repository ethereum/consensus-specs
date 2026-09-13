% Realization aspect: source-address authorization.
%
% Whether the request's source_address matches the referenced builder's
% execution_address, i.e. builder.execution_address == request.source_address
% (specs/gloas/beacon-chain.md process_builder_exit_request). Applicable only
% when a builder is resolved.

include "base.mzn";

var bool: source_authorization_applicable;
var BOOLV_NA: source_address_matches;
constraint (source_address_matches == NA) <-> not source_authorization_applicable;
