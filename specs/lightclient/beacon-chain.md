# Ethereum 2.0 Light Client Support

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->


- [Introduction](#introduction)
- [Constants](#constants)
- [Configuration](#configuration)
  - [Misc](#misc)
  - [Time parameters](#time-parameters)
  - [Domain types](#domain-types)
- [Containers](#containers)
  - [Extended containers](#extended-containers)
    - [`BeaconBlockBody`](#beaconblockbody)
    - [`BeaconState`](#beaconstate)
  - [New containers](#new-containers)
    - [`SyncCommittee`](#synccommittee)
- [Helper functions](#helper-functions)
  - [Beacon state accessors](#beacon-state-accessors)
    - [`get_sync_committee_indices`](#get_sync_committee_indices)
    - [`get_sync_committee`](#get_sync_committee)
  - [Block processing](#block-processing)
    - [Sync committee processing](#sync-committee-processing)
  - [Epoch processing](#epoch-processing)
    - [Final updates](#final-updates)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This is a standalone beacon chain patch adding light client support via sync committees.

## Constants

| Name | Value |
| - | - | 
| `BASE_REWARDS_PER_EPOCH` | `uint64(5)` |

## Configuration

### Misc

| Name | Value |
| - | - | 
| `SYNC_COMMITTEE_SIZE` | `uint64(2**10)` (= 1024) |
| `SYNC_COMMITTEE_PUBKEY_AGGREGATES_SIZE` | `uint64(2**6)` (= 64) |

### Time parameters

| Name | Value | Unit | Duration |
| - | - | :-: | :-: |
| `EPOCHS_PER_SYNC_COMMITTEE_PERIOD` | `Epoch(2**8)` (= 256) | epochs | ~27 hours |

### Domain types

| Name | Value |
| - | - |
| `DOMAIN_SYNC_COMMITTEE` | `DomainType('0x07000000')` |

## Containers

### Extended containers

*Note*: Extended SSZ containers inherit all fields from the parent in the original
order and append any additional fields to the end.

#### `BeaconBlock`

```python
class BeaconBlock(phase0.BeaconBlock):
    # Sync committee aggregate signature
    sync_committee_bits: Bitvector[SYNC_COMMITTEE_SIZE]
    sync_committee_signature: BLSSignature
```

#### `BeaconBlockHeader`

```python
class BeaconBlockHeader(phase0.BeaconBlockHeader):
    # Sync committee aggregate signature
    sync_committee_bits: Bitvector[SYNC_COMMITTEE_SIZE]
    sync_committee_signature: BLSSignature
```


#### `BeaconState`

```python
class BeaconState(phase0.BeaconState):
    # Sync committees
    current_sync_committee: SyncCommittee
    next_sync_committee: SyncCommittee
```

### New containers

#### `SyncCommittee`

```python
class SyncCommittee(Container):
    pubkeys: Vector[BLSPubkey, SYNC_COMMITTEE_SIZE]
    pubkey_aggregates: Vector[BLSPubkey, SYNC_COMMITTEE_SIZE // SYNC_COMMITTEE_PUBKEY_AGGREGATES_SIZE]
```

## Helper functions

### Beacon state accessors

#### `get_sync_committee_indices`

```python
def get_sync_committee_indices(state: BeaconState, epoch: Epoch) -> Sequence[ValidatorIndex]:
    """
    Return the sync committee indices for a given state and epoch.
    """
    MAX_RANDOM_BYTE = 2**8 - 1
    base_epoch = Epoch((max(epoch // EPOCHS_PER_SYNC_COMMITTEE_PERIOD, 1) - 1) * EPOCHS_PER_SYNC_COMMITTEE_PERIOD)
    active_validator_indices = get_active_validator_indices(state, base_epoch)
    active_validator_count = uint64(len(active_validator_indices))
    seed = get_seed(state, base_epoch, DOMAIN_SYNC_COMMITTEE)
    i, sync_committee_indices = 0, []
    while len(sync_committee_indices) < SYNC_COMMITTEE_SIZE:
        shuffled_index = compute_shuffled_index(uint64(i % active_validator_count), active_validator_count, seed)
        candidate_index = active_validator_indices[shuffled_index]
        random_byte = hash(seed + uint_to_bytes(uint64(i // 32)))[i % 32]
        effective_balance = state.validators[candidate_index].effective_balance
        if effective_balance * MAX_RANDOM_BYTE >= MAX_EFFECTIVE_BALANCE * random_byte:
            sync_committee_indices.append(candidate_index)
        i += 1
    return sync_committee_indices
```

#### `get_sync_committee`

```python
def get_sync_committee(state: BeaconState, epoch: Epoch) -> SyncCommittee:
    """
    Return the sync committee for a given state and epoch.
    """
    indices = get_sync_committee_indices(state, epoch)
    validators = [state.validators[index] for index in indices]
    pubkeys = [validator.pubkey for validator in validators]
    aggregates = [
        bls.AggregatePKs(pubkeys[i:i + SYNC_COMMITTEE_PUBKEY_AGGREGATES_SIZE])
        for i in range(0, len(pubkeys), SYNC_COMMITTEE_PUBKEY_AGGREGATES_SIZE)
    ]
    return SyncCommittee(pubkeys, aggregates)
```

### Block processing

```python
def process_block(state: BeaconState, block: BeaconBlock) -> None:
    phase0.process_block(state, block)
    process_sync_committee(state, block)
```

#### Sync committee processing

```python
def process_sync_committee(state: BeaconState, block: BeaconBlock) -> None:
    # Verify sync committee aggregate signature signing over the previous slot block root
    previous_slot = Slot(max(state.slot, 1) - 1)
    committee_indices = get_sync_committee_indices(state, get_current_epoch(state))
    participant_indices = [index for index, bit in zip(committee_indices, body.sync_committee_bits) if bit]
    committee_pubkeys = state.current_sync_committee.pubkeys
    participant_pubkeys = [pubkey for pubkey, bit in zip(committee_pubkeys, body.sync_committee_bits) if bit]
    domain = get_domain(state, DOMAIN_SYNC_COMMITTEE, compute_epoch_at_slot(previous_slot))
    signing_root = compute_signing_root(get_block_root_at_slot(state, previous_slot), domain)
    assert bls.FastAggregateVerify(participant_pubkeys, signing_root, block.sync_committee_signature)

    # Reward sync committee participants
    participant_rewards = Gwei(0)
    active_validator_count = uint64(len(get_active_validator_indices(state, get_current_epoch(state))))
    for participant_index in participant_indices:
        base_reward = get_base_reward(state, participant_index)
        reward = Gwei(base_reward * active_validator_count // len(committee_indices) // SLOTS_PER_EPOCH)
        increase_balance(state, participant_index, reward)
        participant_rewards += reward

    # Reward beacon proposer
    increase_balance(state, get_beacon_proposer_index(state), Gwei(participant_rewards // PROPOSER_REWARD_QUOTIENT))
```

### Epoch processing

#### Final updates

```python
def process_final_updates(state: BeaconState) -> None:
    phase0.process_final_updates(state)
    next_epoch = get_current_epoch(state) + Epoch(1)
    if next_epoch % EPOCHS_PER_SYNC_COMMITTEE_PERIOD == 0:
        state.current_sync_committee = state.next_sync_committee
        state.next_sync_committee = get_sync_committee(state, next_epoch + EPOCHS_PER_SYNC_COMMITTEE_PERIOD)
```
