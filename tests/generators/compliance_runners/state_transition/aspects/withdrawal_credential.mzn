% Realization aspect: withdrawal-credential profile (parameterized).
%
% withdrawal_credentials[:1]: BLS (0x00), ETH1 (0x01), COMPOUNDING (0x02),
% BUILDER (0xB0), or another prefix. `NA` marks an unresolved role. The
% predicates are reusable for request fields and referenced validators/builders.
% (specs/gloas/beacon-chain.md withdrawal credential prefixes).

include "base.mzn";

enum WithdrawalCredentialProfile = { BLS, ETH1, COMPOUNDING, BUILDER, OTHER, CRED_NA };

predicate withdrawal_credential_ok(var WithdrawalCredentialProfile: c, var bool: applicable) =
    (c == CRED_NA <-> not applicable);

function var bool: cred_has_execution(var WithdrawalCredentialProfile: c) =
    c in {ETH1, COMPOUNDING};
function var bool: cred_has_compounding(var WithdrawalCredentialProfile: c) =
    c == COMPOUNDING;
function var bool: cred_is_eth1(var WithdrawalCredentialProfile: c) =
    c == ETH1;
function var bool: cred_is_builder(var WithdrawalCredentialProfile: c) =
    c == BUILDER;
