# Ethereum 2.0 Phase 1 -- Shard Data Chains

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- TOC -->

- [Ethereum 2.0 Phase 1 -- Shard Data Chains](#ethereum-20-phase-1----shard-data-chains)
    - [Table of contents](#table-of-contents)
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
        - [`ShardBlock`](#shardblock)
        - [`ShardBlockHeader`](#shardblockheader)
        - [`ShardState`](#shardstate)
        - [`ShardCheckpoint`](#shardcheckpoint)
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
            - [Block body fee](#block-body-fee)
    - [Shard fork choice rule](#shard-fork-choice-rule)

<!-- /TOC -->

## Introduction

This document describes the shard transition function (data layer only) and the shard fork choice rule as part of Phase 1 of Ethereum 2.0.

## Custom types

| Name | SSZ equivalent | Description |
| - | - | - |
| `ShardSlot` | `uint64` | a shard slot number |
| `GweiDelta` | `int64` | a signed Gwei delta |

## Configuration

### Misc

| Name | Value |
| - | - |
| `MIN_BLOCK_SIZE_PRICE` | `2**0` (= 1) |
| `MAX_PERIOD_COMMITTEE_SIZE` | `2**7` (= 128) |
| `SHARD_HEADER_SIZE` | `2**9` (= 512) |
| `SHARD_BLOCK_SIZE_TARGET` | `2**14` (= 16,384) |
| `SHARD_BLOCK_SIZE_LIMIT` | `2**16` (= 65,536) |

### Initial values

| Name | Value |
| - | - |
| `SHARD_GENESIS_EPOCH` | **TBD** |

### Time parameters

| Name | Value | Unit | Duration |
| - | - | :-: | :-: |
| `SHARD_SLOTS_PER_EPOCH` | `2**7` (= 128) | shard slots | 6.4 minutes |
| `EPOCHS_PER_SHARD_PERIOD` | `2**8` (= 256) | epochs | ~27 hours |

### State list lengths

| Name | Value | Unit |
| - | - | :-: |
| `HISTORY_ACCUMULATOR_VECTOR` | `2**6` (= 64) | state tree maximum depth |

### Rewards and penalties

| Name | Value |
| - | - |
| `SHARD_BLOCK_SIZE_PRICE_QUOTIENT` | `2**3` (= 8) |

### Signature domain types

| Name | Value |
| - | - |
| `DOMAIN_SHARD_PROPOSER` | `128` |
| `DOMAIN_SHARD_ATTESTER` | `129` |

## Containers

### `ShardBlock`

```python
class ShardBlock(FlatContainer):
    shard: Shard
    slot: ShardSlot
    beacon_block_root: Hash
    parent_root: Hash
    state_root: Hash
    block_size_sum: uint64
    body: List[byte, SHARD_BLOCK_SIZE_LIMIT - SHARD_HEADER_SIZE]
    attestation_bits: Bitvector[2 * MAX_PERIOD_COMMITTEE_SIZE]
    attestation_signature: BLSSignature
    signature: BLSSignature
```

### `ShardBlockHeader`

```python
class ShardBlockHeader(FlatContainer):
    shard: Shard
    slot: ShardSlot
    beacon_block_root: Hash
    parent_root: Hash
    state_root: Hash
    block_size_sum: uint64
    body_root: List[byte, SHARD_BLOCK_SIZE_LIMIT - SHARD_HEADER_SIZE]
    attestation_bits: Bitvector[2 * MAX_PERIOD_COMMITTEE_SIZE]
    attestation_signature: BLSSignature
    signature: BLSSignature
```

### `ShardState`

```python
class ShardState(FlatContainer):
    shard: Shard
    slot: ShardSlot
    history_accumulator: Vector[Hash, HISTORY_ACCUMULATOR_VECTOR]
    latest_block_header: ShardBlockHeader
    block_size_sum: uint64
    # Fees and rewards
    block_body_price: Gwei
    older_committee_deltas: Vector[GweiDelta, MAX_PERIOD_COMMITTEE_SIZE]
    newer_committee_deltas: Vector[GweiDelta, MAX_PERIOD_COMMITTEE_SIZE]
```

### `ShardCheckpoint`

```python
class ShardCheckpoint(Container):
    slot: ShardSlot
    parent_root: Hash
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
def get_period_committee(state: BeaconState, shard: Shard, epoch: Epoch) -> Sequence[ValidatorIndex]:
    active_validator_indices = get_active_validator_indices(state, epoch)
    seed = get_seed(state, epoch)
    return compute_committee(active_validator_indices, seed, shard, SHARD_COUNT)[:MAX_PERIOD_COMMITTEE_SIZE]
```

#### `get_shard_committee`

```python
def get_shard_committee(state: BeaconState, shard: Shard, epoch: Epoch) -> Sequence[ValidatorIndex]:
    older_committee = get_period_committee(state, shard, compute_shard_period_start_epoch(epoch, 2))
    newer_committee = get_period_committee(state, shard, compute_shard_period_start_epoch(epoch, 1))
    # Every epoch cycle out validators from the older committee and cycle in validators from the newer committee
    older_subcommittee = [i for i in older_committee if i % EPOCHS_PER_SHARD_PERIOD > epoch % EPOCHS_PER_SHARD_PERIOD]
    newer_subcommittee = [i for i in newer_committee if i % EPOCHS_PER_SHARD_PERIOD <= epoch % EPOCHS_PER_SHARD_PERIOD]
    return older_subcommittee + newer_subcommittee
```

#### `get_shard_proposer_index`

```python
def get_shard_proposer_index(state: BeaconState, shard: Shard, slot: ShardSlot) -> ValidatorIndex:
    epoch = get_current_epoch(state)
    shard_committee = get_shard_committee(state, shard, epoch)
    active_indices = [i for i in shard_committee if is_active_validator(state.validators[i], epoch)]
    seed = hash(get_seed(state, epoch) + int_to_bytes(slot, length=8) + int_to_bytes(shard, length=8))
    compute_proposer_index(state, active_indices, seed)
```

### Shard state mutators

#### `process_delta`

```python
def process_delta(state: BeaconState, shard_state: ShardState, index: ValidatorIndex, delta: GweiDelta) -> None:
    epoch = compute_epoch_of_shard_slot(state.slot)
    older_committee = get_period_committee(state, shard_state.shard, compute_shard_period_start_epoch(epoch, 2))
    newer_committee = get_period_committee(state, shard_state.shard, compute_shard_period_start_epoch(epoch, 1))
    if index in older_committee:
        shard_state.older_committee_deltas[older_committee.index(index)] += delta
    elif index in newer_committee:
        shard_state.newer_committee_deltas[newer_committee.index(index)] += delta
```

## Genesis

### `get_genesis_shard_state`

```python
def get_genesis_shard_state(state: BeaconState, shard: Shard) -> ShardState:
    return ShardState(
        shard=shard,
        slot=ShardSlot(SHARD_GENESIS_EPOCH * SHARD_SLOTS_PER_EPOCH),
        block_body_price=MIN_BLOCK_SIZE_PRICE,
    )
```

### `get_genesis_shard_block`

```python
def get_genesis_shard_block(state: BeaconState, shard: Shard) -> ShardBlock:
    return ShardBlock(
        shard=shard,
        slot=ShardSlot(SHARD_GENESIS_EPOCH * SHARD_SLOTS_PER_EPOCH),
        state_root=hash_tree_root(get_genesis_shard_state(state, shard)),
    )
```

## Shard state transition function

```python
def shard_state_transition(state: BeaconState,
                           shard_state: ShardState,
                           block: ShardBlock,
                           validate_state_root: bool=False) -> ShardState:
    # Process slots (including those with no blocks) since block
    process_shard_slots(state, shard_state, block.slot)
    # Process block
    process_shard_block(state, shard_state, block)
    # Validate state root (`validate_state_root == True` in production)
    if validate_state_root:
        assert block.state_root == hash_tree_root(shard_state)
    # Return post-state
    return shard_state
```

```python
def process_shard_slots(state: BeaconState, shard_state: ShardState, slot: ShardSlot) -> None:
    assert shard_state.slot <= slot
    while shard_state.slot < slot:
        process_shard_slot(state, shard_state)
        # Process period on the start slot of the next period
        if (shard_state.slot + 1) % (SHARD_SLOTS_PER_EPOCH * EPOCHS_PER_SHARD_PERIOD) == 0:
            process_shard_period(state, shard_state)
        shard_state.slot += ShardSlot(1)
```

```python
def process_shard_slot(state: BeaconState, shard_state: ShardState) -> None:
    # Cache state root
    previous_state_root = hash_tree_root(state)
    if state.latest_block_header.state_root == Bytes32():
        state.latest_block_header.state_root = previous_state_root
    # Cache state root in history accumulator
    depth = 0
    while state.slot % 2**depth == 0 and depth < HISTORY_ACCUMULATOR_VECTOR:
        state.history_accumulator[depth] = previous_state_root
        depth += 1
```

### Period processing

```python
def process_shard_period(state: BeaconState, shard_state: ShardState) -> None:
    # Rotate rewards and fees
    state.older_committee_deltas = state.newer_committee_deltas
    state.newer_committee_deltas = [GweiDelta(0) for _ in range(MAX_PERIOD_COMMITTEE_SIZE)]
```

### Block processing

```python
def process_shard_block(state: BeaconState, shard_state: ShardState, block: ShardBlock) -> None:
    process_shard_block_header(state, shard_state, block)
    process_shard_attestations(state, shard_state, block)
    process_shard_block_body_fee(state, shard_state, block)
```

#### Block header

```python
def process_shard_block_header(state: BeaconState, shard_state: ShardState, block: ShardBlock) -> None:
    # Verify that the slots match
    assert block.slot == state.slot
    # Verify that the beacon chain root matches
    parent_epoch = compute_epoch_of_shard_slot(state.latest_block_header.slot)
    assert block.beacon_block_root == get_block_root(state, parent_epoch)
    # Verify that the parent matches
    assert block.parent_root == hash_tree_root(state.latest_block_header)
    # Save current block as the new latest block
    state.latest_block_header = ShardBlockHeader(
        shard=block.shard,
        slot=block.slot,
        beacon_block_root=block.beacon_block_root,
        parent_root=block.parent_root,
        # `state_root` is zeroed and overwritten in the next `process_shard_slot` call
        block_size_sum=block.block_size_sum,
        body_root=hash_tree_root(block.body),
        attestation_bits=block.attestation_bits,
        attestation_signature=block.attestation_signature,
        # `signature` is zeroed
    )
    # Verify proposer signature
    proposer_index = get_shard_proposer_index(state, state.shard, block.slot)
    pubkey = state.validators[proposer_index].pubkey
    domain = get_domain(state, DOMAIN_SHARD_PROPOSER, compute_epoch_of_shard_slot(block.slot))
    assert bls_verify(pubkey, hash_tree_root(block.block), block.proposer, domain)
    # Verify body size is a multiple of the header size
    assert len(block.body) % SHARD_HEADER_SIZE == 0
    # Verify the sum of the block sizes since genesis
    state.block_size_sum += SHARD_HEADER_SIZE + len(block.body)
    assert block.block_size_sum == state.block_size_sum
```

#### Attestations

```python
def process_shard_attestations(state: BeaconState, shard_state: ShardState, block: ShardBlock) -> None:
    pubkeys = []
    attestation_count = 0
    shard_committee = get_shard_committee(state, state.shard, block.slot)
    for i, validator_index in enumerate(shard_committee):
        if block.attestation_bits[i]:
            pubkeys.append(state.validators[validator_index].pubkey)
            process_delta(state, shard_state, validator_index, get_base_reward(state, validator_index))
            attestation_count += 1
    # Verify there are no extraneous bits set beyond the shard committee
    for i in range(len(shard_committee), 2 * MAX_PERIOD_COMMITTEE_SIZE):
        assert block.attestation_bits[i] == 0b0
    # Verify attester aggregate signature
    domain = get_domain(state, DOMAIN_SHARD_ATTESTER, compute_epoch_of_shard_slot(block.slot))
    message = hash_tree_root(ShardCheckpoint(shard_state.slot, block.parent_root))
    assert bls_verify(bls_aggregate_pubkeys(pubkeys), message, block.attestation_signature, domain)
    # Proposer micro-reward
    proposer_index = get_shard_proposer_index(state, state.shard, block.slot)
    reward = attestation_count * get_base_reward(state, proposer_index) // PROPOSER_REWARD_QUOTIENT
    process_delta(state, shard_state, proposer_index, reward)
```

#### Block body fee

```python
def process_shard_block_body_fee(state: BeaconState, shard_state: ShardState, block: ShardBlock) -> None:
    # Apply proposer block body fee
    proposer_index = get_shard_proposer_index(state, state.shard, block.slot)
    block_body_fee = state.block_body_price * len(block.body) // SHARD_BLOCK_SIZE_LIMIT
    process_delta(state, shard_state, proposer_index, -block_body_fee)  # Burn
    process_delta(state, shard_state, proposer_index, block_body_fee // PROPOSER_REWARD_QUOTIENT)  # Reward
    # Calculate new block body price
    block_size = SHARD_HEADER_SIZE + len(block.body)
    QUOTIENT = SHARD_BLOCK_SIZE_LIMIT * SHARD_BLOCK_SIZE_PRICE_QUOTIENT
    price_delta = GweiDelta(state.block_body_price * (block_size - SHARD_BLOCK_SIZE_TARGET) // QUOTIENT)
    if price_delta > 0:
        # The maximum gas price caps the amount burnt on gas fees within a period
        MAX_BLOCK_SIZE_PRICE = MAX_EFFECTIVE_BALANCE // EPOCHS_PER_SHARD_PERIOD // SHARD_SLOTS_PER_EPOCH
        state.block_body_price = Gwei(min(MAX_BLOCK_SIZE_PRICE, state.block_body_price + price_delta))
    else:
        state.block_body_price = Gwei(max(MIN_BLOCK_SIZE_PRICE, state.block_body_price + price_delta))
```

## Shard fork choice rule

The fork choice rule for any shard is LMD GHOST using the shard attestations of the shard committee and the beacon chain attestations of the crosslink committee currently assigned to that shard, but instead of being rooted in the genesis it is rooted in the block referenced in the most recent accepted crosslink (i.e. `state.crosslinks[shard].shard_block_root`). Only blocks whose `beacon_block_root` is the block in the main beacon chain at the specified `slot` should be considered. (If the beacon chain skips a slot, then the block at that slot is considered to be the block in the beacon chain at the highest slot lower than that slot.)
