% Handler model: process_execution_payload_bid (aggregate bid_processing aspect).
%
% Includes the bid_processing aggregate aspect's constraints, adds handler-local
% dimensions (amount_positive, state_slot_past_genesis), derives the outcome
% (first-failing gate in spec order), per-gate faults, effects, and trace
% dimensions. No solve item — a coverage model drives solving.
%
% All dimensions are declared as flat top-level vars (not nested in a record)
% so the coverage engine (enumerate_signatures) can read them via getattr.
%
% Spec: specs/gloas/beacon-chain.md process_execution_payload_bid (:1611).

include "../../aspects/builder/builder.mzn";

% ---- Enums (from bid_processing aspect) ------------------------------------
enum BuilderType = { EXTERNAL, SELF };
enum SignatureType = { INF, VALID, INVALID };

% Sub-domains (from bid_processing aspect; CMP/BOOL are subsets of OpCmp/OpBool)
set of OpCmp: CMP  = { LT, EQ, GT };
set of OpBool: BOOL = { F, T };

% ---- Flat dimension vars ---------------------------------------------------
% Builder sub-dimensions (from the Builder record)
var OpBool: payload_builder_version;
var OpCmp:  cmp_state_epoch_deposit_epoch;
var OpCmp:  cmp_state_epoch_withdrawal_epoch;
var OpCmp:  cmp_finalized_epoch_deposit_epoch;
var OpBool: withdrawable_epoch_set;
var OpCmp:  cmp_balance_zero;
var OpCmp:  cmp_balance_min_deposit;
var OpBool: has_pending_payments;
var OpBool: has_pending_withdrawals;

% Bid-processing dimensions
var BuilderType:    builder_type;
var CMP:            cmp_bid_value_zero;
var SignatureType:  bid_signature;
var CMP:            cmp_builder_balance_to_bid_value_plus_min_balance;
var CMP:            cmp_len_kzg_commitments_max_blobs;
var CMP:            cmp_state_slot_bid_slot;
var BOOL:           parent_block_hash_match;
var BOOL:           parent_block_root_match;
var BOOL:           prev_randao_match;

% Handler-local dimensions
var bool: amount_positive;
var bool: state_slot_past_genesis;
constraint state_slot_past_genesis = true;

% ---- Builder predicates (from builder.mzn) ----------------------------------
predicate is_self_builder(var OpBool: pv, var OpCmp: sd, var OpCmp: sw, var OpCmp: fd,
                           var OpBool: ws, var OpCmp: bz, var OpCmp: bm, var OpBool: pp, var OpBool: pw) =
    pv == NA_BOOL /\ sd == NA_CMP /\ sw == NA_CMP /\ fd == NA_CMP
    /\ ws == NA_BOOL /\ bz == NA_CMP /\ bm == NA_CMP
    /\ pp == NA_BOOL /\ pw == NA_BOOL;

predicate is_external_builder(var OpBool: pv, var OpCmp: sd, var OpCmp: sw, var OpCmp: fd,
                              var OpBool: ws, var OpCmp: bz, var OpCmp: bm, var OpBool: pp, var OpBool: pw) =
    pv != NA_BOOL /\ sd != NA_CMP /\ sw != NA_CMP /\ fd != NA_CMP
    /\ ws != NA_BOOL /\ bz != NA_CMP /\ bm != NA_CMP
    /\ pp != NA_BOOL /\ pw != NA_BOOL;

predicate is_active_builder(var OpCmp: fd, var OpBool: ws) =
    fd == GT /\ ws == F;

predicate has_pending_withdrawals_pred(var OpBool: pp, var OpBool: pw) =
    pp == T \/ pw == T;

