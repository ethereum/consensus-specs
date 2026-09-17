% Relational coverage model: process_bls_to_execution_change (Gloas).
enum Scenario = { VALID, OUT_OF_RANGE, NON_BLS_CREDENTIAL, PUBKEY_MISMATCH,
                  INVALID_SIGNATURE };
enum Outcome = { ACCEPT, REJECT_INDEX, REJECT_CREDENTIAL_PREFIX,
                 REJECT_PUBKEY_MISMATCH, REJECT_SIGNATURE };

var Scenario: scenario;
var bool: validator_index_in_range;
var bool: has_bls_withdrawal_credential;
var bool: from_pubkey_matches;
var bool: signature_valid;
var Outcome: outcome;

constraint validator_index_in_range <-> scenario != OUT_OF_RANGE;
constraint has_bls_withdrawal_credential <-> not (
    scenario in {OUT_OF_RANGE, NON_BLS_CREDENTIAL}
);
constraint from_pubkey_matches <-> not (
    scenario in {OUT_OF_RANGE, NON_BLS_CREDENTIAL, PUBKEY_MISMATCH}
);
constraint signature_valid <-> scenario != INVALID_SIGNATURE;

constraint (scenario == VALID) <-> outcome == ACCEPT;
constraint (scenario == OUT_OF_RANGE) <-> outcome == REJECT_INDEX;
constraint (scenario == NON_BLS_CREDENTIAL) <-> outcome == REJECT_CREDENTIAL_PREFIX;
constraint (scenario == PUBKEY_MISMATCH) <-> outcome == REJECT_PUBKEY_MISMATCH;
constraint (scenario == INVALID_SIGNATURE) <-> outcome == REJECT_SIGNATURE;
