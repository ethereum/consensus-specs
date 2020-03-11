<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Ethereum 2.0 Phase 1 -- Shard Transition and Fraud Proofs](#ethereum-20-phase-1----shard-transition-and-fraud-proofs)
  - [Table of contents](#table-of-contents)
  - [Introduction](#introduction)
  - [Fraud proofs](#fraud-proofs)
  - [Shard state transition function](#shard-state-transition-function)
  - [Honest committee member behavior](#honest-committee-member-behavior)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# Ethereum 2.0 Phase 1 -- Shard Transition and Fraud Proofs

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- TOC -->

 TODO

<!-- /TOC -->

## Introduction

This document describes the shard transition function and fraud proofs as part of Phase 1 of Ethereum 2.0.

## Fraud proofs

TODO. The intent is to have a single universal fraud proof type, which contains the following parts:

1. An on-time attestation on some `shard` signing a `ShardTransition`
2. An index `i` of a particular position to focus on
3. The `ShardTransition` itself
4. The full body of the block
5. A Merkle proof to the `shard_states` in the parent block the attestation is referencing

The proof verifies that one of the two conditions is false:

1. `custody_bits[i][j] != generate_custody_bit(subkey, block_contents)` for any `j`
2. `execute_state_transition(shard, slot, transition.shard_states[i-1].data, hash_tree_root(parent), get_shard_proposer_index(state, shard, slot), block_contents) != transition.shard_states[i].data` (if `i=0` then instead use `parent.shard_states[shard][-1].data`)

## Shard state transition function

```python
def shard_state_transition(shard: Shard,
                           slot: Slot,
                           pre_state: Root,
                           previous_beacon_root: Root,
                           proposer_pubkey: BLSPubkey,
                           block_data: ByteList[MAX_SHARD_BLOCK_SIZE]) -> Root:
    # We will add something more substantive in phase 2
    return hash(pre_state + hash_tree_root(previous_beacon_root) + hash_tree_root(block_data))
```

## Honest committee member behavior

Suppose you are a committee member on shard `shard` at slot `current_slot`. Let `state` be the head beacon state you are building on, and let `QUARTER_PERIOD = SECONDS_PER_SLOT // 4`. `2 * QUARTER_PERIOD` seconds into slot `slot`, run the following procedure:

* Initialize `proposals = []`, `shard_states = []`, `shard_state = state.shard_states[shard][-1]`, `start_slot = shard_state.slot`.
* For `slot in get_offset_slots(state, start_slot)`, do the following:
    * Look for all valid proposals for `slot`; that is, a Bytes `proposal` where `shard_state_transition(shard, slot, shard_state, get_block_root_at_slot(state, state.slot - 1), get_shard_proposer_index(state, shard, slot), proposal)` returns a result and does not throw an exception. Let `choices` be the set of non-empty valid proposals you discover.
    * If `len(choices) == 0`, do `proposals.append(make_empty_proposal(shard_state, slot))`
    * If `len(choices) == 1`, do `proposals.append(choices[0])`
    * If `len(choices) > 1`, let `winning_proposal` be the proposal with the largest number of total attestations from slots in `state.shard_next_slots[shard]....slot-1` supporting it or any of its descendants, breaking ties by choosing the first proposal locally seen. Do `proposals.append(winning_proposal)`.
    * If `proposals[-1]` is NOT an empty proposal, set `shard_state = shard_state_transition(shard, slot, shard_state, get_block_root_at_slot(state, state.slot - 1), get_shard_proposer_index(state, shard, slot), proposals[-1])` and do `shard_states.append(shard_state)`. If it is an empty proposal, leave `shard_state` unchanged.

Make an attestation using `shard_data_roots = [hash_tree_root(proposal) for proposal in proposals]` and `shard_state_roots = shard_states`.