% ---- Builder constraints (from builder.mzn) ----------------------------------
constraint (not is_self_builder(payload_builder_version, cmp_state_epoch_deposit_epoch,
    cmp_state_epoch_withdrawal_epoch, cmp_finalized_epoch_deposit_epoch,
    withdrawable_epoch_set, cmp_balance_zero, cmp_balance_min_deposit,
    has_pending_payments, has_pending_withdrawals))
    <-> is_external_builder(payload_builder_version, cmp_state_epoch_deposit_epoch,
        cmp_state_epoch_withdrawal_epoch, cmp_finalized_epoch_deposit_epoch,
        withdrawable_epoch_set, cmp_balance_zero, cmp_balance_min_deposit,
        has_pending_payments, has_pending_withdrawals);

constraint (not is_self_builder(payload_builder_version, cmp_state_epoch_deposit_epoch,
    cmp_state_epoch_withdrawal_epoch, cmp_finalized_epoch_deposit_epoch,
    withdrawable_epoch_set, cmp_balance_zero, cmp_balance_min_deposit,
    has_pending_payments, has_pending_withdrawals))
    -> (cmp_state_epoch_deposit_epoch in {EQ, GT});

constraint (not is_self_builder(payload_builder_version, cmp_state_epoch_deposit_epoch,
    cmp_state_epoch_withdrawal_epoch, cmp_finalized_epoch_deposit_epoch,
    withdrawable_epoch_set, cmp_balance_zero, cmp_balance_min_deposit,
    has_pending_payments, has_pending_withdrawals))
    -> (cmp_balance_zero in {EQ, GT});

constraint (not is_self_builder(payload_builder_version, cmp_state_epoch_deposit_epoch,
    cmp_state_epoch_withdrawal_epoch, cmp_finalized_epoch_deposit_epoch,
    withdrawable_epoch_set, cmp_balance_zero, cmp_balance_min_deposit,
    has_pending_payments, has_pending_withdrawals))
    -> ((cmp_balance_zero == EQ) <-> (cmp_balance_min_deposit == LT));

constraint (not is_self_builder(payload_builder_version, cmp_state_epoch_deposit_epoch,
    cmp_state_epoch_withdrawal_epoch, cmp_finalized_epoch_deposit_epoch,
    withdrawable_epoch_set, cmp_balance_zero, cmp_balance_min_deposit,
    has_pending_payments, has_pending_withdrawals))
    -> (is_active_builder(cmp_finalized_epoch_deposit_epoch, withdrawable_epoch_set)
        -> (cmp_balance_min_deposit in {EQ, GT}));

constraint (not is_self_builder(payload_builder_version, cmp_state_epoch_deposit_epoch,
    cmp_state_epoch_withdrawal_epoch, cmp_finalized_epoch_deposit_epoch,
    withdrawable_epoch_set, cmp_balance_zero, cmp_balance_min_deposit,
    has_pending_payments, has_pending_withdrawals))
    -> (has_pending_withdrawals_pred(has_pending_payments, has_pending_withdrawals)
        -> is_active_builder(cmp_finalized_epoch_deposit_epoch, withdrawable_epoch_set));

constraint (not is_self_builder(payload_builder_version, cmp_state_epoch_deposit_epoch,
    cmp_state_epoch_withdrawal_epoch, cmp_finalized_epoch_deposit_epoch,
    withdrawable_epoch_set, cmp_balance_zero, cmp_balance_min_deposit,
    has_pending_payments, has_pending_withdrawals))
    -> (has_pending_withdrawals_pred(has_pending_payments, has_pending_withdrawals)
        -> (cmp_balance_min_deposit == GT));

constraint (not is_self_builder(payload_builder_version, cmp_state_epoch_deposit_epoch,
    cmp_state_epoch_withdrawal_epoch, cmp_finalized_epoch_deposit_epoch,
    withdrawable_epoch_set, cmp_balance_zero, cmp_balance_min_deposit,
    has_pending_payments, has_pending_withdrawals))
    -> ((withdrawable_epoch_set == F) -> (cmp_state_epoch_withdrawal_epoch == LT));

