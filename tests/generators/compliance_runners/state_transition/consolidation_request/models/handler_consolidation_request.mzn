% Handler model: process_consolidation_request.
%
% Two paths: switch-to-compounding (source == target) and consolidation
% (source != target). The parameterized validator aspects (lifecycle / credential)
% are instantiated for BOTH the source and the target role — the same aspect
% predicates, applied twice. Seasoning + authorization + pending are source-only.
%
% Spec: specs/electra/beacon-chain.md process_consolidation_request (inherited by gloas).

include "../../aspects/consolidation_pair.mzn";
include "../../aspects/pending_consolidations_capacity.mzn";
include "../../aspects/consolidation_churn.mzn";
include "../../aspects/validator_membership.mzn";     % source membership (validator_pubkey_found)
include "../../aspects/validator_credential.mzn";     % parameterized (source + target)
include "../../aspects/validator_lifecycle.mzn";      % parameterized (source + target)
include "../../aspects/validator_seasoning.mzn";      % parameterized (source only)
include "../../aspects/source_authorization.mzn";     % shared with builder_exit / withdrawal
include "../../aspects/validator_pending_withdrawal.mzn";  % source

% ---- Source validator instance ----------------------------------------------
var ValidatorCredentialKind: validator_credential;
var BOOLV_NA: validator_active;
var BOOLV_NA: validator_exiting;
var BOOLV_NA: validator_old_enough;
constraint validator_credential_ok(validator_credential, validator_pubkey_found);
constraint validator_lifecycle_ok(validator_active, validator_exiting, validator_pubkey_found);
constraint validator_seasoning_ok(validator_old_enough, validator_pubkey_found);
constraint (validator_old_enough == T /\ validator_exiting == F) -> (validator_active == T);
constraint source_authorization_applicable <-> validator_pubkey_found;
constraint validator_pending_applicable    <-> validator_pubkey_found;

var bool: validator_has_execution_credential;
var bool: validator_has_compounding_credential;
constraint validator_has_execution_credential <-> cred_has_execution(validator_credential);
constraint validator_has_compounding_credential <-> cred_has_compounding(validator_credential);

% ---- Target validator instance (consolidation path only) --------------------
% The target role exists only when source != target; membership then decides the
% rest. Same lifecycle/credential predicates as the source, applied to target vars.
var BOOLV_NA: target_found;
constraint (target_found == NA) <-> same_source_target;
var bool: target_role_found = (not same_source_target) /\ target_found == T;

var ValidatorCredentialKind: target_credential;
var BOOLV_NA: target_active;
var BOOLV_NA: target_exiting;
constraint validator_credential_ok(target_credential, target_role_found);
constraint validator_lifecycle_ok(target_active, target_exiting, target_role_found);

var bool: target_has_compounding_credential;
constraint target_has_compounding_credential <-> cred_has_compounding(target_credential);

% ---- Source predicates ------------------------------------------------------
var bool: source_found      = validator_pubkey_found;
var bool: source_authorized = source_address_matches == T;
var bool: source_is_eth1    = validator_credential == CRED_ETH1;
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
     elseif  not (source_execution_and_authorized)  then REJECTED_SOURCE_CREDENTIALS
     elseif  not target_has_compounding_credential  then REJECTED_TARGET_NOT_COMPOUNDING
     elseif  not source_active                      then REJECTED_SOURCE_INACTIVE
     elseif  not (target_active == T)               then REJECTED_TARGET_INACTIVE
     elseif  source_exiting                         then REJECTED_SOURCE_EXITING
     elseif  target_exiting == T                    then REJECTED_TARGET_EXITING
     elseif  not source_old_enough                  then REJECTED_SOURCE_TOO_YOUNG
     elseif  source_has_pending                     then REJECTED_SOURCE_PENDING_WITHDRAWAL
     else    CONSOLIDATED endif)
  endif;

var bool: source_execution_and_authorized = validator_has_execution_credential /\ source_authorized;

% ---- Effect -----------------------------------------------------------------
var bool: state_effected;
constraint state_effected <-> (outcome in {SWITCHED_TO_COMPOUNDING, CONSOLIDATED});
