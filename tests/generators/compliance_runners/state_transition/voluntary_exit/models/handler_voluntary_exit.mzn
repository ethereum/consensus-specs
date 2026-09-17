% Relational coverage model: process_voluntary_exit (Gloas).
enum Scenario = { VALID, VALID_CARRIED_CHURN, VALID_EXHAUSTED_CHURN, INACTIVE,
                  ALREADY_EXITED, FUTURE_EXIT_EPOCH, TOO_YOUNG, PENDING_WITHDRAWAL,
                  INVALID_SIGNATURE };
enum Outcome = { ACCEPT, REJECT_INACTIVE, REJECT_ALREADY_EXITED,
                 REJECT_EXIT_EPOCH, REJECT_TOO_YOUNG, REJECT_PENDING_WITHDRAWAL,
                 REJECT_SIGNATURE };
enum ExitChurnState = { NEW_EPOCH, CARRIED_AVAILABLE, CARRIED_EXHAUSTED };

var Scenario: scenario;
var bool: validator_active;
var bool: exit_not_initiated;
var bool: exit_epoch_valid;
var bool: active_long_enough;
var ExitChurnState: exit_churn_state;
var bool: no_pending_withdrawal;
var bool: signature_valid;
var Outcome: outcome;

constraint validator_active <-> scenario != INACTIVE;
constraint exit_not_initiated <-> scenario != ALREADY_EXITED;
constraint exit_epoch_valid <-> scenario != FUTURE_EXIT_EPOCH;
constraint active_long_enough <-> not (scenario in {INACTIVE, TOO_YOUNG});
constraint no_pending_withdrawal <-> scenario != PENDING_WITHDRAWAL;
constraint signature_valid <-> scenario != INVALID_SIGNATURE;
constraint (exit_churn_state == CARRIED_AVAILABLE) <-> scenario == VALID_CARRIED_CHURN;
constraint (exit_churn_state == CARRIED_EXHAUSTED) <-> scenario == VALID_EXHAUSTED_CHURN;
constraint (exit_churn_state == NEW_EPOCH) <-> not (
    scenario in {VALID_CARRIED_CHURN, VALID_EXHAUSTED_CHURN}
);

constraint (scenario in {VALID, VALID_CARRIED_CHURN, VALID_EXHAUSTED_CHURN}) <-> outcome == ACCEPT;
constraint (scenario == INACTIVE) <-> outcome == REJECT_INACTIVE;
constraint (scenario == ALREADY_EXITED) <-> outcome == REJECT_ALREADY_EXITED;
constraint (scenario == FUTURE_EXIT_EPOCH) <-> outcome == REJECT_EXIT_EPOCH;
constraint (scenario == TOO_YOUNG) <-> outcome == REJECT_TOO_YOUNG;
constraint (scenario == PENDING_WITHDRAWAL) <-> outcome == REJECT_PENDING_WITHDRAWAL;
constraint (scenario == INVALID_SIGNATURE) <-> outcome == REJECT_SIGNATURE;
