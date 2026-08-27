% Handler model: process_withdrawals (Gloas).
%
% The four sources are considered in protocol order: builder-pending,
% pending-partial, builder sweep, then validator sweep.  ``over_limit`` models
% the MAX_WITHDRAWALS_PER_PAYLOAD boundary, rather than a separate source.
%
% Spec: specs/gloas/beacon-chain.md process_withdrawals.

int: MAX_WITHDRAWALS_PER_PAYLOAD = 4;

enum Outcome = {
  PARENT_EMPTY_NOOP,
  FULL_NO_WITHDRAWALS,
  BUILDER_PENDING,
  PENDING_PARTIAL,
  BUILDER_SWEEP,
  VALIDATOR_SWEEP,
  MIXED_WITHDRAWALS,
  MAX_WITHDRAWALS_LIMIT
};

var bool: parent_payload_revealed;
var bool: builder_pending_nonempty;
var bool: pending_partial_nonempty;
var bool: builder_sweep_nonempty;
var bool: validator_sweep_nonempty;
var bool: withdrawals_over_limit;

var int: active_sources = bool2int(builder_pending_nonempty)
                        + bool2int(pending_partial_nonempty)
                        + bool2int(builder_sweep_nonempty)
                        + bool2int(validator_sweep_nonempty);

constraint active_sources >= MAX_WITHDRAWALS_PER_PAYLOAD -> withdrawals_over_limit;

% Builder pending, pending partials, and builder sweep each reserve the final
% slot; a full payload therefore always contains a validator-sweep withdrawal.
constraint withdrawals_over_limit -> parent_payload_revealed /\ validator_sweep_nonempty;
constraint not parent_payload_revealed ->
    (not builder_pending_nonempty /\ not pending_partial_nonempty /\
     not builder_sweep_nonempty /\ not validator_sweep_nonempty /\
     not withdrawals_over_limit);

var Outcome: outcome;
constraint outcome =
  if not parent_payload_revealed then PARENT_EMPTY_NOOP
  elseif withdrawals_over_limit then MAX_WITHDRAWALS_LIMIT
  elseif active_sources == 0 then FULL_NO_WITHDRAWALS
  elseif active_sources >= 2 then MIXED_WITHDRAWALS
  elseif builder_pending_nonempty then BUILDER_PENDING
  elseif pending_partial_nonempty then PENDING_PARTIAL
  elseif builder_sweep_nonempty then BUILDER_SWEEP
  else VALIDATOR_SWEEP endif;

var bool: state_effected;
constraint state_effected <-> parent_payload_revealed;
