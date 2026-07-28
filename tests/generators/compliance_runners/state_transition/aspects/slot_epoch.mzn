% Realization aspect: slot / epoch relationship.
%
% Spec: bid.slot == state.slot ; state.slot > GENESIS_SLOT
% (specs/gloas/beacon-chain.md process_execution_payload_bid :1639-1640).
% Always applicable.

include "base.mzn";

var CMP: bid_slot_to_state;         % compare(bid.slot, state.slot)
var bool: state_slot_past_genesis;   % state.slot > GENESIS_SLOT

var bool: bid_slot_matches;
constraint bid_slot_matches <-> (bid_slot_to_state == EQ);

% bid.slot < state.slot requires state.slot > GENESIS_SLOT (a bid slot cannot be
% below the genesis slot), so LT implies the state is past genesis.
constraint (bid_slot_to_state == LT) -> state_slot_past_genesis;
