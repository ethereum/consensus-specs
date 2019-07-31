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
        - [Signature domain types](#signature-domain-types)
        - [TODO PLACEHOLDER](#todo-placeholder)
    - [Data structures](#data-structures)
        - [`ShardBlockHeader`](#shardblockheader)
        - [`ShardBlock`](#shardblock)
        - [`ShardBlockSignatures`](#shardblocksignatures)
        - [`ShardBlockCore`](#shardblockcore)
        - [`ExtendedShardBlockCore`](#extendedshardblockcore)
        - [`ShardState`](#shardstate)
        - [`ShardReceiptDelta`](#shardreceiptdelta)
    - [Helper functions](#helper-functions)
        - [`compute_slot_of_shard_slot`](#compute_slot_of_shard_slot)
        - [`compute_epoch_of_shard_slot`](#compute_epoch_of_shard_slot)
        - [`get_shard_period_start_epoch`](#get_shard_period_start_epoch)
        - [`get_period_committee`](#get_period_committee)
        - [`get_persistent_committee`](#get_persistent_committee)
        - [`get_shard_block_proposer_index`](#get_shard_block_proposer_index)
        - [`get_shard_header`](#get_shard_header)
        - [`pad`](#pad)
        - [`flatten_shard_header`](#flatten_shard_header)
        - [`compute_crosslink_data_root`](#compute_crosslink_data_root)
        - [`get_default_shard_state`](#get_default_shard_state)
    - [Object validity](#object-validity)
        - [Shard block validation: preliminary](#shard-block-validation-preliminary)
        - [Shard state transition function helpers](#shard-state-transition-function-helpers)
        - [Shard state transition function](#shard-state-transition-function)
        - [Beacon attestations](#beacon-attestations)
    - [Shard fork choice rule](#shard-fork-choice-rule)

<!-- /TOC -->

## Introduction

This document describes the shard data layer and the shard fork choice rule in Phase 1 of Ethereum 2.0.

## Custom types

We define the following Python custom types for type hinting and readability:

| Name | SSZ equivalent | Description |
| - | - | - |
| `ShardSlot` | `uint64` | a slot number in shard chain |

## Configuration

### Misc

| Name | Value |
| - | - |
| `SHARD_HEADER_SIZE` | `2**9` (= 512) |
| `SHARD_BLOCK_SIZE_LIMIT` | `2**16` (= 65,536) |
| `SHARD_BLOCK_SIZE_TARGET` | `2**14` (= 16,384) |
| `SHARD_SLOTS_PER_BEACON_SLOT` | `2**1` (= 2) |
| `MAX_PERSISTENT_COMMITTEE_SIZE` | `2**7` (= 128) |
| `REWARD_COEFFICIENT_BASE` | `2**20` ( = 1,048,576) |
| `BASEFEE_ADJUSTMENT_FACTOR` | `2**3` (= 8) |

### Initial values

| Name | Value |
| - | - |
| `PHASE_1_FORK_EPOCH` | **TBD** |
| `PHASE_1_FORK_SLOT` | **TBD** |
| `GENESIS_SHARD_SLOT` | 0 |

### Time parameters

| Name | Value | Unit | Duration |
| - | - | :-: | :-: |
| `CROSSLINK_LOOKBACK` | `2**0` (= 1) | epochs | 6.4 minutes |
| `EPOCHS_PER_SHARD_PERIOD` | `2**8` (= 256) | epochs | ~27 hours |

### Signature domain types

The following types are defined, mapping into `DomainType` (little endian):

| Name | Value |
| - | - |
| `DOMAIN_SHARD_PROPOSER` | `128` |
| `DOMAIN_SHARD_ATTESTER` | `129` |

### TODO PLACEHOLDER

| Name | Value |
| - | - |
| `PLACEHOLDER` | `2**3` |

## Data structures

_Note: the shard block header structure is carefully designed so that all of the values have the same depth in a hash tree implementation, so `hash_tree_root(SSZ_partial(x)) == hash_tree_root(x)` (using the "left-to-right leaves" scheme [here](https://github.com/ethereum/eth2.0-specs/issues/1303)), which allows shard block headers to look like an SSZ object when in the crosslink structure. This is done by balancing it so that 7 or 8 items are on the left side (the "core") and two 96-byte (ie. 3*2 = 6 chunk) items are on the right side. Change with care._

### `ShardBlockHeader`

```python
class ShardBlockHeader(Container):
    core: ShardBlockCore
    signatures: ShardBlockSignatures
```

### `ShardBlock`

```python
class ShardBlock(Container):
    core: ExtendedShardBlockCore
    signatures: ShardBlockSignatures
```

### `ShardBlockSignatures`

```python
class ShardBlockSignatures(Container):
    attestation_signature: BLSSignature
    proposer_signature: BLSSignature
```

### `ShardBlockCore`

```python
class ShardBlockCore(Container):
    slot: ShardSlot
    beacon_chain_root: Hash
    parent_root: Hash
    data_root: Hash
    state_root: Hash
    total_bytes: uint64
    attester_bitfield: Bitvector[MAX_PERSISTENT_COMMITTEE_SIZE * 2]
```

### `ExtendedShardBlockCore`

```python
class ExtendedShardBlockCore(Container):
    slot: ShardSlot
    beacon_chain_root: Hash
    parent_root: Hash
    data: Bytes[SHARD_BLOCK_SIZE_LIMIT - SHARD_HEADER_SIZE]
    state_root: Hash
    total_bytes: uint64
    attester_bitfield: Bitvector[MAX_PERSISTENT_COMMITTEE_SIZE * 2]
```

### `ShardState`

```python
class ShardState(Container):
    history_acc: Vector[Hash, 64]
    earlier_committee_rewards: List[uint64, MAX_PERSISTENT_COMMITTEE_SIZE]
    later_committee_rewards: List[uint64, MAX_PERSISTENT_COMMITTEE_SIZE]
    earlier_committee_fees: List[Gwei, MAX_PERSISTENT_COMMITTEE_SIZE]
    later_committee_fees: List[Gwei, MAX_PERSISTENT_COMMITTEE_SIZE]
    basefee: Gwei
    slot: ShardSlot
    shard: Shard
    most_recent_block_core: ShardBlockCore
    receipt_root: Hash
```

### `ShardReceiptDelta`

```python
class ShardReceiptDelta(Container):
    index: ValidatorIndex
    reward_coefficient: uint64
    block_fee: Gwei
```

## Helper functions

### `compute_slot_of_shard_slot`

```python
def compute_slot_of_shard_slot(slot: ShardSlot) -> Epoch:
    return Epoch(slot // SHARD_SLOTS_PER_BEACON_SLOT)
```

### `compute_epoch_of_shard_slot`

```python
def compute_epoch_of_shard_slot(slot: ShardSlot) -> Epoch:
    return Epoch(slot // SHARD_SLOTS_PER_BEACON_SLOT // SLOTS_PER_EPOCH)
```

### `get_shard_period_start_epoch`

```python
def get_shard_period_start_epoch(epoch: Epoch, lookback: uint64=0) -> Epoch:
    return Epoch(epoch - (epoch % EPOCHS_PER_SHARD_PERIOD) - lookback * EPOCHS_PER_SHARD_PERIOD)
```

### `get_period_committee`

```python
def get_period_committee(state: BeaconState,
                         epoch: Epoch,
                         shard: Shard) -> List[ValidatorIndex, MAX_PERSISTENT_COMMITTEE_SIZE]:
    """
    Return committee for a period. Used to construct persistent committees.
    """
    full_committee = compute_committee(
        indices=get_active_validator_indices(state, epoch),
        seed=get_seed(state, epoch),
        index=shard,
        count=SHARD_COUNT,
    )

    return full_committee[:MAX_PERSISTENT_COMMITTEE_SIZE]
```

### `get_persistent_committee`

```python
def get_persistent_committee(state: BeaconState,
                             shard: Shard,
                             slot: ShardSlot) -> Sequence[ValidatorIndex]:
    """
    Return the persistent committee for the given ``shard`` at the given ``slot``.
    """
    epoch = compute_epoch_of_shard_slot(slot)

    earlier_committee = get_period_committee(state, get_shard_period_start_epoch(epoch, lookback=2), shard)
    later_committee = get_period_committee(state, get_shard_period_start_epoch(epoch, lookback=1), shard)

    # Take not-yet-cycled-out validators from earlier committee and already-cycled-in validators from
    # later committee; return a sorted list of the union of the two, deduplicated
    return sorted(set(
        [i for i in earlier_committee if epoch % EPOCHS_PER_SHARD_PERIOD < i % EPOCHS_PER_SHARD_PERIOD]
        + [i for i in later_committee if epoch % EPOCHS_PER_SHARD_PERIOD >= i % EPOCHS_PER_SHARD_PERIOD]
    ))
```

### `get_shard_block_proposer_index`

```python
def get_shard_block_proposer_index(state: BeaconState,
                                   shard: Shard,
                                   slot: ShardSlot) -> Optional[ValidatorIndex]:
    # Randomly shift persistent committee
    persistent_committee = list(get_persistent_committee(state, shard, slot))
    current_epoch = get_current_epoch(state)

    active_indices = [i for i in persistent_committee if is_active_validator(state.validators[i], current_epoch)]
    if not any(active_indices):
        return None

    MAX_RANDOM_BYTE = 2**8 - 1
    seed = hash(get_seed(state, current_epoch) + int_to_bytes(shard, length=8) + int_to_bytes(slot, length=8))
    i = 0
    while True:
        candidate_index = active_indices[(slot + i) % len(active_indices)]
        random_byte = hash(seed + int_to_bytes(i // 32, length=8))[i % 32]
        effective_balance = state.validators[candidate_index].effective_balance
        if effective_balance * MAX_RANDOM_BYTE >= MAX_EFFECTIVE_BALANCE * random_byte:
            return ValidatorIndex(candidate_index)
        i += 1
```

### `get_shard_header`

```python
def get_shard_header(block: ShardBlock) -> ShardBlockHeader:
    return ShardBlockHeader(
        core=ShardBlockCore(
            slot=block.core.slot,
            beacon_chain_root=block.core.beacon_chain_root,
            parent_root=block.core.parent_root,
            data_root=hash_tree_root(block.core.data),
            state_root=block.core.state_root,
            total_bytes=block.core.total_bytes,
            attester_bitfield=block.core.attester_bitfield
        ),
        signatures=block.signatures
    )
```

### `pad`

```python
def pad(x: bytes, length: int) -> bytes:
    assert len(x) <= length
    return x + b'\x00' * (length - len(x))
```

### `flatten_shard_header`

```python
def flatten_shard_header(header: ShardBlockHeader) -> Bytes[SHARD_HEADER_SIZE]:
    """
    Converts a shard block header into a flat object with the same hash tree root. Used
    in the crosslink construction.
    """
    committee_size = len(header.core.attester_bitfield)
    attester_bits = [header.core.attester_bitfield[i] if i < committee_size else 0 for i in range(256)]
    attester_bytes = bytes([sum([attester_bits[i + j] << j for j in range(8)]) for i in range(0, 256, 8)])
    return (
        pad(int_to_bytes(header.core.slot, length=8), 32) +
        header.core.beacon_chain_root +
        header.core.parent_root +
        header.core.data_root +
        header.core.state_root +
        pad(int_to_bytes(header.core.total_bytes, length=8), 32) +
        attester_bytes +
        b'\x00' * 32 +
        pad(header.signatures.attestation_signature, 128) +
        pad(header.signatures.proposer_signature, 128)
    )
```

### `compute_crosslink_data_root`

```python
def compute_crosslink_data_root(blocks: Sequence[ShardBlock]) -> Hash:
    header = b''.join([flatten_shard_header(get_shard_header(block)) for block in blocks])
    footer = b''.join([block.core.data for block in blocks])
    MAX_SIZE = SHARD_BLOCK_SIZE_LIMIT * SHARD_SLOTS_PER_BEACON_SLOT * SLOTS_PER_EPOCH * MAX_EPOCHS_PER_CROSSLINK
    return hash_tree_root(BytesN[MAX_SIZE](pad(header + footer, MAX_SIZE)))
```

### `get_default_shard_state`

```python
def get_default_shard_state(beacon_state: BeaconState, shard: Shard) -> ShardState:
    earlier_committee = get_period_committee(beacon_state, PHASE_1_FORK_SLOT - SHARD_SLOTS_PER_BEACON_SLOT * SLOTS_PER_EPOCH * EPOCHS_PER_SHARD_PERIOD * 2, shard)
    later_committee = get_period_committee(beacon_state, PHASE_1_FORK_SLOT - SHARD_SLOTS_PER_BEACON_SLOT * SLOTS_PER_EPOCH * EPOCHS_PER_SHARD_PERIOD, shard)
    return ShardState(
        basefee=1,
        shard=shard,
        slot=PHASE_1_FORK_SLOT,
        earlier_committee_rewards=[REWARD_COEFFICIENT_BASE for _ in range(len(earlier_committee))],
        later_committee_rewards=[REWARD_COEFFICIENT_BASE for _ in range(len(later_committee))],
        earlier_committee_fees=[0 for _ in range(len(earlier_committee))],
        later_committee_fees=[0 for _ in range(len(later_committee))],        
    )
```

## Object validity

### Shard block validation: preliminary

Accept a shard block `block` only if all of the following are correct:

* Either `block.core.parent_root == Hash()` or a block `parent` such that `hash_tree_root(parent.core) == block.core.parent_root` has already been accepted.
* `block.core.beacon_chain_root == get_block_root(head_beacon_state, compute_epoch_of_shard_slot(parent.core.slot))` where `head_beacon_state` is the current beacon chain head state. Alternatively phrased, a beacon chain block `beacon_ref` such that `signing_root(beacon_ref) == block.core.beacon_chain_root` has already been accepted and is part of the canonical chain, and no block with slot `beacon_ref.slot < slot <= compute_start_slot_of_epoch(compute_epoch_of_shard_slot(parent.core.slot))` is part of the canonical chain.
* Let `beacon_state` be the state where `beacon_ref.state_root == hash_tree_root(beacon_state)`. Let `prev_state` be the post-state of the `parent` if the `parent` exists, otherwise let it be `get_default_shard_state(beacon_state, shard)` (defined below). `block.core.state_root` must equal the `hash_tree_root` of the state after applying `shard_state_transition(prev_state, beacon_state, block)`.

Note that these acceptance conditions depend on the canonical beacon chain; when the canonical beacon chain reorganizes, the eligibility of shard blocks should be re-evaluated.

### Shard state transition function helpers

```python
def add_reward(state: ShardState, beacon_state: BeaconState, index: ValidatorIndex, delta: Gwei) -> None:
    epoch = compute_epoch_of_shard_slot(state.slot)
    earlier_committee = get_period_committee(beacon_state, get_shard_period_start_epoch(epoch, lookback=2), state.shard)
    later_committee = get_period_committee(beacon_state, get_shard_period_start_epoch(epoch, lookback=1), state.shard)
    if index in earlier_committee:
        state.earlier_committee_rewards[earlier_committee.index(index)] += delta
    elif index in later_committee:
        state.later_committee_rewards[later_committee.index(index)] += delta
    else:
        raise Exception("Should never be here")
```

```python
def add_fee(state: ShardState, beacon_state: BeaconState, index: ValidatorIndex, delta: Gwei) -> None:
    epoch = compute_epoch_of_shard_slot(state.slot)
    earlier_committee = get_period_committee(beacon_state, get_shard_period_start_epoch(epoch, lookback=2), state.shard)
    later_committee = get_period_committee(beacon_state, get_shard_period_start_epoch(epoch, lookback=1), state.shard)
    if index in earlier_committee:
        state.earlier_committee_fees[earlier_committee.index(index)] += delta
    elif index in later_committee:
        state.later_committee_fees[later_committee.index(index)] += delta
    else:
        raise Exception("Should never be here")
```

### Shard state transition function

```python
def shard_state_transition(state: ShardState, beacon_state: BeaconState, block: ShardBlock) -> None:
    assert block.core.slot > state.slot
    for slot in range(state.slot, block.core.slot):
        shard_slot_transition(state, beacon_state)
    shard_block_transition(state, beacon_state, block)
```

```python
def shard_slot_transition(state: ShardState, beacon_state: BeaconState) -> None:
    # Correct saved state root
    if state.most_recent_block_core.state_root == Hash():
        state.most_recent_block_core.state_root = hash_tree_root(state)
    
    # Save states in history accumulator
    depth = 0
    h = hash_tree_root(state)
    while state.slot % 2**depth == 0:
        state.history_acc[depth] = h
        
    # Period transitions
    if (state.slot + 1) % (SHARD_SLOTS_PER_BEACON_SLOT * SLOTS_PER_EPOCH * EPOCHS_PER_SHARD_PERIOD) == 0:
        epoch = compute_epoch_of_shard_slot(state.slot)
        earlier_committee = get_period_committee(beacon_state, get_shard_period_start_epoch(epoch, lookback=2), state.shard)
        later_committee = get_period_committee(beacon_state, get_shard_period_start_epoch(epoch, lookback=1), state.shard)
        state.receipt_root = hash_tree_root(List[ShardReceiptDelta, PLACEHOLDER]([
            ShardReceiptDelta(index, state.earlier_committee_rewards[i], state.earlier_committee_fees[i])
            for i, index in enumerate(committee)
        ]))
        state.earlier_committee_rewards = state.later_committee_rewards
        state.earlier_committee_fees = state.later_committee_fees
        state.later_committee_rewards = [REWARD_COEFFICIENT_BASE for _ in range(len(later_committee))],
        state.later_committee_fees = [0 for _ in range(len(later_committee))],
    else:
        state.receipt_root = Hash()
    state.slot += 1
```

```python
def shard_block_transition(state: ShardState, beacon_state: BeaconState, block: ShardBlock) -> None:
    # Check slot number
    assert candidate.core.slot == state.slot
    
    # Check parent block
    if candidate.core.parent_root != Hash():
        assert candidate.core.parent_root == hash_tree_root(state.most_recent_block_core)
        
    # Calculate base reward
    total_balance = get_total_active_balance(beacon_state)
    base_reward = Gwei(REWARD_COEFFICIENT_BASE * BASE_REWARD_FACTOR // integer_squareroot(total_balance) // BASE_REWARDS_PER_EPOCH)
    
    # Check attestations
    attester_committee = get_persistent_committee(beacon_state, shard, block.core.slot)
    pubkeys = []
    attestations = 0
    
    for i, index in enumerate(attester_committee):
        if block.core.attester_bitfield[i]:
            pubkeys.append(beacon_state.validators[index].pubkey)
            add_reward(state, beacon_state, index, base_reward)
            attestations += 1
            
    for i in range(len(attester_committee), MAX_PERSISTENT_COMMITTEE_SIZE):
        assert block.attester_bitfield[i] is False
        
    assert bls_verify(
        pubkey=bls_aggregate_pubkeys(pubkeys),
        message_hash=candidate.core.parent_root,
        signature=candidate.signatures.attestation_signature,
        domain=get_domain(beacon_state, DOMAIN_SHARD_ATTESTER, compute_epoch_of_shard_slot(candidate.core.slot))
    )

    # Check proposer
    proposer_index = get_shard_block_proposer_index(beacon_state, shard, candidate.core.slot)
    assert proposer_index is not None
    add_reward(state, beacon_state, proposer_index, attestations * base_reward // PROPOSER_REWARD_QUOTIENT)
    assert bls_verify(
        pubkey=beacon_state.validators[proposer_index].pubkey,
        message_hash=hash_tree_root(candidate.core),
        signature=candidate.signatures.proposer_signature,
        domain=get_domain(beacon_state, DOMAIN_SHARD_PROPOSER, compute_epoch_of_shard_slot(candidate.core.slot)),
    )
    
    # Process and update block data fees
    add_fee(state, beacon_state, proposer_index, state.basefee * len(block.core.data) // SHARD_BLOCK_SIZE_LIMIT)
    QUOTIENT = SHARD_BLOCK_SIZE_LIMIT * BASEFEE_ADJUSTMENT_FACTOR
    if len(block.core.data) > SHARD_BLOCK_SIZE_TARGET:
        state.basefee += min(1, state.basefee * (len(block.core.data) - SHARD_BLOCK_SIZE_TARGET) // QUOTIENT)
    elif len(block.core.data) < SHARD_BLOCK_SIZE_TARGET:
        state.basefee -= min(1, state.basefee * (len(block.core.data) - SHARD_BLOCK_SIZE_TARGET) // QUOTIENT)
    state.basefee = max(1, min(EFFECTIVE_BALANCE_INCREMENT // EPOCHS_PER_SHARD_PERIOD // SHARD_SLOTS_PER_BEACON_SLOT * SLOTS_PER_EPOCH, state.basefee))
    
    # Check total bytes
    assert block.core.total_bytes == state.most_recent_block_core.total_bytes + len(block.core.data)
    
    # Update in-state block header
    state.most_recent_block_core = ShardBlockCore(
        slot=block.core.slot,
        beacon_chain_root=block.core.beacon_chain_root,
        parent_root=block.core.parent_root,
        data_root=block.core.data_root,
        state_root=Hash(),
        total_bytes=block.core.total_bytes,
        attester_bitfield=block.core.attester_bitfield
    )
    
    # Check state root
    assert hash_tree_root(state) == block.core.state_root
```

### Beacon attestations

Let:

- `shard` be a valid `Shard`
- `shard_blocks` be the `ShardBlock` list such that `shard_blocks[slot]` is the canonical `ShardBlock` for shard `shard` at slot `slot`
- `beacon_state` be the canonical `BeaconState`
- `valid_attestations` be the set of valid `Attestation` objects, recursively defined
- `candidate` be a candidate `Attestation` which is valid under Phase 0 rules, and for which validity is to be determined under Phase 1 rules by running `is_valid_beacon_attestation`

```python
def is_valid_beacon_attestation(shard: Shard,
                                shard_blocks: Sequence[ShardBlock],
                                beacon_state: BeaconState,
                                valid_attestations: Set[Attestation],
                                candidate: Attestation) -> bool:
    # Check if attestation is already determined valid
    for attestation in valid_attestations:
        if candidate == attestation:
            return True

    # Check previous attestation
    if candidate.data.previous_crosslink.epoch <= PHASE_1_FORK_EPOCH:
        assert candidate.data.previous_crosslink.data_root == Hash()
    else:
        previous_attestation = next(
            (attestation for attestation in valid_attestations
             if attestation.data.crosslink.data_root == candidate.data.previous_crosslink.data_root),
            None,
        )
        assert previous_attestation is not None
        assert candidate.data.previous_attestation.epoch < compute_epoch_of_slot(candidate.data.slot)

    # Check crosslink data root
    start_epoch = beacon_state.crosslinks[shard].epoch
    end_epoch = min(compute_epoch_of_slot(candidate.data.slot) - CROSSLINK_LOOKBACK,
                    start_epoch + MAX_EPOCHS_PER_CROSSLINK)
    blocks = []
    for slot in range(start_epoch * SLOTS_PER_EPOCH, end_epoch * SLOTS_PER_EPOCH):
        blocks.append(shard_blocks[slot])
    assert candidate.data.crosslink.data_root == compute_crosslink_data_root(blocks)

    return True
```

## Shard fork choice rule

The fork choice rule for any shard is LMD GHOST using the shard attestations of the persistent committee and the beacon chain attestations of the crosslink committee currently assigned to that shard, but instead of being rooted in the genesis it is rooted in the block referenced in the most recent accepted crosslink (i.e. `state.crosslinks[shard].shard_block_root`). Only blocks whose `beacon_chain_root` is the block in the main beacon chain at the specified `slot` should be considered. (If the beacon chain skips a slot, then the block at that slot is considered to be the block in the beacon chain at the highest slot lower than that slot.)
