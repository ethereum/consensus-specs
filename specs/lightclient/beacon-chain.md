# Ethereum 2.0 Light Client Support

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Constants](#constants)
- [Configuration](#configuration)
  - [Constants](#constants-1)
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
  - [`Predicates`](#predicates)
    - [`eth2_fast_aggregate_verify`](#eth2_fast_aggregate_verify)
  - [Beacon state accessors](#beacon-state-accessors)
    - [`get_sync_committee_indices`](#get_sync_committee_indices)
    - [`get_sync_committee`](#get_sync_committee)
  - [Block processing](#block-processing)
    - [Sync committee processing](#sync-committee-processing)
  - [Epoch processing](#epoch-processing)
    - [Components of attestation deltas](#components-of-attestation-deltas)
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

### Constants

| Name | Value |
| - | - |
| `G2_POINT_AT_INFINITY` | `BLSSignature(b'\xc0' + b'\x00' * 95)` |

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

#### `BeaconBlockBody`

```python
class BeaconBlockBody(phase0.BeaconBlockBody):
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

### `Predicates`

#### `eth2_fast_aggregate_verify`

```python
def eth2_fast_aggregate_verify(pubkeys: Sequence[BLSPubkey], message: Bytes32, signature: BLSSignature) -> bool:
    """
    Wrapper to ``bls.FastAggregateVerify`` accepting the ``G2_POINT_AT_INFINITY`` signature when ``pubkeys`` is empty.
    """
    if len(pubkeys) == 0 and signature == G2_POINT_AT_INFINITY:
        return True
    return bls.FastAggregateVerify(pubkeys, message, signature)
```

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
    i = 0
    sync_committee_indices: List[ValidatorIndex] = []
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
    return SyncCommittee(pubkeys=pubkeys, pubkey_aggregates=aggregates)
```

### Block processing

```python
def process_block(state: BeaconState, block: BeaconBlock) -> None:
    process_block_header(state, block)
    process_randao(state, block.body)
    process_eth1_data(state, block.body)
    process_operations(state, block.body)
    # Light client support
    process_sync_committee(state, block.body)
```

#### Sync committee processing

```python
def process_sync_committee(state: BeaconState, body: BeaconBlockBody) -> None:
    # Verify sync committee aggregate signature signing over the previous slot block root
    previous_slot = Slot(max(int(state.slot), 1) - 1)
    committee_indices = get_sync_committee_indices(state, get_current_epoch(state))
    participant_indices = [index for index, bit in zip(committee_indices, body.sync_committee_bits) if bit]
    committee_pubkeys = state.current_sync_committee.pubkeys
    participant_pubkeys = [pubkey for pubkey, bit in zip(committee_pubkeys, body.sync_committee_bits) if bit]
    domain = get_domain(state, DOMAIN_SYNC_COMMITTEE, compute_epoch_at_slot(previous_slot))
    signing_root = compute_signing_root(get_block_root_at_slot(state, previous_slot), domain)
    assert eth2_fast_aggregate_verify(participant_pubkeys, signing_root, body.sync_committee_signature)

    # Reward sync committee participants
    total_proposer_reward = Gwei(0)
    active_validator_count = uint64(len(get_active_validator_indices(state, get_current_epoch(state))))
    for participant_index in participant_indices:
        base_reward = get_base_reward(state, participant_index)
        proposer_reward = get_proposer_reward(state, participant_index)
        max_participant_reward = base_reward - proposer_reward
        reward = Gwei(max_participant_reward * active_validator_count // len(committee_indices) // SLOTS_PER_EPOCH)
        increase_balance(state, participant_index, reward)
        total_proposer_reward += proposer_reward

    # Reward beacon proposer
    increase_balance(state, get_beacon_proposer_index(state), total_proposer_reward)
```

### Epoch processing

#### Components of attestation deltas

*Note*: The function `get_inactivity_penalty_deltas` is modified with `BASE_REWARDS_PER_EPOCH` replaced by `BASE_REWARDS_PER_EPOCH - 1`.

```python
def get_inactivity_penalty_deltas(state: BeaconState) -> Tuple[Sequence[Gwei], Sequence[Gwei]]:
    """
    Return inactivity reward/penalty deltas for each validator.
    """
    penalties = [Gwei(0) for _ in range(len(state.validators))]
    if is_in_inactivity_leak(state):
        matching_target_attestations = get_matching_target_attestations(state, get_previous_epoch(state))
        matching_target_attesting_indices = get_unslashed_attesting_indices(state, matching_target_attestations)
        for index in get_eligible_validator_indices(state):
            # Penalize validator so that optimal attestation performance is rewarded with one base reward per epoch
            base_reward = get_base_reward(state, index)
            penalties[index] += Gwei((BASE_REWARDS_PER_EPOCH - 1) * base_reward - get_proposer_reward(state, index))
            if index not in matching_target_attesting_indices:
                effective_balance = state.validators[index].effective_balance
                penalties[index] += Gwei(effective_balance * get_finality_delay(state) // INACTIVITY_PENALTY_QUOTIENT)

    # No rewards associated with inactivity penalties
    rewards = [Gwei(0) for _ in range(len(state.validators))]
    return rewards, penalties
```

#### Final updates

*Note*: The function `process_final_updates` is modified to handle sync committee updates.

```python
def process_final_updates(state: BeaconState) -> None:
    # FIXME: unfold the full `process_final_updates` to avoid side effects.
    phase0.process_final_updates(state)
    next_epoch = get_current_epoch(state) + Epoch(1)
    if next_epoch % EPOCHS_PER_SYNC_COMMITTEE_PERIOD == 0:
        state.current_sync_committee = state.next_sync_committee
        state.next_sync_committee = get_sync_committee(state, next_epoch + EPOCHS_PER_SYNC_COMMITTEE_PERIOD)
```
