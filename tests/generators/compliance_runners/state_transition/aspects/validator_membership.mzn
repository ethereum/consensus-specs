% Realization aspect: validator membership by public key.
%
% Whether request.validator_pubkey resolves to an existing validator in
% state.validators. Shared by the pubkey-addressed validator handlers
% (withdrawal_request, consolidation_request, voluntary_exit).

include "base.mzn";

var bool: validator_pubkey_found;
