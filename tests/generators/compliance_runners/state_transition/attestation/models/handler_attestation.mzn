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
constraint outcome = if not target_epoch_in_window then REJECT_TARGET_EPOCH_OUT_OF_WINDOW
 elseif not target_epoch_matches_slot then REJECT_TARGET_EPOCH_SLOT_MISMATCH
 elseif not inclusion_delay_ok then REJECT_INCLUSION_DELAY elseif not index_valid then REJECT_INDEX
 elseif not committee_indices_valid then REJECT_COMMITTEE_INDEX elseif not committee_nonempty then REJECT_COMMITTEE_EMPTY
 elseif not aggregation_length_valid then REJECT_AGGREGATION_LENGTH elseif not signature_valid then REJECT_SIGNATURE
 elseif target_is_current then ACCEPT_CURRENT else ACCEPT_PREVIOUS endif;
constraint payment_weight_increased <-> outcome in {ACCEPT_CURRENT, ACCEPT_PREVIOUS} /\ attestation_is_same_slot /\ pending_payment_amount_positive /\ sets_new_participation_flag;
