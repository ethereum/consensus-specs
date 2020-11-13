# Ethereum 2.0 Light Client Support: Beacon Chain Changes

## Table of contents

- [Introduction](#introduction)
- [Configuration](#configuration)
  - [Domain types](#domain-types)
  - [Misc](#misc)
- [Updated containers](#updated-containers)
  - [Extended `BeaconBlockBody`](#extended-beaconblockbody)
  - [Extended `BeaconState`](#extended-beaconstate)
- [New containers](#new-containers)
  - [`CompactCommittee`](#compactcommittee)
- [Helper functions](#helper-functions)
  - [Misc](#misc-1)
    - [`pack_compact_validator`](#pack_compact_validator)
    - [`unpack_compact_validator`](#unpack_compact_validator)
    - [`committee_to_compact_committee`](#committee_to_compact_committee)
  - [Beacon state accessors](#beacon-state-accessors)
    - [`get_light_client_committee`](#get_light_client_committee)
  - [Block processing](#block-processing)
    - [Light client processing](#light-client-processing)
  - [Epoch processing](#epoch-transition)
    - [Light client committee updates](#light-client-committee-updates)
  
## Introduction

This is a standalone patch to the ethereum beacon chain that adds light client support.

## Configuration

### Misc

| Name | Value |
| - | - | 
| `LIGHT_CLIENT_COMMITTEE_SIZE` | `uint64(2**7)` (= 128) |
| `LIGHT_CLIENT_COMMITTEE_PERIOD` | `Epoch(2**8)` (= 256) | epochs | ~27 hours |
| `BASE_REWARDS_PER_EPOCH` | 5 |

### Domain types

| Name | Value |
| - | - |
| `DOMAIN_LIGHT_CLIENT` | `DomainType('0x82000000')` |

## Updated containers

### Extended `BeaconBlockBody`

```python
class BeaconBlockBody(phase0.BeaconBlockBody):
    # Bitfield of participants in this light client signature
    light_client_bits: Bitvector[LIGHT_CLIENT_COMMITTEE_SIZE]
    light_client_signature: BLSSignature
```

### Extended `BeaconState`

```python
class BeaconState(phase0.BeaconState):
    # Compact representations of the light client committee
    current_light_committee: CompactCommittee
    next_light_committee: CompactCommittee
```

## New containers

### `CompactCommittee`

```python
class CompactCommittee(Container):
    pubkeys: List[BLSPubkey, MAX_VALIDATORS_PER_COMMITTEE]
    compact_validators: List[uint64, MAX_VALIDATORS_PER_COMMITTEE]
```

## Helper functions

### Misc


#### `pack_compact_validator`

```python
def pack_compact_validator(index: ValidatorIndex, slashed: bool, balance_in_increments: uint64) -> uint64:
    """
    Create a compact validator object representing index, slashed status, and compressed balance.
    Takes as input balance-in-increments (// EFFECTIVE_BALANCE_INCREMENT) to preserve symmetry with
    the unpacking function.
    """
    return (index << 16) + (slashed << 15) + balance_in_increments
```

#### `unpack_compact_validator`

```python
def unpack_compact_validator(compact_validator: uint64) -> Tuple[ValidatorIndex, bool, uint64]:
    """
    Return validator index, slashed, balance // EFFECTIVE_BALANCE_INCREMENT
    """
    return (
        ValidatorIndex(compact_validator >> 16),
        bool((compact_validator >> 15) % 2),
        compact_validator & (2**15 - 1),
    )
```

#### `committee_to_compact_committee`

```python
def committee_to_compact_committee(state: BeaconState, committee: Sequence[ValidatorIndex]) -> CompactCommittee:
    """
    Given a state and a list of validator indices, outputs the ``CompactCommittee`` representing them.
    """
    validators = [state.validators[i] for i in committee]
    compact_validators = [
        pack_compact_validator(i, v.slashed, v.effective_balance // EFFECTIVE_BALANCE_INCREMENT)
        for i, v in zip(committee, validators)
    ]
    pubkeys = [v.pubkey for v in validators]
    return CompactCommittee(pubkeys=pubkeys, compact_validators=compact_validators)
```

### Beacon state accessors

#### `get_light_client_committee`

```python
def get_light_client_committee(beacon_state: BeaconState, epoch: Epoch) -> Sequence[ValidatorIndex]:
    """
    Return the light client committee of no more than ``LIGHT_CLIENT_COMMITTEE_SIZE`` validators.
    """
    source_epoch = (max(epoch // LIGHT_CLIENT_COMMITTEE_PERIOD, 1) - 1) * LIGHT_CLIENT_COMMITTEE_PERIOD
    active_validator_indices = get_active_validator_indices(beacon_state, source_epoch)
    seed = get_seed(beacon_state, source_epoch, DOMAIN_LIGHT_CLIENT)
    return [
        compute_shuffled_index(i, active_validator_indices, seed)
        for i in range(min(active_validator_indices, LIGHT_CLIENT_COMMITTEE_SIZE))
    ]
```

### Block processing

```python
def process_block(state: BeaconState, block: BeaconBlock) -> None:
    phase0.process_block(state, block)
    process_light_client_signature(state, block.body)
```

#### Light client processing

```python
def process_light_client_signature(state: BeaconState, block_body: BeaconBlockBody) -> None:
    committee = get_light_client_committee(state, get_current_epoch(state))
    previous_slot = max(state.slot, 1) - 1
    previous_block_root = get_block_root_at_slot(state, previous_slot)

    # Light client committees sign over the previous block root
    signing_root = compute_signing_root(
        previous_block_root,
        get_domain(state, DOMAIN_LIGHT_CLIENT, compute_epoch_at_slot(previous_slot))
    )
    
    participants = [
        committee[i] for i in range(len(committee)) if block_body.light_client_bits[i]
    ]
    
    signer_pubkeys = [
        state.validators[participant].pubkey for participant in participants
    ]
    
    assert bls.FastAggregateVerify(signer_pubkeys, signing_root, block_body.light_client_signature)
    
    # Process rewards
    total_reward = Gwei(0)
    active_validator_count = len(get_active_validator_indices(beacon_state, get_current_epoch(state)))
    for participant in participants:
        reward = get_base_reward(state, participant) * active_validator_count // len(committee) // SLOTS_PER_EPOCH
        increase_balance(state, participant, reward)
        total_reward += reward        

    increase_balance(state, get_beacon_proposer_index(state), Gwei(total_reward // PROPOSER_REWARD_QUOTIENT))
```

### Epoch processing

This epoch transition overrides the phase0 epoch transition:

```python
def process_epoch(state: BeaconState) -> None:
    phase0.process_epoch(state)
    process_light_client_committee_updates(state)
```

#### Light client committee updates

```python
def process_light_client_committee_updates(state: BeaconState) -> None:
    """
    Update light client committees.
    """
    next_epoch = compute_epoch_at_slot(Slot(state.slot + 1))
    if next_epoch % LIGHT_CLIENT_COMMITTEE_PERIOD == 0:
        state.current_light_committee = state.next_light_committee
        new_committee = get_light_client_committee(state, next_epoch + LIGHT_CLIENT_COMMITTEE_PERIOD)
        state.next_light_committee = committee_to_compact_committee(state, new_committee)
```

