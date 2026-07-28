% Realization aspect: builder message signature validity (parameterized).
%
% A boolean coverage dimension: does the message carry a valid builder signature?
% The handler binds which signature and its applicability — e.g.
% verify_execution_payload_bid_signature for a bid,
% is_valid_builder_deposit_signature for a builder deposit. Shared across signed
% builder handlers.

include "base.mzn";

predicate signed_message_ok(var Dim: valid, var bool: applicable) =
    (valid == NA <-> not applicable);
