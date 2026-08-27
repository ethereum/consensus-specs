% Handler model: process_proposer_slashing (Gloas).
%
% The payment dimensions model the EIP-7732 two-epoch pending-payment window.
% Signature values remain applicable even when an earlier assertion rejects.

include "../../aspects/signed_message.mzn";

enum PaymentWindow = { CURRENT, PREVIOUS, OLD };
enum Outcome = {
  REJECT_SLOT_MISMATCH, REJECT_PROPOSER_MISMATCH, REJECT_HEADERS_EQUAL,
  REJECT_NOT_SLASHABLE_SLASHED, REJECT_NOT_ACTIVATED,
  REJECT_NOT_SLASHABLE_WITHDRAWABLE, REJECT_SIGNATURE_1, REJECT_SIGNATURE_2,
  ACCEPT_CURRENT_PAYMENT_CLEARED, ACCEPT_CURRENT_PAYMENT_RETAINED,
  ACCEPT_PREVIOUS_PAYMENT_CLEARED, ACCEPT_PREVIOUS_PAYMENT_RETAINED, ACCEPT_OLD
};

var bool: slots_match;
var bool: proposers_match;
var bool: headers_different;

constraint (not slots_match \/ not proposers_match) -> headers_different;

var Dim: signature_1_valid;
var Dim: signature_2_valid;
constraint signed_message_ok(signature_1_valid, true);
constraint signed_message_ok(signature_2_valid, true);
constraint signature_1_valid in BOOLV;
constraint signature_2_valid in BOOLV;

var bool: proposer_slashed;
var bool: proposer_activated;
var bool: proposer_withdrawable;
% `is_slashable_validator` deliberately does not check `exit_epoch`: a
% validator remains slashable after exit until its withdrawable epoch.
var bool: proposer_exited;

var PaymentWindow: payment_window;
var BOOLV_NA: payment_proposer_matches;
constraint (payment_proposer_matches == NA) <-> payment_window == OLD;

var bool: proposer_slashable;
constraint proposer_slashable <->
  not proposer_slashed /\ proposer_activated /\ not proposer_withdrawable;

var Outcome: outcome;
constraint outcome =
  if not slots_match then REJECT_SLOT_MISMATCH
  elseif not proposers_match then REJECT_PROPOSER_MISMATCH
  elseif not headers_different then REJECT_HEADERS_EQUAL
  elseif not proposer_slashable then
    if proposer_slashed then REJECT_NOT_SLASHABLE_SLASHED
    elseif not proposer_activated then REJECT_NOT_ACTIVATED
    else REJECT_NOT_SLASHABLE_WITHDRAWABLE endif
  elseif signature_1_valid != T then REJECT_SIGNATURE_1
  elseif signature_2_valid != T then REJECT_SIGNATURE_2
  elseif payment_window == CURRENT then
    if payment_proposer_matches == T then ACCEPT_CURRENT_PAYMENT_CLEARED
    else ACCEPT_CURRENT_PAYMENT_RETAINED endif
  elseif payment_window == PREVIOUS then
    if payment_proposer_matches == T then ACCEPT_PREVIOUS_PAYMENT_CLEARED
    else ACCEPT_PREVIOUS_PAYMENT_RETAINED endif
  else ACCEPT_OLD endif;

var bool: pending_payment_cleared;
constraint pending_payment_cleared <-> outcome in {
  ACCEPT_CURRENT_PAYMENT_CLEARED, ACCEPT_PREVIOUS_PAYMENT_CLEARED
};
var bool: state_effected;
constraint state_effected <-> outcome in {
  ACCEPT_CURRENT_PAYMENT_CLEARED, ACCEPT_CURRENT_PAYMENT_RETAINED,
  ACCEPT_PREVIOUS_PAYMENT_CLEARED, ACCEPT_PREVIOUS_PAYMENT_RETAINED, ACCEPT_OLD
};
