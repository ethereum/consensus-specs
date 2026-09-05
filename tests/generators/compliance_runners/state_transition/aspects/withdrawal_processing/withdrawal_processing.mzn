% Aspect: withdrawal processing (process_withdrawals aggregate).
%
% Self-contained bundle of the withdrawal_processing model and its transitive
% dependencies (builder_withdrawals/builder_sweep and base), inlined into a
% single file.
%
% Combines the pending builder/validator withdrawal presence + hit-limit
% dimensions, the builder sweep, and the validator sweep dimensions.

enum Dim = { LT, EQ, GT, F, T, NA };

set of Dim: CMP = { LT, EQ, GT };

% --- builder_withdrawals/builder_sweep ---

type BuilderSweep = record(
    var CMP: cmp_builder_count_withdrawals_limit,
    var CMP: cmp_builder_count_max_per_sweep,
    var CMP: cmp_eligible_builder_count_zero,
    var CMP: cmp_swept_count_zero,
    var CMP: cmp_swept_count_max_per_sweep,
    var CMP: cmp_next_index_zero,
    var CMP: cmp_next_index_last_builder_index,
    var {F, T}: swept_builders_hit_withdrawals_limit,
);

predicate builder_sweep_constraints(var BuilderSweep: s) =
    % Total builder count is always greater than the withdrawals limit
    s.cmp_builder_count_withdrawals_limit == GT
    % Sweep eligible builder count >= 0
    /\ s.cmp_eligible_builder_count_zero in {EQ, GT}
    % If no sweep eligible builders in the builder set
    % the swept count is zero
    /\ (s.cmp_eligible_builder_count_zero == EQ ->
            s.cmp_swept_count_zero == EQ
            /\ s.swept_builders_hit_withdrawals_limit == F)
    % Number of swept builders >= 0
    /\ s.cmp_swept_count_zero in {EQ, GT}
    % Number of swept builders < MAX_BUILDERS_PER_WITHDRAWALS_SWEEP
    /\ s.cmp_swept_count_max_per_sweep == LT
    % If a number of swept builders == 0 there is no way to hit the limit
    /\ (s.cmp_swept_count_zero == EQ ->
            s.swept_builders_hit_withdrawals_limit == F)
    % When the sweep window covers the entire builder set (bc <= max_per_sweep),
    % the sweep withdraws from some builder iff there is an eligible builder
    /\ (s.cmp_builder_count_max_per_sweep in {LT, EQ} ->
            ((s.cmp_swept_count_zero == GT)
                <-> (s.cmp_eligible_builder_count_zero == GT)))
    /\ s.cmp_next_index_zero in {EQ, GT}
    /\ s.cmp_next_index_last_builder_index in {LT, EQ}
    /\ (s.cmp_next_index_last_builder_index == EQ ->
            s.cmp_next_index_zero == GT);

% --- withdrawal_processing/withdrawal_processing ---

type WithdrawalProcessing = record(
    var {F, T}: state_latest_block_hash_match,
    var {F, T}: builder_pending_withdrawals_exist,
    var {F, T}: builder_pending_withdrawals_hit_limit,
    var {F, T}: validator_pending_withdrawals_exist,
    var {F, T}: eligible_validator_pending_withdrawals_exist,
    var {F, T}: validator_pending_withdrawals_hit_limit,
    var BuilderSweep: builder_sweep,
    var {F, T}: validators_eligible_for_sweep_exist,
    var {F, T}: swept_validators_hit_limit,
);

var WithdrawalProcessing: p;

predicate withdrawal_processing_constraints(var WithdrawalProcessing: p) =
    builder_sweep_constraints(p.builder_sweep)
    % Hitting the limit implies pending builder withdrawals exist
    /\ (p.builder_pending_withdrawals_hit_limit == T ->
            p.builder_pending_withdrawals_exist == T)
    % Eligible (withdrawable) withdrawals imply pending withdrawals exist
    /\ (p.eligible_validator_pending_withdrawals_exist == T ->
            p.validator_pending_withdrawals_exist == T)
    % Hitting the limit implies eligible withdrawals exist
    /\ (p.validator_pending_withdrawals_hit_limit == T ->
            p.eligible_validator_pending_withdrawals_exist == T)
    % If prior withdrawals exist, a swept builder implies hitting the
    % withdrawals limit by the builder sweep (in minimal configuration)
    % 1 builder pending + 1 validator pending + 1 swept builder == limit (3)
    /\ ((p.builder_pending_withdrawals_exist == T
                /\ p.eligible_validator_pending_withdrawals_exist == T
                /\ p.builder_sweep.cmp_swept_count_zero == GT) ->
            p.builder_sweep.swept_builders_hit_withdrawals_limit == T)
    % 0 builder pending + 2 validator pending + 1 swept builder == limit (3)
    /\ ((p.builder_pending_withdrawals_exist == F
                /\ p.validator_pending_withdrawals_hit_limit == T
                /\ p.builder_sweep.cmp_swept_count_zero == GT) ->
            p.builder_sweep.swept_builders_hit_withdrawals_limit == T)
    % Hitting the limit implies eligible validators for the sweep exist
    /\ (p.swept_validators_hit_limit == T ->
            p.validators_eligible_for_sweep_exist == T)
    % Swept count must be zero if the limit is already hit
    /\ ((p.builder_pending_withdrawals_hit_limit == T
                \/ (p.validator_pending_withdrawals_hit_limit == T
                    /\ p.builder_pending_withdrawals_exist == T)) ->
            p.builder_sweep.cmp_swept_count_zero == EQ)
    % Exclusivity of hitting the withdrawals limit
    /\ (p.builder_pending_withdrawals_hit_limit == T ->
            p.validator_pending_withdrawals_hit_limit == F)
    % Reduce matching failures surface
    /\ (p.state_latest_block_hash_match == F ->
            p.builder_pending_withdrawals_exist == T)
    /\ (p.state_latest_block_hash_match == F ->
            p.eligible_validator_pending_withdrawals_exist == T)
    /\ (p.state_latest_block_hash_match == F ->
            p.builder_sweep.cmp_swept_count_zero == GT)
    /\ (p.state_latest_block_hash_match == F ->
            p.swept_validators_hit_limit == T);

constraint withdrawal_processing_constraints(p);
