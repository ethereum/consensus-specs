% Realization aspect: signed message.
%
% External bid: verify_execution_payload_bid_signature — BLS over builder.pubkey
%   under DOMAIN_BEACON_BUILDER (specs/gloas/beacon-chain.md :1598, :1630).
% Self build: signed_bid.signature == bls.G2_POINT_AT_INFINITY (:1621).
%
% The two dimensions have complementary applicability (external vs self-build).

include "base.mzn";

var bool: builder_signature_applicable;
var bool: self_build_signature_applicable;

var BOOLV_NA: builder_signature_valid;             % external: BLS verify result
var BOOLV_NA: self_build_signature_is_infinity;     % self: signature == G2_POINT_AT_INFINITY

constraint (builder_signature_valid == NA)          <-> not builder_signature_applicable;
constraint (self_build_signature_is_infinity == NA) <-> not self_build_signature_applicable;
