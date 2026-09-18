% Realization aspect: builder membership by public key.
%
% Whether request.pubkey resolves to an existing builder in state.builders
% (specs/gloas/beacon-chain.md process_builder_exit_request / process_builder_deposit_request).
% Shared by the pubkey-addressed builder handlers.

include "base.mzn";

var bool: builder_pubkey_found;
