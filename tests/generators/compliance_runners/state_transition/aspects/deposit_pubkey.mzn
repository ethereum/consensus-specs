% Realization aspect: deposit request pubkey membership.
%
% pubkey_is_existing_validator <-> request.pubkey matches some state.validators[i].pubkey.
% process_deposit_request copies the request verbatim into a PendingDeposit and
% does NOT branch on this — pure input/output coverage. Always applicable.

include "base.mzn";

var bool: pubkey_is_existing_validator;
