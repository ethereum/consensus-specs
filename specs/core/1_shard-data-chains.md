# Ethereum 2.0 Phase 1 -- Shard Data Chains

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->


- [Introduction](#introduction)
- [Custom types](#custom-types)
- [Configuration](#configuration)
  - [Misc](#misc)
  - [Initial values](#initial-values)
  - [Time parameters](#time-parameters)
  - [State list lengths](#state-list-lengths)
  - [Rewards and penalties](#rewards-and-penalties)
  - [Signature domain types](#signature-domain-types)
- [Containers](#containers)
  - [`Crosslink`](#crosslink)
  - [`ShardBlock`](#shardblock)
  - [`ShardBlockHeader`](#shardblockheader)
  - [`ShardState`](#shardstate)
  - [`ShardAttestationData`](#shardattestationdata)
- [Helper functions](#helper-functions)
  - [Misc](#misc-1)
    - [`compute_epoch_of_shard_slot`](#compute_epoch_of_shard_slot)
    - [`compute_shard_period_start_epoch`](#compute_shard_period_start_epoch)
  - [Beacon state accessors](#beacon-state-accessors)
    - [`get_period_committee`](#get_period_committee)
    - [`get_shard_committee`](#get_shard_committee)
    - [`get_shard_proposer_index`](#get_shard_proposer_index)
  - [Shard state mutators](#shard-state-mutators)
    - [`process_delta`](#process_delta)
- [Genesis](#genesis)
  - [`get_genesis_shard_state`](#get_genesis_shard_state)
  - [`get_genesis_shard_block`](#get_genesis_shard_block)
- [Shard state transition function](#shard-state-transition-function)
  - [Period processing](#period-processing)
  - [Block processing](#block-processing)
    - [Block header](#block-header)
    - [Attestations](#attestations)
    - [Block body](#block-body)
- [Shard fork choice rule](#shard-fork-choice-rule)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This document describes the shard transition function (data layer only) and the shard fork choice rule as part of Phase 1 of Ethereum 2.0.

## Custom types

| Name | SSZ equivalent | Description |
| - | - | - |
| `Shard` | `uint64` | a shard number |
| `ShardSlot` | `uint64` | a shard slot number |

## Configuration

### Misc

| Name | Value |
| - | - |
| `SHARD_COUNT` | `2**10` (= 1,024) |
| `MIN_BLOCK_BODY_PRICE` | `2**0` (= 1) |
| `MAX_PERIOD_COMMITTEE_SIZE` | `2**7` (= 128) |
| `SHARD_HEADER_SIZE` | `2**10` (= 1024) |
| `SHARD_BLOCK_SIZE_TARGET` | `2**14` (= 16,384) |
| `MAX_SHARD_BLOCK_SIZE` | `2**16` (= 65,536) |

### Initial values

| Name | Value | Unit |
| - | - |
| `SHARD_GENESIS_EPOCH` | **TBD** | Epoch |

### Time parameters

| Name | Value | Unit | Duration |
| - | - | :-: | :-: |
| `SHARD_SLOTS_PER_EPOCH` | `2**7` (= 128) | shard slots | 6.4 minutes |
| `EPOCHS_PER_SHARD_PERIOD` | `2**8` (= 256) | epochs | ~27 hours |

### State list lengths

| Name | Value |
| - | - |
| `HISTORY_ACCUMULATOR_DEPTH` | `2**6` (= 64) |

### Rewards and penalties

| Name | Value |
| - | - |
| `BLOCK_BODY_PRICE_QUOTIENT` | `2**3` (= 8) |

### Signature domain types

| Name | Value |
| - | - |
| `DOMAIN_SHARD_PROPOSER` | `0x80000000` |
| `DOMAIN_SHARD_ATTESTER` | `0x81000000` |

## Containers

### `Crosslink`

```python
# Crosslink is a placeholder to appease the build script until phase 1 is reworked
class Crosslink(Container):
    shard: Shard
```
 
### `ShardBlock`

```python
class ShardBlock(Container):
    shard: Shard
    slot: ShardSlot
    beacon_block_root: Root
    parent_root: Root
    state_root: Root
    body: List[byte, MAX_SHARD_BLOCK_SIZE - SHARD_HEADER_SIZE]
    block_size_sum: uint64
    aggregation_bits: Bitvector[2 * MAX_PERIOD_COMMITTEE_SIZE]
    attestations: BLSSignature
    signature: BLSSignature
```

### `ShardBlockHeader`

```python
class ShardBlockHeader(Container):
    shard: Shard
    slot: ShardSlot
    beacon_block_root: Root
    parent_root: Root
    state_root: Root
    body_root: Root
    block_size_sum: uint64
    aggregation_bits: Bitvector[2 * MAX_PERIOD_COMMITTEE_SIZE]
    attestations: BLSSignature
    signature: BLSSignature
```

### `ShardState`

```python
class ShardState(Container):
    shard: Shard
    slot: ShardSlot
    history_accumulator: Vector[Bytes32, HISTORY_ACCUMULATOR_DEPTH]
    latest_block_header: ShardBlockHeader
    block_size_sum: uint64
    # Fees and rewards
    block_body_price: Gwei
    older_committee_positive_deltas: Vector[Gwei, MAX_PERIOD_COMMITTEE_SIZE]
    older_committee_negative_deltas: Vector[Gwei, MAX_PERIOD_COMMITTEE_SIZE]
    newer_committee_positive_deltas: Vector[Gwei, MAX_PERIOD_COMMITTEE_SIZE]
    newer_committee_negative_deltas: Vector[Gwei, MAX_PERIOD_COMMITTEE_SIZE]
```

### `ShardAttestationData`

```python
class ShardAttestationData(Container):
    slot: ShardSlot
    parent_root: Root
```

## Helper functions

### Misc

#### `compute_epoch_of_shard_slot`

```python
def compute_epoch_of_shard_slot(slot: ShardSlot) -> Epoch:
    return Epoch(slot // SHARD_SLOTS_PER_EPOCH)
```

#### `compute_shard_period_start_epoch`

```python
def compute_shard_period_start_epoch(epoch: Epoch, lookback: uint64) -> Epoch:
    return Epoch(epoch - (epoch % EPOCHS_PER_SHARD_PERIOD) - lookback * EPOCHS_PER_SHARD_PERIOD)
```

### Beacon state accessors

#### `get_period_committee`

```python
def get_period_committee(beacon_state: BeaconState, shard: Shard, epoch: Epoch) -> Sequence[ValidatorIndex]:
    active_validator_indices = get_active_validator_indices(beacon_state, epoch)
    seed = get_seed(beacon_state, epoch, DOMAIN_SHARD_ATTESTER)
    return compute_committee(active_validator_indices, seed, shard, SHARD_COUNT)[:MAX_PERIOD_COMMITTEE_SIZE]
```

#### `get_shard_committee`

```python
def get_shard_committee(beacon_state: BeaconState, shard: Shard, epoch: Epoch) -> Sequence[ValidatorIndex]:
    older_committee = get_period_committee(beacon_state, shard, compute_shard_period_start_epoch(epoch, 2))
    newer_committee = get_period_committee(beacon_state, shard, compute_shard_period_start_epoch(epoch, 1))
    # Every epoch cycle out validators from the older committee and cycle in validators from the newer committee
    older_subcommittee = [i for i in older_committee if i % EPOCHS_PER_SHARD_PERIOD > epoch % EPOCHS_PER_SHARD_PERIOD]
    newer_subcommittee = [i for i in newer_committee if i % EPOCHS_PER_SHARD_PERIOD <= epoch % EPOCHS_PER_SHARD_PERIOD]
    return older_subcommittee + newer_subcommittee
```

#### `get_shard_proposer_index`

```python
def get_shard_proposer_index(beacon_state: BeaconState, shard: Shard, slot: ShardSlot) -> ValidatorIndex:
    epoch = get_current_epoch(beacon_state)
    shard_committee = get_shard_committee(beacon_state, shard, epoch)
    active_indices = [i for i in shard_committee if is_active_validator(beacon_state.validators[i], epoch)]
    assert any(active_indices)

    epoch_seed = get_seed(beacon_state, epoch, DOMAIN_SHARD_PROPOSER)
    seed = hash(epoch_seed + int_to_bytes(slot, length=8) + int_to_bytes(shard, length=8))
    return compute_proposer_index(beacon_state, active_indices, seed)
```

### Shard state mutators

#### `process_delta`

```python
def process_delta(beacon_state: BeaconState,
                  shard_state: ShardState,
                  index: ValidatorIndex,
                  delta: Gwei,
                  positive: bool=True) -> None:
    epoch = compute_epoch_of_shard_slot(shard_state.slot)
    older_committee = get_period_committee(beacon_state, shard_state.shard, compute_shard_period_start_epoch(epoch, 2))
    newer_committee = get_period_committee(beacon_state, shard_state.shard, compute_shard_period_start_epoch(epoch, 1))
    if index in older_committee:
        if positive:
            shard_state.older_committee_positive_deltas[older_committee.index(index)] += delta
        else:
            shard_state.older_committee_negative_deltas[older_committee.index(index)] += delta
    elif index in newer_committee:
        if positive:
            shard_state.newer_committee_positive_deltas[newer_committee.index(index)] += delta
        else:
            shard_state.newer_committee_negative_deltas[newer_committee.index(index)] += delta
```

## Genesis

### `get_genesis_shard_state`

```python
def get_genesis_shard_state(shard: Shard) -> ShardState:
    return ShardState(
        shard=shard,
        slot=ShardSlot(SHARD_GENESIS_EPOCH * SHARD_SLOTS_PER_EPOCH),
        latest_block_header=ShardBlockHeader(
            shard=shard,
            slot=ShardSlot(SHARD_GENESIS_EPOCH * SHARD_SLOTS_PER_EPOCH),
            body_root=hash_tree_root(List[byte, MAX_SHARD_BLOCK_SIZE - SHARD_HEADER_SIZE]()),
        ),
        block_body_price=MIN_BLOCK_BODY_PRICE,
    )
```

### `get_genesis_shard_block`

```python
def get_genesis_shard_block(shard: Shard) -> ShardBlock:
    return ShardBlock(
        shard=shard,
        slot=ShardSlot(SHARD_GENESIS_EPOCH * SHARD_SLOTS_PER_EPOCH),
        state_root=hash_tree_root(get_genesis_shard_state(shard)),
    )
```

## Shard state transition function

```python
def shard_state_transition(beacon_state: BeaconState,
                           shard_state: ShardState,
                           block: ShardBlock,
                           validate_state_root: bool=False) -> ShardState:
    # Process slots (including those with no blocks) since block
    process_shard_slots(shard_state, block.slot)
    # Process block
    process_shard_block(beacon_state, shard_state, block)
    # Validate state root (`validate_state_root == True` in production)
    if validate_state_root:
        assert block.state_root == hash_tree_root(shard_state)
    # Return post-state
    return shard_state
```

```python
def process_shard_slots(shard_state: ShardState, slot: ShardSlot) -> None:
    assert shard_state.slot <= slot
    while shard_state.slot < slot:
        process_shard_slot(shard_state)
        # Process shard period on the start slot of the next shard period
        if (shard_state.slot + 1) % (SHARD_SLOTS_PER_EPOCH * EPOCHS_PER_SHARD_PERIOD) == 0:
            process_shard_period(shard_state)
        shard_state.slot += ShardSlot(1)
```

```python
def process_shard_slot(shard_state: ShardState) -> None:
    # Cache state root
    previous_state_root = hash_tree_root(shard_state)
    if shard_state.latest_block_header.state_root == Bytes32():
        shard_state.latest_block_header.state_root = previous_state_root
    # Cache state root in history accumulator
    depth = 0
    while shard_state.slot % 2**depth == 0 and depth < HISTORY_ACCUMULATOR_DEPTH:
        shard_state.history_accumulator[depth] = previous_state_root
        depth += 1
```

### Period processing

```python
def process_shard_period(shard_state: ShardState) -> None:
    # Rotate committee deltas
    shard_state.older_committee_positive_deltas = shard_state.newer_committee_positive_deltas
    shard_state.older_committee_negative_deltas = shard_state.newer_committee_negative_deltas
    shard_state.newer_committee_positive_deltas = [Gwei(0) for _ in range(MAX_PERIOD_COMMITTEE_SIZE)]
    shard_state.newer_committee_negative_deltas = [Gwei(0) for _ in range(MAX_PERIOD_COMMITTEE_SIZE)]
```

### Block processing

```python
def process_shard_block(beacon_state: BeaconState, shard_state: ShardState, block: ShardBlock) -> None:
    process_shard_block_header(beacon_state, shard_state, block)
    process_shard_attestations(beacon_state, shard_state, block)
    process_shard_block_body(beacon_state, shard_state, block)
```

#### Block header

```python
def process_shard_block_header(beacon_state: BeaconState, shard_state: ShardState, block: ShardBlock) -> None:
    # Verify the shard number
    assert block.shard == shard_state.shard
    # Verify the slot number
    assert block.slot == shard_state.slot
    # Verify the beacon chain root
    epoch = compute_epoch_of_shard_slot(shard_state.slot)
    assert epoch * SLOTS_PER_EPOCH == beacon_state.slot
    beacon_block_header = BeaconBlockHeader(
        slot=beacon_state.latest_block_header.slot,
        parent_root=beacon_state.latest_block_header.parent_root,
        state_root=beacon_state.latest_block_header.state_root,
        body_root=beacon_state.latest_block_header.body_root,
    )
    if beacon_block_header.state_root == Bytes32():
        beacon_block_header.state_root = hash_tree_root(beacon_state)
    assert block.beacon_block_root == hash_tree_root(beacon_block_header)
    # Verify the parent root
    assert block.parent_root == hash_tree_root(shard_state.latest_block_header)
    # Save current block as the new latest block
    shard_state.latest_block_header = ShardBlockHeader(
        shard=block.shard,
        slot=block.slot,
        beacon_block_root=block.beacon_block_root,
        parent_root=block.parent_root,
        # `state_root` is zeroed and overwritten in the next `process_shard_slot` call
        body_root=hash_tree_root(block.body),
        block_size_sum=block.block_size_sum,
        aggregation_bits=block.aggregation_bits,
        attestations=block.attestations,
        # `signature` is zeroed
    )
    # Verify the sum of the block sizes since genesis
    shard_state.block_size_sum += SHARD_HEADER_SIZE + len(block.body)
    assert block.block_size_sum == shard_state.block_size_sum
    # Verify proposer is not slashed
    proposer_index = get_shard_proposer_index(beacon_state, shard_state.shard, block.slot)
    proposer = beacon_state.validators[proposer_index]
    assert not proposer.slashed
    # Verify proposer signature
    domain = get_domain(beacon_state, DOMAIN_SHARD_PROPOSER, compute_epoch_of_shard_slot(block.slot))
    assert bls_verify(proposer.pubkey, hash_tree_root(block), block.signature, domain)
```

#### Attestations

```python
def process_shard_attestations(beacon_state: BeaconState, shard_state: ShardState, block: ShardBlock) -> None:
    pubkeys = []
    attestation_count = 0
    shard_committee = get_shard_committee(beacon_state, shard_state.shard, block.slot)
    for i, validator_index in enumerate(shard_committee):
        if block.aggregation_bits[i]:
            pubkeys.append(beacon_state.validators[validator_index].pubkey)
            process_delta(beacon_state, shard_state, validator_index, get_base_reward(beacon_state, validator_index))
            attestation_count += 1
    # Verify there are no extraneous bits set beyond the shard committee
    for i in range(len(shard_committee), 2 * MAX_PERIOD_COMMITTEE_SIZE):
        assert block.aggregation_bits[i] == 0b0
    # Verify attester aggregate signature
    domain = get_domain(beacon_state, DOMAIN_SHARD_ATTESTER, compute_epoch_of_shard_slot(block.slot))
    message = hash_tree_root(ShardAttestationData(slot=shard_state.slot, parent_root=block.parent_root))
    assert bls_verify(bls_aggregate_pubkeys(pubkeys), message, block.attestations, domain)
    # Proposer micro-reward
    proposer_index = get_shard_proposer_index(beacon_state, shard_state.shard, block.slot)
    reward = attestation_count * get_base_reward(beacon_state, proposer_index) // PROPOSER_REWARD_QUOTIENT
    process_delta(beacon_state, shard_state, proposer_index, Gwei(reward))
```

#### Block body

```python
def process_shard_block_body(beacon_state: BeaconState, shard_state: ShardState, block: ShardBlock) -> None:
    # Verify block body size is a multiple of the header size
    assert len(block.body) % SHARD_HEADER_SIZE == 0
    # Apply proposer block body fee
    block_body_fee = shard_state.block_body_price * len(block.body) // MAX_SHARD_BLOCK_SIZE
    proposer_index = get_shard_proposer_index(beacon_state, shard_state.shard, block.slot)
    process_delta(beacon_state, shard_state, proposer_index, Gwei(block_body_fee), positive=False)  # Burn
    process_delta(beacon_state, shard_state, proposer_index, Gwei(block_body_fee // PROPOSER_REWARD_QUOTIENT))  # Reward
    # Calculate new block body price
    block_size = SHARD_HEADER_SIZE + len(block.body)
    QUOTIENT = MAX_SHARD_BLOCK_SIZE * BLOCK_BODY_PRICE_QUOTIENT
    if block_size > SHARD_BLOCK_SIZE_TARGET:
        price_delta = Gwei(shard_state.block_body_price * (block_size - SHARD_BLOCK_SIZE_TARGET) // QUOTIENT)
        # The maximum block body price caps the amount burnt on fees within a shard period
        MAX_BLOCK_BODY_PRICE = MAX_EFFECTIVE_BALANCE // EPOCHS_PER_SHARD_PERIOD // SHARD_SLOTS_PER_EPOCH
        shard_state.block_body_price = Gwei(min(MAX_BLOCK_BODY_PRICE, shard_state.block_body_price + price_delta))
    else:
        price_delta = Gwei(shard_state.block_body_price * (SHARD_BLOCK_SIZE_TARGET - block_size) // QUOTIENT)
        shard_state.block_body_price = Gwei(max(MIN_BLOCK_BODY_PRICE, shard_state.block_body_price + price_delta))
```

## Shard fork choice rule

The fork choice rule for any shard is LMD GHOST using the shard attestations of the shard committee and the beacon chain attestations of the crosslink committee currently assigned to that shard, but instead of being rooted in the genesis it is rooted in the block referenced in the most recent accepted crosslink (i.e. `beacon_state.crosslinks[shard].shard_block_root`). Only blocks whose `beacon_block_root` is the block in the main beacon chain at the specified `slot` should be considered. (If the beacon chain skips a slot, then the block at that slot is considered to be the block in the beacon chain at the highest slot lower than that slot.)
