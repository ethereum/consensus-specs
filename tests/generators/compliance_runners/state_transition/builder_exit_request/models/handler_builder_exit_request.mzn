% Handler model: process_builder_exit_request.
%
% Reuses the SHARED realization aspects builder_lifecycle (is_active_builder) and
% builder_pending_balance (get_pending_balance_to_withdraw_for_builder) — the
% same aspect files bound by execution_payload_bid — plus builder_membership and
% source_authorization. No solve item; a coverage driver solves.
%
% Spec: specs/gloas/beacon-chain.md process_builder_exit_request.

include "../../aspects/builder_membership.mzn";
include "../../aspects/builder_lifecycle.mzn";        % shared with execution_payload_bid
include "../../aspects/builder_pending_balance.mzn";  % shared with execution_payload_bid
include "../../aspects/source_authorization.mzn";

% ---- Bind shared-aspect applicability to membership -------------------------
constraint builder_lifecycle_applicable    <-> builder_pubkey_found;
constraint builder_pending_applicable       <-> builder_pubkey_found;
constraint source_authorization_applicable  <-> builder_pubkey_found;

% Well-formedness: a builder holds pending balance only while active.
constraint builder_has_pending_balance -> builder_active;

% ---- Gate passes (spec order) -----------------------------------------------
var bool: g_found      = builder_pubkey_found;
var bool: g_active     = builder_active;
var bool: g_addr       = source_address_matches == T;
var bool: g_no_pending = not builder_has_pending_balance;

% ---- Outcome (first-failing gate) -------------------------------------------
enum Outcome = {
  EXIT_INITIATED,
  IGNORED_PUBKEY_NOT_FOUND,
  IGNORED_NOT_ACTIVE,
  IGNORED_ADDRESS_MISMATCH,
  IGNORED_PENDING_NONZERO
};

var Outcome: outcome;
constraint outcome =
  if      not g_found      then IGNORED_PUBKEY_NOT_FOUND
  elseif  not g_active     then IGNORED_NOT_ACTIVE
  elseif  not g_addr       then IGNORED_ADDRESS_MISMATCH
  elseif  not g_no_pending then IGNORED_PENDING_NONZERO
  else    EXIT_INITIATED
  endif;

% ---- Faults (applicable gate in its failing state) --------------------------
var bool: fault_found   = not g_found;
var bool: fault_active  = builder_pubkey_found /\ not g_active;
var bool: fault_addr    = builder_pubkey_found /\ not g_addr;
var bool: fault_pending = builder_pubkey_found /\ not g_no_pending;
var int: n_faults =
    bool2int(fault_found) + bool2int(fault_active)
  + bool2int(fault_addr)  + bool2int(fault_pending);

% ---- Effect -----------------------------------------------------------------
% Declared-and-constrained (not `= expr`) so the solver exposes it in solutions.
var bool: exit_initiated;
constraint exit_initiated <-> (outcome == EXIT_INITIATED);
