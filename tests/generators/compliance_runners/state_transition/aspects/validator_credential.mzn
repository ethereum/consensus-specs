% Realization aspect: validator withdrawal-credential kind.
%
% withdrawal_credentials[:1]: BLS (0x00), ETH1 (0x01), or COMPOUNDING (0x02).
%   has_execution_withdrawal_credential  <-> ETH1 or COMPOUNDING
%   has_compounding_withdrawal_credential <-> COMPOUNDING
% (specs/electra/beacon-chain.md). Applicable when a validator is resolved.
% Shared by withdrawal_request and consolidation_request.

include "base.mzn";

enum ValidatorCredential = { CRED_BLS, CRED_ETH1, CRED_COMPOUNDING, CRED_NA };

var bool: validator_credential_applicable;
var ValidatorCredential: validator_credential;
constraint (validator_credential == CRED_NA) <-> not validator_credential_applicable;

var bool: validator_has_execution_credential;
var bool: validator_has_compounding_credential;
constraint validator_has_execution_credential <->
    (validator_credential in {CRED_ETH1, CRED_COMPOUNDING});
constraint validator_has_compounding_credential <->
    (validator_credential == CRED_COMPOUNDING);
