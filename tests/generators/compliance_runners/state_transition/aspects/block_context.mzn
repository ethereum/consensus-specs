% Realization aspect: block-context matching.
%
% Spec (specs/gloas/beacon-chain.md process_execution_payload_bid :1642-1644):
%   bid.parent_block_hash == state.latest_block_hash
%   bid.parent_block_root == get_block_root_at_slot(state, state.slot - 1)
%   bid.prev_randao       == get_randao_mix(state, get_current_epoch(state))
% Always applicable.

include "base.mzn";

var bool: bid_parent_block_hash_matches;
var bool: bid_prev_randao_matches;

% parent_block_root compares against get_block_root_at_slot(state, slot - 1),
% which is only defined past genesis. NA at the genesis slot.
var bool: bid_parent_block_root_applicable;
var BOOLV_NA: bid_parent_block_root_matches;
constraint (bid_parent_block_root_matches == NA) <-> not bid_parent_block_root_applicable;
