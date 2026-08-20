% Aspect: execution payload bid processing (aggregate record).
%
% Bundles the builder-type classification, the builder record, and the
% bid-amount-to-zero comparison for process_execution_payload_bid
% (specs/gloas/beacon-chain.md).
% bid_processing_constraints: applies builder_constraints transitively, then
% builder_type EXTERNAL <-> is_external_builder, and bid amount comparison
% must be EQ or GT (non-negative).

include "../builder/builder.mzn";

enum BuilderType = { EXTERNAL, SELF };
enum SignatureType = { INF, VALID, INVALID };

set of OpCmp: CMP = {LT, EQ, GT};
set of OpBool: BOOL = {F, T};

type ExecutionPayloadBidProcessing = record(
    var BuilderType:    builder_type,
    var Builder:        builder,
    var CMP:            cmp_bid_value_zero,
    var SignatureType:  bid_signature,
    var CMP:            cmp_builder_balance_to_bid_value_plus_min_balance,
    var CMP:            cmp_len_kzg_commitments_max_blobs,
    var CMP:            cmp_state_slot_bid_slot,
    var BOOL:           parent_block_hash_match,
    var BOOL:           parent_block_root_match,
    var BOOL:           prev_randao_match,
);

var ExecutionPayloadBidProcessing: p;

predicate no_more_than_several_of(array[int] of var bool: bs, int: count) =
    sum(bs) == 0 \/ sum(bs) == count;

constraint builder_constraints(p.builder);
constraint (p.builder_type == EXTERNAL) <-> is_external_builder(p.builder);
constraint p.cmp_bid_value_zero in {EQ, GT};
constraint (p.builder_type == SELF) -> (p.bid_signature in {INF, INVALID});
constraint (p.builder_type == SELF) -> ((p.cmp_bid_value_zero == EQ) <-> (p.cmp_builder_balance_to_bid_value_plus_min_balance == EQ));
constraint (p.builder_type == SELF) -> ((p.cmp_bid_value_zero == GT) <-> (p.cmp_builder_balance_to_bid_value_plus_min_balance == LT));

% Coherence: when bid == 0, balance can cover iff balance >= min_deposit (v_funds in {EQ, GT}).
% When v_funds == EQ specifically, either there are pending withdrawals (shifting
% min_balance above MIN_DEPOSIT) or b_min must be EQ (balance == MIN_DEPOSIT).
constraint (p.builder_type == EXTERNAL) /\ (p.cmp_bid_value_zero == EQ) ->
    (p.cmp_builder_balance_to_bid_value_plus_min_balance in {EQ, GT});
constraint (p.builder_type == EXTERNAL) /\ (p.cmp_bid_value_zero == EQ) /\ (p.cmp_builder_balance_to_bid_value_plus_min_balance == EQ) ->
    (has_pending_withdrawals(p.builder) \/ p.builder.cmp_balance_min_deposit == EQ);
constraint (p.builder_type == EXTERNAL) /\ (p.cmp_bid_value_zero == EQ) /\ (p.cmp_builder_balance_to_bid_value_plus_min_balance == GT) ->
    (p.builder.cmp_balance_min_deposit == GT);

% When bid > 0 and balance can cover (v_funds in {EQ, GT}), balance must
% exceed min_deposit (b_min == GT).
constraint (p.builder_type == EXTERNAL) /\ (p.cmp_bid_value_zero == GT) /\ (p.cmp_builder_balance_to_bid_value_plus_min_balance in {EQ, GT}) ->
    (p.builder.cmp_balance_min_deposit == GT);

% EXTERNAL faults (at most one failing gate).
constraint (p.builder_type == EXTERNAL) -> no_more_than_several_of([
    not is_active_builder(p.builder),
    p.builder.payload_builder_version == F,
    p.cmp_builder_balance_to_bid_value_plus_min_balance == LT,
    p.bid_signature == INVALID,
    p.cmp_len_kzg_commitments_max_blobs == GT,
    p.cmp_state_slot_bid_slot in {GT, LT},
    p.parent_block_hash_match == F,
    p.parent_block_root_match == F,
    p.prev_randao_match == F,
],1);

% SELF faults (at most one failing gate; builder-specific gates excluded).
constraint (p.builder_type == SELF) -> no_more_than_several_of([
    p.cmp_builder_balance_to_bid_value_plus_min_balance == LT,
    p.bid_signature == INVALID,
    p.cmp_len_kzg_commitments_max_blobs == GT,
    p.cmp_state_slot_bid_slot in {GT, LT},
    p.parent_block_hash_match == F,
    p.parent_block_root_match == F,
    p.prev_randao_match == F,
],1);
