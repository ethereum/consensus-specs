% Handler model: process_consolidation_request.
%
% Two paths: switch-to-compounding (source == target) and consolidation
% (source != target). REUSES the validator family for the SOURCE validator
% (membership / credential / lifecycle / pending) + source_authorization, and a
% compact target_validator aspect for the target. No BLS. Has a churn gate
% (materialized via active-set sizing).
%
% Spec: specs/electra/beacon-chain.md process_consolidation_request (inherited by gloas).

include "../../aspects/consolidation_pair.mzn";
include "../../aspects/pending_consolidations_capacity.mzn";
include "../../aspects/consolidation_churn.mzn";
include "../../aspects/validator_membership.mzn";     % source
include "../../aspects/validator_credential.mzn";     % source
include "../../aspects/source_authorization.mzn";     % source (shared with builder_exit / withdrawal)
include "../../aspects/validator_lifecycle.mzn";      % source
include "../../aspects/validator_pending_withdrawal.mzn";  % source
include "../../aspects/target_validator.mzn";

% ---- Applicability bindings --------------------------------------------------
constraint validator_credential_applicable <-> validator_pubkey_found;   % source resolved
constraint source_authorization_applicable <-> validator_pubkey_found;
constraint validator_lifecycle_applicable  <-> validator_pubkey_found;
constraint validator_pending_applicable    <-> validator_pubkey_found;
constraint target_role_applicable          <-> not same_source_target;

% ---- Source predicates (from the reused validator family) -------------------
var bool: source_found      = validator_pubkey_found;
var bool: source_authorized = source_address_matches == T;
var bool: source_is_eth1    = validator_credential == CRED_ETH1;
var bool: source_execution  = validator_has_execution_credential;
var bool: source_active     = validator_active == T;
var bool: source_exiting    = validator_exiting == T;
var bool: source_old_enough = validator_old_enough == T;
var bool: source_has_pending = has_pending_partial_withdrawal == T;

var bool: switch_valid =
    same_source_target /\ source_found /\ source_authorized /\ source_is_eth1
    /\ source_active /\ (not source_exiting);

% ---- Outcome ----------------------------------------------------------------
enum Outcome = {
  SWITCHED_TO_COMPOUNDING,
  SWITCH_REJECTED_SOURCE_NOT_FOUND,
  SWITCH_REJECTED_NOT_AUTHORIZED,
  SWITCH_REJECTED_NOT_ETH1,
  SWITCH_REJECTED_INACTIVE,
  SWITCH_REJECTED_EXITING,
  REJECTED_QUEUE_FULL,
  REJECTED_INSUFFICIENT_CHURN,
  REJECTED_SOURCE_NOT_FOUND,
  REJECTED_TARGET_NOT_FOUND,
  REJECTED_SOURCE_CREDENTIALS,
  REJECTED_TARGET_NOT_COMPOUNDING,
  REJECTED_SOURCE_INACTIVE,
  REJECTED_TARGET_INACTIVE,
  REJECTED_SOURCE_EXITING,
  REJECTED_TARGET_EXITING,
  REJECTED_SOURCE_TOO_YOUNG,
  REJECTED_SOURCE_PENDING_WITHDRAWAL,
  CONSOLIDATED
};

var Outcome: outcome;
constraint outcome =
  if switch_valid then
    SWITCHED_TO_COMPOUNDING
  elseif same_source_target then
    (if      not source_found      then SWITCH_REJECTED_SOURCE_NOT_FOUND
     elseif  not source_authorized then SWITCH_REJECTED_NOT_AUTHORIZED
     elseif  not source_is_eth1    then SWITCH_REJECTED_NOT_ETH1
     elseif  not source_active     then SWITCH_REJECTED_INACTIVE
     else    SWITCH_REJECTED_EXITING endif)
  else
    (if      pending_consolidations_full            then REJECTED_QUEUE_FULL
     elseif  not sufficient_consolidation_churn     then REJECTED_INSUFFICIENT_CHURN
     elseif  not source_found                       then REJECTED_SOURCE_NOT_FOUND
     elseif  not (target_found == T)                then REJECTED_TARGET_NOT_FOUND
     elseif  not (source_execution /\ source_authorized) then REJECTED_SOURCE_CREDENTIALS
     elseif  not (target_compounding == T)          then REJECTED_TARGET_NOT_COMPOUNDING
     elseif  not source_active                      then REJECTED_SOURCE_INACTIVE
     elseif  not (target_active == T)               then REJECTED_TARGET_INACTIVE
     elseif  source_exiting                         then REJECTED_SOURCE_EXITING
     elseif  target_exiting == T                    then REJECTED_TARGET_EXITING
     elseif  not source_old_enough                  then REJECTED_SOURCE_TOO_YOUNG
     elseif  source_has_pending                     then REJECTED_SOURCE_PENDING_WITHDRAWAL
     else    CONSOLIDATED endif)
  endif;

% ---- Effect -----------------------------------------------------------------
var bool: state_effected;
constraint state_effected <-> (outcome in {SWITCHED_TO_COMPOUNDING, CONSOLIDATED});
