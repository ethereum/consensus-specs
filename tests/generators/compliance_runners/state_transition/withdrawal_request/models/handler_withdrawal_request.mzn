% Handler model: process_withdrawal_request.
%
% Establishes the validator aspect family (membership / credential / lifecycle /
% balance / pending) and REUSES source_authorization (shared with
% builder_exit_request). No BLS, no churn gate. No solve item.
%
% Spec: specs/electra/beacon-chain.md process_withdrawal_request (inherited by gloas).

include "../../aspects/withdrawal_amount.mzn";
include "../../aspects/partial_queue_capacity.mzn";
include "../../aspects/validator_membership.mzn";
include "../../aspects/validator_credential.mzn";
include "../../aspects/source_authorization.mzn";     % shared with builder_exit_request
include "../../aspects/validator_lifecycle.mzn";
include "../../aspects/validator_pending_withdrawal.mzn";
include "../../aspects/validator_balance.mzn";

% ---- Applicability bindings (validator resolved) ----------------------------
constraint validator_credential_applicable <-> validator_pubkey_found;
constraint source_authorization_applicable <-> validator_pubkey_found;
constraint validator_lifecycle_applicable  <-> validator_pubkey_found;
constraint validator_pending_applicable    <-> validator_pubkey_found;
constraint validator_balance_applicable    <-> validator_pubkey_found;

% ---- Gate passes (spec order) -----------------------------------------------
var bool: g_cred        = validator_has_execution_credential /\ source_address_matches == T;
var bool: g_active      = validator_active == T;
var bool: g_not_exiting = validator_exiting == F;
var bool: g_old         = validator_old_enough == T;

% ---- Outcome (first-failing gate, then branch) ------------------------------
enum Outcome = {
  REJECTED_QUEUE_FULL,
  REJECTED_NOT_FOUND,
  REJECTED_CREDENTIALS,
  REJECTED_INACTIVE,
  REJECTED_EXITING,
  REJECTED_TOO_YOUNG,
  FULL_EXIT_INITIATED,
  FULL_EXIT_NOOP_PENDING,
  PARTIAL_NOOP_NOT_COMPOUNDING,
  PARTIAL_NOOP_INSUFFICIENT_EFFECTIVE_BALANCE,
  PARTIAL_NOOP_NO_EXCESS_BALANCE,
  PARTIAL_QUEUED
};

var Outcome: outcome;
constraint outcome =
  if      partial_queue_full /\ not is_full_exit_request then REJECTED_QUEUE_FULL
  elseif  not validator_pubkey_found then REJECTED_NOT_FOUND
  elseif  not g_cred        then REJECTED_CREDENTIALS
  elseif  not g_active      then REJECTED_INACTIVE
  elseif  not g_not_exiting then REJECTED_EXITING
  elseif  not g_old         then REJECTED_TOO_YOUNG
  elseif  is_full_exit_request then
    (if has_pending_partial_withdrawal == T then FULL_EXIT_NOOP_PENDING else FULL_EXIT_INITIATED endif)
  else
    (if      not validator_has_compounding_credential then PARTIAL_NOOP_NOT_COMPOUNDING
     elseif  sufficient_effective_balance != T        then PARTIAL_NOOP_INSUFFICIENT_EFFECTIVE_BALANCE
     elseif  has_excess_balance != T                  then PARTIAL_NOOP_NO_EXCESS_BALANCE
     else    PARTIAL_QUEUED endif)
  endif;

% ---- Faults (applicable gate in its failing state) --------------------------
var bool: fault_queue    = partial_queue_full /\ not is_full_exit_request;
var bool: fault_found    = not validator_pubkey_found;
var bool: fault_cred     = validator_pubkey_found /\ not g_cred;
var bool: fault_active   = validator_pubkey_found /\ not g_active;
var bool: fault_exiting  = validator_pubkey_found /\ not g_not_exiting;
var bool: fault_young    = validator_pubkey_found /\ not g_old;
var int: n_faults =
    bool2int(fault_queue) + bool2int(fault_found) + bool2int(fault_cred)
  + bool2int(fault_active) + bool2int(fault_exiting) + bool2int(fault_young);

% ---- Effect (label; declared-and-constrained so it is exposed) --------------
var bool: withdrawal_effected;
constraint withdrawal_effected <-> (outcome in {FULL_EXIT_INITIATED, PARTIAL_QUEUED});
