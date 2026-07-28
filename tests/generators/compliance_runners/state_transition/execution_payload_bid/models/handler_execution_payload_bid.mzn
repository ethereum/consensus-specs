% Handler model: process_execution_payload_bid.
%
% Assembles the shared realization aspects, binds their applicability to this
% handler's entity reference, adds handler-local dimensions, and derives the
% outcome (first-failing gate in spec order), per-gate faults, effects, and a
% few trace dimensions. No solve item — a coverage model drives solving.
%
% Spec: specs/gloas/beacon-chain.md process_execution_payload_bid (:1611).

include "../../aspects/entity_reference.mzn";
include "../../aspects/builder_lifecycle.mzn";
include "../../aspects/builder_version.mzn";
include "../../aspects/builder_pending_balance.mzn";
include "../../aspects/builder_funds.mzn";
include "../../aspects/signed_message.mzn";
include "../../aspects/self_build_signature.mzn";
include "../../aspects/blob_kzg_capacity.mzn";
include "../../aspects/slot_epoch.mzn";
include "../../aspects/block_context.mzn";

% ---- Handler-local dimensions ------------------------------------------------
var bool: amount_positive;  % bid.value > 0 (self-build requires amount == 0)

% ---- Bind aspect applicability to the entity reference -----------------------
% Builder lifecycle / version / pending / funds / external signature are
% applicable only for a resolved existing builder. The self-build signature is
% applicable only for a self-build.
constraint builder_lifecycle_applicable    <-> (builder_ref == EXISTING);
constraint builder_version_applicable      <-> (builder_ref == EXISTING);
constraint builder_pending_applicable      <-> (builder_ref == EXISTING);
constraint builder_funds_applicable        <-> (builder_ref == EXISTING);
constraint builder_signature_applicable    <-> (builder_ref == EXISTING);
constraint self_build_signature_applicable <-> (builder_ref == SELF_BUILD);
constraint bid_parent_block_root_applicable <-> state_slot_past_genesis;

% bid.value is the shared operand of the funds comparison and amount_positive:
% a zero bid pins the available/bid comparison to the balance/min gap; a positive
% bid at balance == min_balance is strictly greater (available/bid == LT).
constraint (builder_balance_to_min_balance == EQ /\ amount_positive)     -> (builder_available_to_bid == LT);
constraint (builder_balance_to_min_balance == EQ /\ not amount_positive) -> (builder_available_to_bid == EQ);
constraint (builder_balance_to_min_balance == GT /\ not amount_positive) -> (builder_available_to_bid == GT);

% ---- Gate pass predicates (spec order) ---------------------------------------
var bool: g_self_amount_ok = not amount_positive;                     % amount == 0
var bool: g_self_sig_ok    = self_build_signature_is_infinity == T;
var bool: g_active         = builder_active;
var bool: g_version        = builder_version_valid == T;
var bool: g_funds          = builder_can_cover_bid;
var bool: g_sig            = builder_signature_valid == T;
var bool: g_kzg            = bid_kzg_under_limit;
var bool: g_slot           = bid_slot_matches;
var bool: g_genesis        = state_slot_past_genesis;
var bool: g_ph             = bid_parent_block_hash_matches;
var bool: g_pr             = bid_parent_block_root_matches == T;
var bool: g_rr             = bid_prev_randao_matches;

% ---- Outcome (first-failing gate) --------------------------------------------
enum Outcome = {
  ACCEPT,
  REJECT_SELF_BUILD_NONZERO_AMOUNT,
  REJECT_SELF_BUILD_BAD_SIGNATURE,
  REJECT_BUILDER_NOT_FOUND,
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

% Outcome once the branch-specific gates have passed (shared tail).
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
  if self_build then
    if      not g_self_amount_ok then REJECT_SELF_BUILD_NONZERO_AMOUNT
    elseif  not g_self_sig_ok    then REJECT_SELF_BUILD_BAD_SIGNATURE
    else    common_stage
    endif
  elseif builder_ref == NON_EXISTING then REJECT_BUILDER_NOT_FOUND
  elseif not g_active  then REJECT_BUILDER_INACTIVE
  elseif not g_version then REJECT_WRONG_VERSION
  elseif not g_funds   then REJECT_UNDERFUNDED
  elseif not g_sig     then REJECT_BAD_SIGNATURE
  else   common_stage
  endif;

% ---- Faults (an applicable gate in its failing state) ------------------------
% Used by coverage formulas. Not-applicable gates never count as faults.
var bool: fault_self_amount = self_build /\ not g_self_amount_ok;
var bool: fault_self_sig    = self_build /\ not g_self_sig_ok;
var bool: fault_not_found   = (builder_ref == NON_EXISTING);
var bool: fault_active      = (builder_ref == EXISTING) /\ not g_active;
var bool: fault_version     = (builder_ref == EXISTING) /\ not g_version;
var bool: fault_funds       = (builder_ref == EXISTING) /\ not g_funds;
var bool: fault_sig         = (builder_ref == EXISTING) /\ not g_sig;
var bool: fault_kzg         = not g_kzg;
var bool: fault_slot        = not g_slot;
var bool: fault_genesis     = not g_genesis;
var bool: fault_ph          = not g_ph;
var bool: fault_pr          = bid_parent_block_root_matches == F;  % NA is not a fault
var bool: fault_rr          = not g_rr;

var int: n_faults =
    bool2int(fault_self_amount) + bool2int(fault_self_sig)
  + bool2int(fault_not_found)   + bool2int(fault_active)
  + bool2int(fault_version)     + bool2int(fault_funds) + bool2int(fault_sig)
  + bool2int(fault_kzg)         + bool2int(fault_slot)  + bool2int(fault_genesis)
  + bool2int(fault_ph)          + bool2int(fault_pr)    + bool2int(fault_rr);

% ---- Effects -----------------------------------------------------------------
var bool: pending_payment_written = (outcome == ACCEPT) /\ amount_positive;
var bool: latest_bid_cached       = (outcome == ACCEPT);

% ---- Trace (checks reached) --------------------------------------------------
var bool: version_check_reached   = (builder_ref == EXISTING) /\ g_active;
var bool: funds_check_reached     = version_check_reached /\ g_version;
var bool: signature_check_reached = funds_check_reached /\ g_funds;
var bool: common_reached =
    (self_build /\ g_self_amount_ok /\ g_self_sig_ok)
 \/ ((builder_ref == EXISTING) /\ g_active /\ g_version /\ g_funds /\ g_sig);
