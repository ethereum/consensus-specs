% Handler model: process_deposit_request (gloas).
%
% Modified in gloas: the Electra start-index logic is REMOVED — the handler
% unconditionally appends a PendingDeposit copied from the request (with
% slot = state.slot) and touches nothing else. So there is a single outcome and
% no gates; `amount_nonzero` and `pubkey_is_existing_validator` are pure
% input/output-shape dimensions. No solve item.
%
% Spec: specs/gloas/beacon-chain.md process_deposit_request (invoked via
% apply_parent_execution_payload).

include "../../aspects/deposit_amount.mzn";
include "../../aspects/deposit_pubkey.mzn";

enum Outcome = { APPENDED };

var Outcome: outcome;
constraint outcome = APPENDED;
