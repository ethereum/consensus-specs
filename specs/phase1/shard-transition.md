# Ethereum 2.0 Phase 1 -- Shard Transition and Fraud Proofs

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Introduction](#introduction)
- [Fraud proofs](#fraud-proofs)
- [Proposals](#proposals)
- [Shard state transition function](#shard-state-transition-function)
- [Honest committee member behavior](#honest-committee-member-behavior)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

## Introduction

This document describes the shard transition function and fraud proofs as part of Phase 1 of Ethereum 2.0.

## Fraud proofs

**TODO: pre-phase-2 SSA pivot; remaining fraud-proofs ideas, to be revisited.**

TODO. The intent is to have a single universal fraud proof type, which contains the following parts:

1. An on-time attestation on some `shard` signing a `ShardTransition`
2. An index `i` of a particular position to focus on
3. The `ShardTransition` itself
4. The full body of the block
5. A Merkle proof to the `shard_states` in the parent block the attestation is referencing

The proof verifies that one of the two conditions is false:

1. Check custody bits: `custody_bits[i][j] != generate_custody_bit(subkey, block_contents)` for any `j`
2. Check transition:
    * `shard_state = transition.shard_states[i-1].copy()`
    * `proposer_pubkey = get_pubkey(get_shard_proposer_index(state, shard, slot), block_contents))`
    * `shard_state_transition(shard, slot, shard_state, shard_count, hash_tree_root(parent), proposer_pubkey)`
    * Verify `hash_tree_root(shard_state) != transition.shard_states[i]` (if `i=0` then instead use `parent.shard_states[shard][-1]`)

## Proposals

A proposer builds a data blob by following the proposer protocol:

```python
# We will add something more substantive in phase 2
class Proposer(Protocol):
    def make_empty_proposal(self, 
                            shard: Shard,
                            slot: Slot,
                            shard_state: ShardState,
                            previous_beacon_root: Root,
                            proposer_pubkey: BLSPubkey):
        return ByteList[MAX_SHARD_BLOCK_SIZE]()  # empty byte list

    def make_shard_data_proposal(self,
                                 shard: Shard,
                                 slot: Slot,
                                 shard_state: ShardState,
                                 previous_beacon_root: Root,
                                 proposer_pubkey: BLSPubkey) -> ByteList[MAX_SHARD_BLOCK_SIZE]:
        ...  # Proposer can choose the include any bytes data.
```

## Shard state transition function

```python
def shard_state_transition(shard: Shard,
                           slot: Slot,
                           shard_state: ShardState,
                           shard_count: uint64,
                           previous_beacon_root: Root,
                           proposer_pubkey: BLSPubkey,
                           block_data: ByteList[MAX_SHARD_BLOCK_SIZE]):
    # We will add something more substantive in phase 2
    shard_state.shard_parent_root = hash_tree_root(shard_state)
    shard_state.slot += 1
    shard_state.shard_state_contents_root = hash(hash_tree_root(previous_beacon_root) + hash_tree_root(block_data))
```

## Honest committee member behavior

Suppose you are a committee member on shard `shard` at slot `current_slot`.
Let `state` be the head beacon state you are building on, and let `QUARTER_PERIOD = SECONDS_PER_SLOT // 4`. `2 * QUARTER_PERIOD` seconds into slot `slot`, run the following procedure:

* Initialize `data_proposals = []`, `shard_states = []`, `shard_state = state.shard_states[shard][-1]`, `start_slot = shard_state.slot`, `shard_count = len(state.shard_states)`
* `offset_slots = get_offset_slots(state, start_slot)`
* `proposer` is the `Proposer` agent.
* For `slot in offset_slots`, do the following:
    * Get previous block root of the beacon chain. Let `prev_beacon_root = get_beacon_block_root(state, state.slot - 1)`
    * Get shard proposer. Let `shard_proposer_index = get_shard_proposer_index(state, shard, slot)`
    * Build data-proposal (shard block data): `data_proposal = proposer.make_shard_data_proposal(shard, slot, shard_state, prev_beacon_root, shard_proposer_index)`
    * Verify that `shard_state_transition(shard, slot, shard_state, shard_count, prev_beacon_root, shard_proposer_index, proposal)` raises no exception.
    * If failing to build any proposal (no transactions), make an empty proposal: `proposer.make_empty_proposal(shard_state, slot)`
    * If `data_proposal` is NOT an empty proposal, then transition the shard state forward: 
     `shard_state_transition(shard, slot, shard_state, shard_count, prev_block_root, shard_proposer_index)`
      If it is an empty proposal, leave `shard_state` unchanged.
    * Append a the proposal and resulting shard state:
        * A copy of the shard-state: `shard_states.append(shard_state.copy())`.
        * The proposal: `data_proposals.append(data_proposal)`

To make a `ShardBlock` for `offset_slots[i]`:
 * `shard_parent_root = hash_tree_root(parent_shard_block)`
 * `beacon_parent_root = prev_block_root`
 * `slot = offset_slots[i]`
 * `body = data_proposals[i]`

To make a `ShardTransition`:
 * `shard_data_roots = [hash_tree_root(data_proposal) for data_proposal in data_proposals]`
 * `shard_states = [hash_tree_root(shard_state) for shard_state in shard_states]`

To make an `Attestation`:
 * `custody_bits_blocks = [custody_bits(data_proposal) for data_proposal in data_proposals]`
 * `AttestationData`:
    * `beacon_block_root = prev_beacon_root`
    * `head_shard_root = hash_tree_root(shard_block)`  (See shard block proposals)
    * `shard_state_root = [hash_tree_root(shard_state) for shard_state in shard_states]`.

