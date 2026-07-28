% Relational model: process_parent_execution_payload (Gloas).
%
% The request-cap predicates remain concrete even when an earlier gate rejects:
% they describe recoverable input properties.  The *_checked dimensions model
% the handler's short-circuit trace separately.
%
% Spec: specs/gloas/beacon-chain.md process_parent_execution_payload and
% apply_parent_execution_payload.

enum PaymentSettlement = { CURRENT_EPOCH, PREVIOUS_EPOCH, EVICTED };
enum Outcome = {
  REJECT_NONEMPTY_REQUESTS_FOR_EMPTY_PARENT,
  EMPTY_PARENT_NOOP,
  REJECT_REQUESTS_ROOT,
  REJECT_WITHDRAWALS_CAP,
  REJECT_CONSOLIDATIONS_CAP,
  REJECT_BUILDER_DEPOSITS_CAP,
  REJECT_BUILDER_EXITS_CAP,
  APPLY_CURRENT_WITH_WITHDRAWAL,
  APPLY_CURRENT_NO_WITHDRAWAL,
  APPLY_PREVIOUS_WITH_WITHDRAWAL,
  APPLY_EVICTED_WITH_WITHDRAWAL,
  APPLY_EVICTED_NO_WITHDRAWAL
};

var bool: parent_payload_revealed;
var bool: requests_empty;
var bool: requests_root_matches;
var bool: withdrawals_within_cap;
var bool: consolidations_within_cap;
var bool: builder_deposits_within_cap;
var bool: builder_exits_within_cap;
var bool: deposits_nonempty;
var bool: dispatches_nonempty_requests;
var PaymentSettlement: payment_settlement;
var bool: payment_value_nonzero;

% The materializer puts one item in every request list when a non-empty shape
% is requested. An over-cap list is necessarily non-empty.
constraint requests_empty <->
  withdrawals_within_cap /\ consolidations_within_cap /\
  builder_deposits_within_cap /\ builder_exits_within_cap /\
  not deposits_nonempty;

% A previous-epoch zero-value case has the same observable branch effect as the
% current-epoch zero-value case, apart from the circular-buffer index.
constraint payment_settlement == PREVIOUS_EPOCH -> payment_value_nonzero;

var bool: requests_empty_checked;
var bool: requests_root_checked;
var bool: withdrawals_cap_checked;
var bool: consolidations_cap_checked;
var bool: builder_deposits_cap_checked;
var bool: builder_exits_cap_checked;

constraint requests_empty_checked <-> not parent_payload_revealed;
constraint requests_root_checked <-> parent_payload_revealed;
constraint withdrawals_cap_checked <->
  parent_payload_revealed /\ requests_root_matches;
constraint consolidations_cap_checked <->
  withdrawals_cap_checked /\ withdrawals_within_cap;
constraint builder_deposits_cap_checked <->
  consolidations_cap_checked /\ consolidations_within_cap;
constraint builder_exits_cap_checked <->
  builder_deposits_cap_checked /\ builder_deposits_within_cap;
constraint dispatches_nonempty_requests <->
  builder_exits_cap_checked /\ builder_exits_within_cap /\ not requests_empty;

var Outcome: outcome;
constraint outcome =
  if not parent_payload_revealed then
    if requests_empty then EMPTY_PARENT_NOOP
    else REJECT_NONEMPTY_REQUESTS_FOR_EMPTY_PARENT endif
  elseif not requests_root_matches then REJECT_REQUESTS_ROOT
  elseif not withdrawals_within_cap then REJECT_WITHDRAWALS_CAP
  elseif not consolidations_within_cap then REJECT_CONSOLIDATIONS_CAP
  elseif not builder_deposits_within_cap then REJECT_BUILDER_DEPOSITS_CAP
  elseif not builder_exits_within_cap then REJECT_BUILDER_EXITS_CAP
  elseif payment_settlement == CURRENT_EPOCH then
    if payment_value_nonzero then APPLY_CURRENT_WITH_WITHDRAWAL
    else APPLY_CURRENT_NO_WITHDRAWAL endif
  elseif payment_settlement == PREVIOUS_EPOCH then
    APPLY_PREVIOUS_WITH_WITHDRAWAL
  else
    if payment_value_nonzero then APPLY_EVICTED_WITH_WITHDRAWAL
    else APPLY_EVICTED_NO_WITHDRAWAL endif
  endif;

set of Outcome: APPLIED = {
  APPLY_CURRENT_WITH_WITHDRAWAL,
  APPLY_CURRENT_NO_WITHDRAWAL,
  APPLY_PREVIOUS_WITH_WITHDRAWAL,
  APPLY_EVICTED_WITH_WITHDRAWAL,
  APPLY_EVICTED_NO_WITHDRAWAL
};

var bool: state_effected;
var bool: payment_withdrawal_appended;
var bool: payment_slot_cleared;
constraint state_effected <-> outcome in APPLIED;
constraint payment_withdrawal_appended <->
  outcome in APPLIED /\ payment_value_nonzero;
constraint payment_slot_cleared <->
  outcome in APPLIED /\
  payment_settlement in {CURRENT_EPOCH, PREVIOUS_EPOCH};
