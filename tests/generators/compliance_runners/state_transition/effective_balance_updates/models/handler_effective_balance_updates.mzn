% Relational coverage model: process_effective_balance_updates (Gloas).
enum Scenario = { STABLE_STANDARD, DOWNWARD_STANDARD, UPWARD_STANDARD,
                  CAPPED_STANDARD, UPWARD_COMPOUNDING };
enum CredentialType = { STANDARD, COMPOUNDING };
enum HysteresisResult = { NO_CHANGE, DOWNWARD, UPWARD, CAPPED };
enum BalanceAlignment = { EXACT_INCREMENT, ROUNDED_DOWN };
enum Outcome = { UNCHANGED, EFFECTIVE_BALANCE_UPDATED, EFFECTIVE_BALANCE_CAPPED };

var Scenario: scenario;
var CredentialType: credential_type;
var HysteresisResult: hysteresis_result;
var BalanceAlignment: balance_alignment;
var Outcome: outcome;

constraint (credential_type == COMPOUNDING) <-> scenario == UPWARD_COMPOUNDING;
constraint (credential_type == STANDARD) <-> scenario != UPWARD_COMPOUNDING;
constraint (hysteresis_result == NO_CHANGE) <-> scenario == STABLE_STANDARD;
constraint (hysteresis_result == DOWNWARD) <-> scenario == DOWNWARD_STANDARD;
constraint (hysteresis_result == UPWARD) <-> scenario in {UPWARD_STANDARD, UPWARD_COMPOUNDING};
constraint (hysteresis_result == CAPPED) <-> scenario == CAPPED_STANDARD;
constraint (balance_alignment == ROUNDED_DOWN) <-> scenario in {
    DOWNWARD_STANDARD, UPWARD_STANDARD, UPWARD_COMPOUNDING
};
constraint (balance_alignment == EXACT_INCREMENT) <-> not (
    scenario in {DOWNWARD_STANDARD, UPWARD_STANDARD, UPWARD_COMPOUNDING}
);
constraint (scenario == STABLE_STANDARD) <-> outcome == UNCHANGED;
constraint (scenario in {DOWNWARD_STANDARD, UPWARD_STANDARD, UPWARD_COMPOUNDING}) <-> outcome == EFFECTIVE_BALANCE_UPDATED;
constraint (scenario == CAPPED_STANDARD) <-> outcome == EFFECTIVE_BALANCE_CAPPED;
