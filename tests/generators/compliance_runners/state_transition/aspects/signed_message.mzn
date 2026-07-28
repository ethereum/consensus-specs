% Realization aspect: builder message signature validity.
%
% A boolean coverage dimension: does the message carry a valid builder signature
% from the relevant key? The handler binds *which* signature and its
% applicability — e.g. verify_execution_payload_bid_signature for a bid,
% is_valid_builder_deposit_signature for a builder deposit. Shared across signed
% builder handlers.

include "base.mzn";

var bool: builder_signature_applicable;
var BOOLV_NA: builder_signature_valid;
constraint (builder_signature_valid == NA) <-> not builder_signature_applicable;