% ---- Bid processing constraints (from bid_processing.mzn) ---------------------
constraint (builder_type == EXTERNAL) <-> is_external_builder(payload_builder_version,
    cmp_state_epoch_deposit_epoch, cmp_state_epoch_withdrawal_epoch, cmp_finalized_epoch_deposit_epoch,
    withdrawable_epoch_set, cmp_balance_zero, cmp_balance_min_deposit,
    has_pending_payments, has_pending_withdrawals);
constraint cmp_bid_value_zero in {EQ, GT};
constraint (builder_type == SELF) -> (bid_signature in {INF, INVALID});
constraint (builder_type == SELF) -> ((cmp_bid_value_zero == EQ) <-> (cmp_builder_balance_to_bid_value_plus_min_balance == EQ));
constraint (builder_type == SELF) -> ((cmp_bid_value_zero == GT) <-> (cmp_builder_balance_to_bid_value_plus_min_balance == LT));

% Coherence (from bid_processing.mzn)
constraint (builder_type == EXTERNAL) /\ (cmp_bid_value_zero == EQ) ->
    (cmp_builder_balance_to_bid_value_plus_min_balance in {EQ, GT});
constraint (builder_type == EXTERNAL) /\ (cmp_bid_value_zero == EQ) /\ (cmp_builder_balance_to_bid_value_plus_min_balance == EQ) ->
    (has_pending_withdrawals_pred(has_pending_payments, has_pending_withdrawals) \/ cmp_balance_min_deposit == EQ);
constraint (builder_type == EXTERNAL) /\ (cmp_bid_value_zero == EQ) /\ (cmp_builder_balance_to_bid_value_plus_min_balance == GT) ->
    (cmp_balance_min_deposit == GT);
constraint (builder_type == EXTERNAL) /\ (cmp_bid_value_zero == GT) /\ (cmp_builder_balance_to_bid_value_plus_min_balance in {EQ, GT}) ->
    (cmp_balance_min_deposit == GT);

% no_more_than_several_of (from bid_processing.mzn)
predicate no_more_than_several_of(array[int] of var bool: bs, int: count) =
    sum(bs) == 0 \/ sum(bs) == count;

constraint (builder_type == EXTERNAL) -> no_more_than_several_of([
    not is_active_builder(cmp_finalized_epoch_deposit_epoch, withdrawable_epoch_set),
    payload_builder_version == F,
    cmp_builder_balance_to_bid_value_plus_min_balance == LT,
    bid_signature == INVALID,
    cmp_len_kzg_commitments_max_blobs == GT,
    cmp_state_slot_bid_slot in {GT, LT},
    parent_block_hash_match == F,
    parent_block_root_match == F,
    prev_randao_match == F,
],1);

constraint (builder_type == SELF) -> no_more_than_several_of([
    cmp_builder_balance_to_bid_value_plus_min_balance == LT,
    bid_signature == INVALID,
    cmp_len_kzg_commitments_max_blobs == GT,
    cmp_state_slot_bid_slot in {GT, LT},
    parent_block_hash_match == F,
    parent_block_root_match == F,
    prev_randao_match == F,
],1);

% ---- Handler-local constraint -----------------------------------------------
constraint amount_positive <-> (cmp_bid_value_zero == GT);

% ---- Gate pass predicates (spec order) ---------------------------------------
var bool: g_self_amount_ok = not amount_positive;
var bool: g_self_sig_ok    = bid_signature == INF;

var bool: g_active  = is_active_builder(cmp_finalized_epoch_deposit_epoch, withdrawable_epoch_set);
var bool: g_version = payload_builder_version == T;

var bool: g_funds =
    if builder_type == SELF then true
    elseif cmp_builder_balance_to_bid_value_plus_min_balance == LT then false
    else true
    endif;
var bool: g_sig     = bid_signature == VALID;

var bool: g_kzg     = cmp_len_kzg_commitments_max_blobs in {LT, EQ};
var bool: g_slot    = cmp_state_slot_bid_slot == EQ;
var bool: g_genesis = state_slot_past_genesis;
var bool: g_ph      = parent_block_hash_match == T;
var bool: g_pr      = parent_block_root_match == T;
var bool: g_rr      = prev_randao_match == T;

