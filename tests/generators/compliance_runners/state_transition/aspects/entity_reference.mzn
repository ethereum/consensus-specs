% Realization aspect: entity reference & membership.
%
% Resolve bid.builder_index against state.builders:
%   builder_index == BUILDER_INDEX_SELF_BUILD          -> SELF_BUILD
%   index resolves to an existing builder                -> EXISTING
%   index past the registry (no builder)                 -> NON_EXISTING
% (specs/gloas/beacon-chain.md process_execution_payload_bid :1619; is_active_builder indexing)
%
% Shared with builder_exit_request / builder_deposit_request (all resolve a builder).

include "base.mzn";

enum BuilderRef = { SELF_BUILD, EXISTING, NON_EXISTING };
var BuilderRef: builder_ref;

var bool: self_build;
var bool: external_bid;
var bool: builder_found;
constraint self_build    <-> (builder_ref == SELF_BUILD);
constraint external_bid  <-> (builder_ref != SELF_BUILD);
constraint builder_found <-> (builder_ref == EXISTING);
