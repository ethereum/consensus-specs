% Relational model: process_attestation (Gloas). Gate values are deliberately
% free: coverage profiles, not a first-failing frontier, select representatives.
enum Outcome = { REJECT_TARGET_EPOCH_OUT_OF_WINDOW, REJECT_TARGET_EPOCH_SLOT_MISMATCH,
  REJECT_INCLUSION_DELAY, REJECT_INDEX, REJECT_COMMITTEE_INDEX, REJECT_COMMITTEE_EMPTY,
  REJECT_AGGREGATION_LENGTH, REJECT_SIGNATURE, ACCEPT_CURRENT, ACCEPT_PREVIOUS };
var bool: target_epoch_in_window; var bool: target_epoch_matches_slot;
var bool: inclusion_delay_ok; var bool: index_valid; var bool: committee_indices_valid;
var bool: committee_nonempty; var bool: aggregation_length_valid; var bool: signature_valid;
var bool: target_is_current; var bool: attestation_is_same_slot;
var bool: pending_payment_amount_positive; var bool: sets_new_participation_flag;
var bool: payment_weight_increased; var Outcome: outcome;
constraint attestation_is_same_slot -> target_is_current;
constraint attestation_is_same_slot -> target_epoch_matches_slot;
constraint attestation_is_same_slot -> inclusion_delay_ok;
% An inclusion-delay failure is materialized at state.slot. If its target still
% matches that slot, it is necessarily a current-epoch target.
constraint not inclusion_delay_ok /\ target_epoch_matches_slot -> target_is_current;
constraint not inclusion_delay_ok /\ not target_epoch_matches_slot -> not target_is_current;
% Payment weight is a same-slot effect. The materializer's flag-preparation
% dimension is likewise meaningful only for a same-slot attestation.
constraint not attestation_is_same_slot ->
  (not pending_payment_amount_positive /\ not sets_new_participation_flag);
% An out-of-window target is materialized in the future. It is neither the
% current target nor consistent with the (current/previous) attestation slot.
constraint not target_epoch_in_window ->
  (not target_is_current /\ not target_epoch_matches_slot);
% The materializer signs only structurally valid attestations. Once committee
% processing cannot reach a later structural/signature check, its value is
% deterministically false in the concrete vector.
constraint not committee_indices_valid ->
  (not committee_nonempty /\ not aggregation_length_valid /\ not signature_valid);
constraint not committee_nonempty -> not signature_valid;
constraint not aggregation_length_valid -> not signature_valid;
% The materializer can only prepare same-slot participation/payment state once
% the signed attestation is structurally valid. These dimensions therefore
% cannot be true when a structural or signature gate blocks that preparation.
constraint (not signature_valid \/ not committee_indices_valid \/
            not committee_nonempty \/ not aggregation_length_valid) ->
  (not pending_payment_amount_positive /\ not sets_new_participation_flag);
constraint not index_valid ->
  (not pending_payment_amount_positive /\ not sets_new_participation_flag);
constraint outcome = if not target_epoch_in_window then REJECT_TARGET_EPOCH_OUT_OF_WINDOW
 elseif not target_epoch_matches_slot then REJECT_TARGET_EPOCH_SLOT_MISMATCH
 elseif not inclusion_delay_ok then REJECT_INCLUSION_DELAY elseif not index_valid then REJECT_INDEX
 elseif not committee_indices_valid then REJECT_COMMITTEE_INDEX elseif not committee_nonempty then REJECT_COMMITTEE_EMPTY
 elseif not aggregation_length_valid then REJECT_AGGREGATION_LENGTH elseif not signature_valid then REJECT_SIGNATURE
 elseif target_is_current then ACCEPT_CURRENT else ACCEPT_PREVIOUS endif;
constraint payment_weight_increased <-> outcome in {ACCEPT_CURRENT, ACCEPT_PREVIOUS} /\ attestation_is_same_slot /\ pending_payment_amount_positive /\ sets_new_participation_flag;
