% Realization aspect: withdrawal-credential profile.
%
% withdrawal_credentials[:1]: BLS (0x00), ETH1 (0x01), COMPOUNDING (0x02), or
% BUILDER (0xB0). The builder predicate is derived from this profile.
% (specs/gloas/beacon-chain.md withdrawal credential prefixes).

include "base.mzn";

enum WithdrawalCredentialsProfile = { BLS, ETH1, COMPOUNDING, BUILDER };

var WithdrawalCredentialsProfile: withdrawal_credentials_profile;
var bool: wc_is_builder_prefix;
constraint wc_is_builder_prefix <-> withdrawal_credentials_profile == BUILDER;
