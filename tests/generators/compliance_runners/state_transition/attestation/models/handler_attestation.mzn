% Handler model: process_attestation (Gloas).
enum Outcome = {
  REJECT_TARGET_EPOCH_OUT_OF_WINDOW, REJECT_TARGET_EPOCH_SLOT_MISMATCH,
  REJECT_INCLUSION_DELAY, REJECT_INDEX, REJECT_COMMITTEE_INDEX,
  REJECT_COMMITTEE_EMPTY, REJECT_AGGREGATION_LENGTH, REJECT_SIGNATURE,
  ACCEPT_CURRENT, ACCEPT_PREVIOUS
};

var bool: target_epoch_in_window;
var bool: target_epoch_matches_slot;
var bool: inclusion_delay_ok;
var bool: index_valid;
var bool: committee_indices_valid;
var bool: committee_nonempty;
var bool: aggregation_length_valid;
var bool: signature_valid;
var bool: target_is_current;
var bool: attestation_is_same_slot;
var bool: pending_payment_amount_positive;
var bool: sets_new_participation_flag;
var bool: payment_weight_increased;
var Outcome: outcome;

constraint outcome =
  if not target_epoch_in_window then REJECT_TARGET_EPOCH_OUT_OF_WINDOW
  elseif not target_epoch_matches_slot then REJECT_TARGET_EPOCH_SLOT_MISMATCH
  elseif not inclusion_delay_ok then REJECT_INCLUSION_DELAY
  elseif not index_valid then REJECT_INDEX
  elseif not committee_indices_valid then REJECT_COMMITTEE_INDEX
  elseif not committee_nonempty then REJECT_COMMITTEE_EMPTY
  elseif not aggregation_length_valid then REJECT_AGGREGATION_LENGTH
  elseif not signature_valid then REJECT_SIGNATURE
  elseif target_is_current then ACCEPT_CURRENT else ACCEPT_PREVIOUS endif;

constraint attestation_is_same_slot -> target_is_current;
constraint payment_weight_increased <-> outcome in {ACCEPT_CURRENT, ACCEPT_PREVIOUS}
  /\ attestation_is_same_slot /\ pending_payment_amount_positive /\ sets_new_participation_flag;

% One canonical first-failing-gate vector per rejection, plus two successes.
constraint outcome == REJECT_TARGET_EPOCH_OUT_OF_WINDOW ->
  (not target_epoch_in_window /\ target_epoch_matches_slot /\ inclusion_delay_ok /\ index_valid /\ committee_indices_valid /\ committee_nonempty /\ aggregation_length_valid /\ signature_valid /\ target_is_current);
constraint outcome == REJECT_TARGET_EPOCH_SLOT_MISMATCH ->
  (target_epoch_in_window /\ not target_epoch_matches_slot /\ inclusion_delay_ok /\ index_valid /\ committee_indices_valid /\ committee_nonempty /\ aggregation_length_valid /\ signature_valid /\ target_is_current);
constraint outcome == REJECT_INCLUSION_DELAY ->
  (target_epoch_in_window /\ target_epoch_matches_slot /\ not inclusion_delay_ok /\ index_valid /\ committee_indices_valid /\ committee_nonempty /\ aggregation_length_valid /\ signature_valid /\ target_is_current);
constraint outcome == REJECT_INDEX ->
  (target_epoch_in_window /\ target_epoch_matches_slot /\ inclusion_delay_ok /\ not index_valid /\ committee_indices_valid /\ committee_nonempty /\ aggregation_length_valid /\ signature_valid /\ target_is_current);
constraint outcome == REJECT_COMMITTEE_INDEX ->
  (target_epoch_in_window /\ target_epoch_matches_slot /\ inclusion_delay_ok /\ index_valid /\ not committee_indices_valid /\ committee_nonempty /\ aggregation_length_valid /\ signature_valid /\ target_is_current);
constraint outcome == REJECT_COMMITTEE_EMPTY ->
  (target_epoch_in_window /\ target_epoch_matches_slot /\ inclusion_delay_ok /\ index_valid /\ committee_indices_valid /\ not committee_nonempty /\ aggregation_length_valid /\ signature_valid /\ target_is_current);
constraint outcome == REJECT_AGGREGATION_LENGTH ->
  (target_epoch_in_window /\ target_epoch_matches_slot /\ inclusion_delay_ok /\ index_valid /\ committee_indices_valid /\ committee_nonempty /\ not aggregation_length_valid /\ signature_valid /\ target_is_current);
constraint outcome == REJECT_SIGNATURE ->
  (target_epoch_in_window /\ target_epoch_matches_slot /\ inclusion_delay_ok /\ index_valid /\ committee_indices_valid /\ committee_nonempty /\ aggregation_length_valid /\ not signature_valid /\ target_is_current);
constraint outcome == ACCEPT_CURRENT ->
  (target_epoch_in_window /\ target_epoch_matches_slot /\ inclusion_delay_ok /\ index_valid /\ committee_indices_valid /\ committee_nonempty /\ aggregation_length_valid /\ signature_valid /\ target_is_current);
constraint outcome == ACCEPT_PREVIOUS ->
  (target_epoch_in_window /\ target_epoch_matches_slot /\ inclusion_delay_ok /\ index_valid /\ committee_indices_valid /\ committee_nonempty /\ aggregation_length_valid /\ signature_valid /\ not target_is_current);
