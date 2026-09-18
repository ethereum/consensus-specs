% Relational coverage model: process_slashings (Gloas).
enum Scenario = { UNSLASHED, SLASHED_NOT_DUE, ZERO, PARTIAL, FULL, UNDERFLOW };
enum ValidatorStatus = { UNSLASHED_VALIDATOR, SLASHED_WAITING, SLASHED_DUE };
enum TotalSlashings = { ZERO_TOTAL, PARTIAL_TOTAL, SATURATED_TOTAL };
enum PenaltyOutcome = { NO_PENALTY, PARTIAL_PENALTY, FULL_PENALTY, UNDERFLOW_TO_ZERO };
enum Outcome = { NO_STATE_CHANGE, BALANCE_DECREASED, BALANCE_ZEROED };

var Scenario: scenario;
var ValidatorStatus: validator_status;
var TotalSlashings: total_slashings;
var PenaltyOutcome: penalty_outcome;
var Outcome: outcome;

constraint (validator_status == UNSLASHED_VALIDATOR) <-> scenario == UNSLASHED;
constraint (validator_status == SLASHED_WAITING) <-> scenario == SLASHED_NOT_DUE;
constraint (validator_status == SLASHED_DUE) <-> not (
    scenario in {UNSLASHED, SLASHED_NOT_DUE}
);
constraint (total_slashings == ZERO_TOTAL) <-> scenario == ZERO;
constraint (total_slashings == PARTIAL_TOTAL) <-> scenario == PARTIAL;
constraint (total_slashings == SATURATED_TOTAL) <-> not (scenario in {ZERO, PARTIAL});
constraint (penalty_outcome == NO_PENALTY) <-> scenario in {UNSLASHED, SLASHED_NOT_DUE, ZERO};
constraint (penalty_outcome == PARTIAL_PENALTY) <-> scenario == PARTIAL;
constraint (penalty_outcome == FULL_PENALTY) <-> scenario == FULL;
constraint (penalty_outcome == UNDERFLOW_TO_ZERO) <-> scenario == UNDERFLOW;
constraint (outcome == NO_STATE_CHANGE) <-> scenario in {UNSLASHED, SLASHED_NOT_DUE, ZERO};
constraint (outcome == BALANCE_DECREASED) <-> scenario == PARTIAL;
constraint (outcome == BALANCE_ZEROED) <-> scenario in {FULL, UNDERFLOW};