% ---- Outcome (first-failing gate) --------------------------------------------
enum Outcome = {
  ACCEPT,
  REJECT_SELF_BUILD_NONZERO_AMOUNT,
  REJECT_SELF_BUILD_BAD_SIGNATURE,
  REJECT_BUILDER_INACTIVE,
  REJECT_WRONG_VERSION,
  REJECT_UNDERFUNDED,
  REJECT_BAD_SIGNATURE,
  REJECT_KZG_OVER_LIMIT,
  REJECT_WRONG_SLOT,
  REJECT_NOT_PAST_GENESIS,
  REJECT_PARENT_HASH,
  REJECT_PARENT_ROOT,
  REJECT_PREV_RANDAO
};

var Outcome: common_stage;
constraint common_stage =
  if      not g_kzg     then REJECT_KZG_OVER_LIMIT
  elseif  not g_slot    then REJECT_WRONG_SLOT
  elseif  not g_genesis then REJECT_NOT_PAST_GENESIS
  elseif  not g_ph      then REJECT_PARENT_HASH
  elseif  not g_pr      then REJECT_PARENT_ROOT
  elseif  not g_rr      then REJECT_PREV_RANDAO
  else    ACCEPT
  endif;

var Outcome: outcome;
constraint outcome =
  if builder_type == SELF then
    if      not g_self_amount_ok then REJECT_SELF_BUILD_NONZERO_AMOUNT
    elseif  not g_self_sig_ok    then REJECT_SELF_BUILD_BAD_SIGNATURE
    else    common_stage
    endif
  else
    if      not g_active  then REJECT_BUILDER_INACTIVE
    elseif  not g_version then REJECT_WRONG_VERSION
    elseif  not g_funds   then REJECT_UNDERFUNDED
    elseif  not g_sig     then REJECT_BAD_SIGNATURE
    else    common_stage
    endif
  endif;

% ---- Faults ------------------------------------------------------------------
var bool: fault_self_amount = (builder_type == SELF)  /\ not g_self_amount_ok;
var bool: fault_self_sig    = (builder_type == SELF)  /\ not g_self_sig_ok;
var bool: fault_active      = (builder_type == EXTERNAL) /\ not g_active;
var bool: fault_version     = (builder_type == EXTERNAL) /\ not g_version;
var bool: fault_funds       = (builder_type == EXTERNAL) /\ not g_funds;
var bool: fault_sig         = (builder_type == EXTERNAL) /\ not g_sig;
var bool: fault_kzg         = not g_kzg;
var bool: fault_slot        = not g_slot;
var bool: fault_genesis     = not g_genesis;
var bool: fault_ph          = not g_ph;
var bool: fault_pr          = not g_pr;
var bool: fault_rr          = not g_rr;

var int: n_faults =
    bool2int(fault_self_amount) + bool2int(fault_self_sig)
  + bool2int(fault_active)      + bool2int(fault_version)
  + bool2int(fault_funds)       + bool2int(fault_sig)
  + bool2int(fault_kzg)         + bool2int(fault_slot)
  + bool2int(fault_genesis)     + bool2int(fault_ph)
  + bool2int(fault_pr)          + bool2int(fault_rr);

% ---- Effects -----------------------------------------------------------------
var bool: pending_payment_written = (outcome == ACCEPT) /\ amount_positive;
var bool: latest_bid_cached       = (outcome == ACCEPT);

% ---- Trace (checks reached) --------------------------------------------------
var bool: version_check_reached   = (builder_type == EXTERNAL) /\ g_active;
var bool: funds_check_reached     = version_check_reached /\ g_version;
var bool: signature_check_reached = funds_check_reached /\ g_funds;
var bool: common_reached =
    (builder_type == SELF  /\ g_self_amount_ok /\ g_self_sig_ok)
 \/ ((builder_type == EXTERNAL) /\ g_active /\ g_version /\ g_funds /\ g_sig);
