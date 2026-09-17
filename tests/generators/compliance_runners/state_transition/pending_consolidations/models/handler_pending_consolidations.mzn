% Relational coverage model: process_pending_consolidations (Gloas).
include "../../aspects/base.mzn";

enum QueueLayout = { EMPTY, SLASHED_ONLY, BLOCKED_ONLY, PROCESS_ONE,
                     SLASHED_THEN_PROCESS, PROCESS_THEN_BLOCKED };
enum Outcome = { EMPTY_QUEUE, SKIPPED_SLASHED, STOP_NOT_WITHDRAWABLE,
                 PROCESSED, PROCESSED_THEN_STOPPED };

var QueueLayout: queue_layout;
var CMP_NA: source_balance_to_effective;
var Outcome: outcome;

constraint (source_balance_to_effective == NA) <->
    queue_layout in {EMPTY, SLASHED_ONLY, BLOCKED_ONLY};
constraint (source_balance_to_effective in CMP) <->
    queue_layout in {PROCESS_ONE, SLASHED_THEN_PROCESS, PROCESS_THEN_BLOCKED};

constraint (queue_layout == EMPTY) <-> outcome == EMPTY_QUEUE;
constraint (queue_layout == SLASHED_ONLY) <-> outcome == SKIPPED_SLASHED;
constraint (queue_layout == BLOCKED_ONLY) <-> outcome == STOP_NOT_WITHDRAWABLE;
constraint (queue_layout in {PROCESS_ONE, SLASHED_THEN_PROCESS}) <-> outcome == PROCESSED;
constraint (queue_layout == PROCESS_THEN_BLOCKED) <-> outcome == PROCESSED_THEN_STOPPED;
