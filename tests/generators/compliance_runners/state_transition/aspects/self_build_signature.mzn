% Realization aspect: self-build signature sentinel (execution_payload_bid).
%
% For self-builds the signature must equal bls.G2_POINT_AT_INFINITY rather than a
% real signature (specs/gloas/beacon-chain.md process_execution_payload_bid).
% Complements signed_message on the self-build branch.

include "base.mzn";

var bool: self_build_signature_applicable;
var BOOLV_NA: self_build_signature_is_infinity;
constraint (self_build_signature_is_infinity == NA) <-> not self_build_signature_applicable;
