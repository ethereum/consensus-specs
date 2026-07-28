% Handler model: process_payload_attestation (Gloas).
%
% An aggregate signature has no semantic truth value when its indexed
% attestation is empty: the helper rejects before aggregate verification.

include "../../aspects/signed_message.mzn";

enum Outcome = {
  REJECT_PARENT_ROOT,
  REJECT_SLOT,
  REJECT_EMPTY,
  REJECT_SIGNATURE,
  ACCEPT
};

var bool: parent_root_matches;
var bool: slot_is_previous;
var bool: attesting_indices_nonempty;
var Dim: signature_valid;
constraint signed_message_ok(signature_valid, attesting_indices_nonempty);
constraint attesting_indices_nonempty -> signature_valid in BOOLV;

var Outcome: outcome;
constraint outcome =
  if not parent_root_matches then REJECT_PARENT_ROOT
  elseif not slot_is_previous then REJECT_SLOT
  elseif not attesting_indices_nonempty then REJECT_EMPTY
  elseif signature_valid != T then REJECT_SIGNATURE
  else ACCEPT endif;

var bool: state_effected;
constraint state_effected <-> false;
