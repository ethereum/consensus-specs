% Realization aspect: withdrawal-credential prefix.
%
% is_builder_withdrawal_credential(request.withdrawal_credentials):
%   withdrawal_credentials[:1] == BUILDER_WITHDRAWAL_PREFIX (0xB0)
% (specs/gloas/beacon-chain.md is_builder_withdrawal_credential).

include "base.mzn";

var bool: wc_is_builder_prefix;
