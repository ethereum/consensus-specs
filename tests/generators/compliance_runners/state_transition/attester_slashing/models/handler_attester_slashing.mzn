% Relational coverage model: process_attester_slashing (Gloas).
include "../../aspects/base.mzn";

enum Scenario = { VALID_ONE, VALID_TWO, VALID_THREE, NOT_SLASHABLE,
                  INVALID_FIRST_SIGNATURE, INVALID_EMPTY_INDICES,
                  INVALID_SECOND_SIGNATURE, NO_SLASHABLE_INTERSECTION };
enum Outcome = { ACCEPT, REJECT_NOT_SLASHABLE, REJECT_FIRST_ATTESTATION,
                 REJECT_MALFORMED_FIRST_INDICES, REJECT_SECOND_ATTESTATION,
                 REJECT_NO_SLASHABLE_INTERSECTION };
enum IntersectionSize = { NONE, ONE, TWO, THREE_OR_MORE };

var Scenario: scenario;
var bool: attestation_data_slashable;
var bool: attestation_1_indices_well_formed;
var bool: attestation_1_valid;
var bool: attestation_2_valid;
var IntersectionSize: intersection_size;
var bool: slashable_intersection;
var Outcome: outcome;

constraint attestation_data_slashable <-> scenario != NOT_SLASHABLE;
constraint attestation_1_indices_well_formed <-> scenario != INVALID_EMPTY_INDICES;
constraint attestation_1_valid <-> not (scenario in {INVALID_FIRST_SIGNATURE, INVALID_EMPTY_INDICES});
constraint attestation_2_valid <-> scenario != INVALID_SECOND_SIGNATURE;
constraint slashable_intersection <-> not (
    scenario in {INVALID_EMPTY_INDICES, NO_SLASHABLE_INTERSECTION}
);
constraint (intersection_size == NONE) <-> scenario == INVALID_EMPTY_INDICES;
constraint (intersection_size == TWO) <-> scenario == VALID_TWO;
constraint (intersection_size == THREE_OR_MORE) <-> scenario == VALID_THREE;
constraint (intersection_size == ONE) <-> not (
    scenario in {VALID_TWO, VALID_THREE, INVALID_EMPTY_INDICES}
);

constraint (scenario in {VALID_ONE, VALID_TWO, VALID_THREE}) <-> outcome == ACCEPT;
constraint (scenario == NOT_SLASHABLE) <-> outcome == REJECT_NOT_SLASHABLE;
constraint (scenario == INVALID_FIRST_SIGNATURE) <-> outcome == REJECT_FIRST_ATTESTATION;
constraint (scenario == INVALID_EMPTY_INDICES) <-> outcome == REJECT_MALFORMED_FIRST_INDICES;
constraint (scenario == INVALID_SECOND_SIGNATURE) <-> outcome == REJECT_SECOND_ATTESTATION;
constraint (scenario == NO_SLASHABLE_INTERSECTION) <-> outcome == REJECT_NO_SLASHABLE_INTERSECTION;
