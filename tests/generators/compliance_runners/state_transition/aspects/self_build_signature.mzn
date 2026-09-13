% Realization aspect: self-build signature sentinel (parameterized).
%
% For self-builds the signature must equal bls.G2_POINT_AT_INFINITY rather than a
% real signature (specs/gloas/beacon-chain.md process_execution_payload_bid).

include "base.mzn";

predicate self_build_signature_ok(var Dim: is_infinity, var bool: applicable) =
    (is_infinity == NA <-> not applicable);
