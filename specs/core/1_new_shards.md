# Ethereum 2.0 Phase 1 -- Crosslinks and Shard Data

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- TOC -->

- [Ethereum 2.0 Phase 1 -- Shard Data Chains](#ethereum-20-phase-1----shard-data-chains)
    - [Table of contents](#table-of-contents)
    - [Introduction](#introduction)
    - [Configuration](#configuration)
        - [Misc](#misc)
    - [Containers](#containers)
    - [Beacon Chain Changes](#beacon-chain-changes)
        - [New state variables](#new-state-variables)

<!-- /TOC -->

## Introduction

This document describes the shard transition function (data layer only) and the shard fork choice rule as part of Phase 1 of Ethereum 2.0.

## Configuration

### Misc

| Name | Value |
| - | - |
| `MAX_SHARDS` | `2**10` (= 1024) |
| `ACTIVE_SHARDS` | `2**6` (= 64) |
| `SHARD_ROOT_HISTORY_LENGTH` | `2**15` (= 32,768) |
| `MAX_CATCHUP` | `2**3` (= 8) |

## Containers

### `AttestationData`

```python
class AttestationData(Container):
    # Slot
    slot: Slot
    # Shard
    shard: shard
    # LMD GHOST vote
    beacon_block_root: Hash
    # FFG vote
    source: Checkpoint
    target: Checkpoint
    # Shard data roots
    shard_data_roots: List[Hash, MAX_CATCHUP]
    # Intermediate state roots
    shard_state_roots: List[Hash, MAX_CATCHUP]
```

### `Attestation`

```python
class Attestation(Container):
    aggregation_bits: Bitlist[MAX_VALIDATORS_PER_COMMITTEE]
    data: AttestationData
    custody_bits: List[Bitlist[MAX_VALIDATORS_PER_COMMITTEE], MAX_CATCHUP]
    signature: BLSSignature
```

## Beacon Chain Changes

### New state variables

```
    shard_state_roots: Vector[Hash, MAX_SHARDS]
    shard_next_slot: Vector[Slot, MAX_SHARDS]
```

### Attestation processing

```python
def process_attestation(state: BeaconState, attestation: Attestation) -> None:
    data = attestation.data
    assert shard < ACTIVE_SHARDS

    # Signature check
    committee = get_crosslink_committee(state, get_current_epoch(state), data.shard)
    for bits in attestation.custody_bits + [attestation.aggregation_bits]:
        assert bits == len(committee)
    # Check signature
    assert is_valid_indexed_attestation(state, get_indexed_attestation(state, attestation))
    
    # Type 1: on-time attestations
    if data.custody_bits != []:
        # Correct start slot
        assert data.slot == state.shard_next_slot[data.shard]
        # Correct data root count
        assert len(data.shard_data_roots) == len(attestation.custody_bits) == len(data.shard_state_roots) == min(state.slot - data.slot, MAX_CATCHUP)
        # Correct parent block root
        assert data.beacon_block_root == get_block_root_at_slot(state, state.slot - 1)
        # Apply
        online_indices = get_online_indices(state)
        attesting_indices = get_attesting_indices(state, attestation.data, attestation.aggregation_bits).intersection(get_online_indices)
        if get_total_balance(state, attesting_indices) * 3 >= get_total_balance(state, online_indices) * 2:
            state.shard_state_roots[data.shard] = data.shard_state_roots[-1]
            state.shard_next_slot[data.shard] += len(data.shard_data_roots)
        
    # Type 2: delayed attestations
    else:
        assert slot_to_epoch(data.slot) in (get_current_epoch(state), get_previous_epoch(state))
        assert len(data.shard_data_roots) == len(data.intermediate_state_roots) == 0

    pending_attestation = PendingAttestation(
        slot=data.slot,
        shard=data.shard,
        aggregation_bits=attestation.aggregation_bits,
        inclusion_delay=state.slot - attestation_slot,
        proposer_index=get_beacon_proposer_index(state),
    )

    if data.target.epoch == get_current_epoch(state):
        assert data.source == state.current_justified_checkpoint
        state.current_epoch_attestations.append(pending_attestation)
    else:
        assert data.source == state.previous_justified_checkpoint
        state.previous_epoch_attestations.append(pending_attestation)
```

### Fraud proofs

TODO. The intent is to have a single universal fraud proof type, which contains (i) an on-time attestation on shard `s` signing a set of `data_roots`, (ii) an index `i` of a particular data root to focus on, (iii) the full contents of the i'th data, (iii) a Merkle proof to the `shard_state_roots` in the parent block the attestation is referencing, and which then verifies that one of the two conditions is false:

* `custody_bits[i][j] != generate_custody_bit(subkey, block_contents)` for any `j`
* `execute_state_transition(slot, shard, attestation.shard_state_roots[i-1], parent.shard_state_roots, block_contents) != shard_state_roots[i]` (if `i=0` then instead use `parent.shard_state_roots[s]`)

For phase 1, we will use a simple state transition function:

* Check that `data[:32] == prev_state_root`
* Check that `bls_verify(get_shard_proposer(state, slot, shard), hash_tree_root(data[-96:]), BLSSignature(data[-96:]), BLOCK_SIGNATURE_DOMAIN)`
* Output the new state root: `hash_tree_root(prev_state_root, other_prev_state_roots, data)`

### Honest persistent committee member behavior

Suppose you are a persistent committee member on shard `i` at slot `s`. Suppose `state.shard_next_slots[i] = s-1` ("the happy case"). In this case, you look for a valid proposal that satisfies the checks in the state transition function above, and if you see such a proposal `data` with post-state `post_state`, make an attestation with `shard_data_roots = [hash_tree_root(data)]` and `shard_state_roots = [post_state]`. If you do not find such a proposal, make an attestation using the "default empty proposal", `data = prev_state_root + b'\x00' * 96`.

Now suppose `state.shard_next_slots[i] = s-k` for `k>1`. Then, initialize `data = []`, `states = []`, `state = state.shard_state_roots[i]`. For `slot in (state.shard_next_slot, min(state.shard_next_slot + MAX_CATCHUP, s))`, do:

* Look for all valid proposals for `slot` whose first 32 bytes equal to `state`. If there are none, add a default empty proposal to `data`. If there is one such proposal `p`, add `p` to `data`. If there is more than one, select the one with the largest number of total attestations supporting it or its descendants, and add it to `data`.
* Set `state` to the state after processing the proposal just added to `data`; append it to `states`

Make an attestation using `shard_data_roots = data` and `shard_state_roots = states`.
