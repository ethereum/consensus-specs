% Handler model: process_builder_deposit_request.
%
% Reuses the SHARED aspects builder_membership and signed_message (the same
% signature aspect execution_payload_bid uses) plus withdrawal_credential,
% deposit_amount, and builder_reset. No solve item; a coverage driver solves.
%
% Spec: specs/gloas/beacon-chain.md process_builder_deposit_request.

include "../../aspects/withdrawal_credential.mzn";
include "../../aspects/builder_membership.mzn";
include "../../aspects/signed_message.mzn";        % shared with execution_payload_bid
include "../../aspects/deposit_amount.mzn";
include "../../aspects/builder_reset.mzn";

% ---- Applicability bindings --------------------------------------------------
% The deposit signature is a pure function of the request, so it is recoverable
% (applicable) regardless of path — reached only on the new-builder path.
constraint builder_signature_applicable <-> true;
% The reset-condition dimensions are recoverable when a builder is resolved.
constraint builder_reset_applicable <-> builder_pubkey_found;

% ---- Outcome (spec branch order) --------------------------------------------
enum Outcome = {
  IGNORED_BAD_PREFIX,
  IGNORED_BAD_SIGNATURE,
  ADDED_NEW_BUILDER,
  TOPPED_UP,
  TOPPED_UP_AFTER_RESET
};

var Outcome: outcome;
constraint outcome =
  if not wc_is_builder_prefix then
    IGNORED_BAD_PREFIX
  elseif not builder_pubkey_found then
    (if builder_signature_valid == T then ADDED_NEW_BUILDER else IGNORED_BAD_SIGNATURE endif)
  else
    (if reset_applies then TOPPED_UP_AFTER_RESET else TOPPED_UP endif)
  endif;

% ---- Effect -----------------------------------------------------------------
% Declared-and-constrained so the solver exposes it (see TEST_METHODOLOGY.md).
var bool: builder_credited;
constraint builder_credited <->
    (outcome in {ADDED_NEW_BUILDER, TOPPED_UP, TOPPED_UP_AFTER_RESET});
