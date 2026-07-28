% Realization aspect: validator withdrawal-credential kind (parameterized).
%
% withdrawal_credentials[:1]: BLS (0x00), ETH1 (0x01), or COMPOUNDING (0x02).
% Parameterized as a predicate over a credential var + derived-value functions,
% instantiable per role (source, target). The handler declares a role-prefixed
% `var ValidatorCredentialKind` and exposes the derived booleans it needs.

include "base.mzn";

enum ValidatorCredentialKind = { CRED_BLS, CRED_ETH1, CRED_COMPOUNDING, CRED_NA };

predicate validator_credential_ok(var ValidatorCredentialKind: c, var bool: applicable) =
    (c == CRED_NA <-> not applicable);

function var bool: cred_has_execution(var ValidatorCredentialKind: c) =
    c in {CRED_ETH1, CRED_COMPOUNDING};
function var bool: cred_has_compounding(var ValidatorCredentialKind: c) =
    c == CRED_COMPOUNDING;
function var bool: cred_is_eth1(var ValidatorCredentialKind: c) =
    c == CRED_ETH1;
