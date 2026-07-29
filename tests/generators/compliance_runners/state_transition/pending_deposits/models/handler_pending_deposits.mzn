% Relational coverage model: process_pending_deposits (gloas).
%
% `queue_layout` is a bounded materialization shape, not an outcome. The
% independently constrained lifecycle, finalization, carried-churn, and churn
% comparison dimensions select semantic situations within that shape.

include "../../aspects/base.mzn";
include "../../aspects/validator_membership.mzn";
include "../../aspects/validator_lifecycle.mzn";

enum QueueLayout = { EMPTY, FIRST_UNFINALIZED, SINGLE, POSTPONE_THEN_ACTIVE,
                     ACTIVE_THEN_UNFINALIZED, LIMIT_AFTER_WITHDRAWN,
                     TWO_PROCESSABLE, INVALID_THEN_PROCESSABLE };
enum PrimaryRole = { ACTIVE, EXITING, WITHDRAWN, NEW_VALID, NEW_INVALID, ROLE_NA };
enum SecondaryRole = { SECOND_NONE, SECOND_ACTIVE, SECOND_UNFINALIZED, SECOND_PROCESSABLE };
enum ChurnCarry = { CARRY_ZERO, CARRY_NONZERO };
enum ChurnEffect = { CHURN_CLEARED, CHURN_RETAINED };
enum Outcome = { EMPTY_QUEUE, STOP_UNFINALIZED, STOP_PER_EPOCH_LIMIT,
                 STOP_CHURN_LIMIT, PROCESSED };

var QueueLayout: queue_layout;
var PrimaryRole: primary_role;
var SecondaryRole: secondary_role;
var ChurnCarry: initial_churn;
var BOOLV_NA: deposit_signature_valid;
var CMP_NA: primary_amount_to_available;
var CMP_NA: second_amount_to_remaining;
var CMP_NA: withdrawable_epoch_to_next_epoch;
var BOOLV_NA: validator_active;
var BOOLV_NA: validator_exiting;
var bool: primary_reached;
var Outcome: outcome;
var ChurnEffect: churn_effect;

% Queue layout binds the fixed entry positions; role and amount dimensions
% remain independent wherever the protocol can observe them.
constraint (queue_layout == EMPTY) <-> (primary_role == ROLE_NA);
constraint (queue_layout == FIRST_UNFINALIZED) -> primary_role != ROLE_NA;
constraint (queue_layout in {SINGLE, ACTIVE_THEN_UNFINALIZED, TWO_PROCESSABLE}) -> primary_role in {ACTIVE, NEW_VALID};
constraint (queue_layout == INVALID_THEN_PROCESSABLE) -> primary_role == NEW_INVALID;
constraint (queue_layout == POSTPONE_THEN_ACTIVE) -> primary_role == EXITING;
constraint (queue_layout == LIMIT_AFTER_WITHDRAWN) -> primary_role == WITHDRAWN;
constraint (queue_layout == POSTPONE_THEN_ACTIVE) <-> (secondary_role == SECOND_ACTIVE);
constraint (queue_layout == ACTIVE_THEN_UNFINALIZED) <-> (secondary_role == SECOND_UNFINALIZED);
constraint (queue_layout in {TWO_PROCESSABLE, INVALID_THEN_PROCESSABLE}) <-> (secondary_role == SECOND_PROCESSABLE);
constraint (queue_layout in {EMPTY, FIRST_UNFINALIZED, SINGLE, LIMIT_AFTER_WITHDRAWN}) <-> (secondary_role == SECOND_NONE);

constraint validator_pubkey_found <-> primary_role in {ACTIVE, EXITING, WITHDRAWN};
constraint validator_lifecycle_ok(validator_active, validator_exiting, validator_pubkey_found);
constraint (primary_role == EXITING) -> (validator_exiting == T);
constraint (primary_role == WITHDRAWN) -> (validator_exiting == T);
constraint (primary_role in {EXITING, WITHDRAWN}) -> validator_active == F;
constraint (primary_role == ACTIVE) -> (validator_exiting == F /\ validator_active == T);

constraint (withdrawable_epoch_to_next_epoch == NA) <-> not (primary_role in {EXITING, WITHDRAWN});
constraint (primary_role == WITHDRAWN) -> withdrawable_epoch_to_next_epoch == LT;
constraint (primary_role == EXITING) -> withdrawable_epoch_to_next_epoch in {EQ, GT};

constraint (deposit_signature_valid == T) <-> primary_role == NEW_VALID;
constraint (deposit_signature_valid == F) <-> primary_role == NEW_INVALID;
constraint (deposit_signature_valid == NA) <-> not (primary_role in {NEW_VALID, NEW_INVALID});
constraint (primary_amount_to_available == NA) <-> (primary_role in {EXITING, WITHDRAWN, ROLE_NA});
constraint (second_amount_to_remaining == NA) <-> not (queue_layout in {TWO_PROCESSABLE, INVALID_THEN_PROCESSABLE});
constraint (queue_layout in {TWO_PROCESSABLE, INVALID_THEN_PROCESSABLE}) -> primary_amount_to_available == LT;
constraint primary_reached <-> not (queue_layout in {EMPTY, FIRST_UNFINALIZED, LIMIT_AFTER_WITHDRAWN});

% A new invalid deposit still passes the churn check before being dropped.
constraint (queue_layout == FIRST_UNFINALIZED) -> outcome == STOP_UNFINALIZED;
constraint (queue_layout == LIMIT_AFTER_WITHDRAWN) -> outcome == STOP_PER_EPOCH_LIMIT;
constraint (queue_layout == EMPTY) -> outcome == EMPTY_QUEUE;
constraint (primary_reached /\ primary_amount_to_available == GT) -> outcome == STOP_CHURN_LIMIT;
constraint (queue_layout == ACTIVE_THEN_UNFINALIZED /\ primary_amount_to_available != GT) -> outcome == STOP_UNFINALIZED;
constraint (queue_layout in {TWO_PROCESSABLE, INVALID_THEN_PROCESSABLE} /\ second_amount_to_remaining == GT) -> outcome == STOP_CHURN_LIMIT;
constraint (primary_reached /\ primary_amount_to_available != GT /\ not (queue_layout in {ACTIVE_THEN_UNFINALIZED, TWO_PROCESSABLE, INVALID_THEN_PROCESSABLE})) -> outcome == PROCESSED;
constraint (queue_layout in {TWO_PROCESSABLE, INVALID_THEN_PROCESSABLE} /\ second_amount_to_remaining != GT) -> outcome == PROCESSED;
constraint (churn_effect == CHURN_RETAINED) <-> outcome == STOP_CHURN_LIMIT;
