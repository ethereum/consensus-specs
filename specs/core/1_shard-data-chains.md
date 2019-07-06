# Ethereum 2.0 Phase 1 -- Shard Data Chains

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- TOC -->

- [Ethereum 2.0 Phase 1 -- Shard Data Chains](#ethereum-20-phase-1----shard-data-chains)
    - [Table of contents](#table-of-contents)
    - [Introduction](#introduction)
    - [Configuration](#configuration)
        - [Misc](#misc)
        - [Initial values](#initial-values)
        - [Time parameters](#time-parameters)
        - [Signature domain types](#signature-domain-types)
        - [TODO PLACEHOLDER](#todo-placeholder)
    - [Data structures](#data-structures)
        - [`ShardBlockBody`](#shardblockbody)
        - [`ShardBlock`](#shardblock)
        - [`ShardBlockHeader`](#shardblockheader)
    - [Helper functions](#helper-functions)
        - [`get_period_committee`](#get_period_committee)
        - [`get_switchover_epoch`](#get_switchover_epoch)
        - [`get_shard_epoch_committee`](#get_shard_epoch_committee)
        - [`get_shard_block_proposer_index`](#get_shard_block_proposer_index)
        - [`get_shard_block_attester_committee`](#get_shard_block_attester_committee)
        - [`get_shard_header`](#get_shard_header)
        - [`verify_shard_attestation_signature`](#verify_shard_attestation_signature)
        - [`compute_crosslink_data_root`](#compute_crosslink_data_root)
    - [Object validity](#object-validity)
        - [Shard blocks](#shard-blocks)
        - [Beacon attestations](#beacon-attestations)
    - [Shard fork choice rule](#shard-fork-choice-rule)

<!-- /TOC -->

## Introduction

This document describes the shard data layer and the shard fork choice rule in Phase 1 of Ethereum 2.0.

## Configuration

### Misc

| Name | Value |
| - | - |
| `BYTES_PER_SHARD_BLOCK_BODY` | `2**14` (= 16,384) |
| `MAX_SHARD_ATTESTIONS` | `2**4` (= 16) |
| `SHARD_SLOTS_PER_BEACON_SLOT` | `2**0` (= 1) |
| `SHARD_SLOT_COMMITTEE_SIZE` | `2**5` (= 32) |

### Initial values

| Name | Value |
| `PHASE_1_FORK_EPOCH` | **TBD** |
| `PHASE_1_FORK_SLOT` | **TBD** |
| `GENESIS_SHARD_SLOT` | 0 |

### Time parameters

| Name | Value | Unit | Duration |
| - | - | :-: | :-: |
| `CROSSLINK_LOOKBACK` | `2**0` (= 1) | epochs  | 6.2 minutes |
| `PERSISTENT_COMMITTEE_PERIOD` | `2**11` (= 2,048) | epochs | ~9 days |

### Signature domain types

The following types are defined, mapping into `DomainType` (little endian):

| Name | Value |
| - | - |
| `DOMAIN_SHARD_PROPOSER` | `128` |
| `DOMAIN_SHARD_ATTESTER` | `129` |

### TODO PLACEHOLDER

| Name | Value |
| - | - |
| `PLACEHOLDER` | `2**32` |

## Data structures

### `ShardBlockBody`

```python
class ShardBlockBody(Container):
    data: Vector[Bytes[PLACEHOLDER], BYTES_PER_SHARD_BLOCK_BODY]
```

### `ShardBlock`

```python
class ShardBlock(Container):
    slot: Slot
    shard: Shard
    beacon_chain_root: Bytes32
    parent_root: Bytes32
    data: ShardBlockBody
    state_root: Bytes32
    attester_bitfield: Bitvector[SHARD_SLOT_COMMITTEE_SIZE]
    signature: BLSSignature
```

### `ShardBlockHeader`

```python
class ShardBlockHeader(Container):
    slot: Slot
    shard: Shard
    beacon_chain_root: Bytes32
    parent_root: Bytes32
    body_root: Bytes32
    state_root: Bytes32
    attester_bitfield: Bitvector[SHARD_SLOT_COMMITTEE_SIZE]
    signature: BLSSignature
```

## Helper functions

### `get_period_committee`

```python
def get_period_committee(state: BeaconState,
                         epoch: Epoch,
                         shard: Shard) -> Sequence[ValidatorIndex]:
    """
    Return committee for a period. Used to construct persistent committees.
    """
    return compute_committee(
        indices=get_active_validator_indices(state, epoch),
        seed=get_seed(state, epoch),
        index=shard,
        count=SHARD_COUNT,
    )
```

### `get_switchover_epoch`

```python
def get_switchover_epoch(state: BeaconState, epoch: Epoch, index: ValidatorIndex) -> int:
    earlier_start_epoch = Epoch(epoch - (epoch % PERSISTENT_COMMITTEE_PERIOD) - PERSISTENT_COMMITTEE_PERIOD * 2)
    return (bytes_to_int(hash(get_seed(state, earlier_start_epoch) + int_to_bytes(index, length=3)[0:8]))
            % PERSISTENT_COMMITTEE_PERIOD)
```

### `get_shard_epoch_committee`

```python
def get_shard_epoch_committee(state: BeaconState,
                              shard: Shard,
                              epoch: Epoch) -> Sequence[ValidatorIndex]:
    """
    Return the persistent committee for the given ``shard`` at the given ``epoch``.
    """
    earlier_start_epoch = Epoch(epoch - (epoch % PERSISTENT_COMMITTEE_PERIOD) - PERSISTENT_COMMITTEE_PERIOD * 2)
    later_start_epoch = Epoch(epoch - (epoch % PERSISTENT_COMMITTEE_PERIOD) - PERSISTENT_COMMITTEE_PERIOD)

    earlier_committee = get_period_committee(state, earlier_start_epoch, shard)
    later_committee = get_period_committee(state, later_start_epoch, shard)

    seed = get_seed(state, epoch)
    MAX_RANDOM_BYTE = 2**8 - 1

    def before_switch(i: ValidatorIndex) -> bool:
        return epoch % PERSISTENT_COMMITTEE_PERIOD < get_switchover_epoch(state, epoch, i)

    def active_and_balance_filter(i: ValidatorIndex) -> bool:
        if not is_active_validator(state.validators[i], epoch):
            return False 
        active_threshold = MAX_EFFECTIVE_BALANCE * seed[i % 32] // MAX_RANDOM_BYTE
        if state.validators[i].effective_balance < active_threshold:
            return False
        return True

    # Take not-yet-cycled-out validators from earlier committee and already-cycled-in validators from
    # later committee; return a sorted list of the union of the two, deduplicated
    combined_committee = sorted(set(
        [i for i in earlier_committee if before_switch(i) and active_and_balance_filter(i)]
        + [i for i in later_committee if (not before_switch(i)) and active_and_balance_filter(i)]
    ))

    committee_size = min(len(combined_committee), SHARD_SLOTS_PER_BEACON_SLOT * SLOTS_PER_EPOCH)
    return [
        compute_shuffled_index(combined_committee[i], len(combined_committee), seed)
        for i in range(committee_size)
    ]
```

### `get_shard_block_proposer_index`

```python
def get_shard_block_proposer_index(state: BeaconState,
                                   shard: Shard,
                                   slot: Slot) -> Optional[ValidatorIndex]:
    epoch_committee = get_shard_epoch_committee(state, shard, compute_epoch_of_slot(slot))
    if len(epoch_committee) == 0:
        return None
    else:
        return epoch_committee[slot % len(epoch_committee)]
```

### `get_shard_block_attester_committee`

```python
def get_shard_block_attester_committee(state: BeaconState,
                                       shard: Shard,
                                       slot: Slot) -> Sequence[Optional[ValidatorIndex]]:
    committee_size = min(
        len(get_shard_epoch_committee(state, shard, compute_epoch_of_slot(slot))),
        SHARD_SLOT_COMMITTEE_SIZE,
    )
    return [get_shard_block_proposer_index(state, shard, Slot(slot - i)) for i in range(committee_size)]
```

### `get_shard_header`

```python
def get_shard_header(block: ShardBlock) -> ShardBlockHeader:
    return ShardBlockHeader(
        slot=block.slot,
        shard=block.shard,
        beacon_chain_root=block.beacon_chain_root,
        parent_root=block.parent_root,
        body_root=hash_tree_root(block.body),
        state_root=block.state_root,
        attester_bitfield=block.attester_bitfield,
        signature=block.signature,
    )
```

### `verify_shard_attestation_signature`

```python
def verify_shard_attestation_signature(state: BeaconState,
                                       block: ShardBlock) -> bool:
    attester_committee = get_shard_block_attester_committee(state, block.shard, block.slot)
    attesters = [v for i, v in enumerate(attester_committee) if i is not None and block.attester_bitfield[i]]
    if get_shard_block_proposer_index(state, block.shard, block.slot) not in attesters:
        return False
    return bls_verify(
        pubkey=bls_aggregate_pubkeys([state.validators[v].pubkey for v in attesters]),
        message_hash=signing_root(block),
        signature=block.signature,
        domain=get_domain(state, DOMAIN_SHARD_ATTESTER, compute_epoch_of_slot(block.slot))
    )
```

### `compute_crosslink_data_root`

```python
def compute_crosslink_data_root(blocks: Sequence[ShardBlock]) -> Bytes32:
    def is_power_of_two(value: uint64) -> bool:
        return (value > 0) and (value & (value - 1) == 0)

    def pad_to_power_of_2(values: MutableSequence[bytes]) -> Sequence[bytes]:
        while not is_power_of_two(len(values)):
            values.append(b'\x00' * BYTES_PER_SHARD_BLOCK_BODY)
        return values

    def hash_tree_root_of_bytes(data: bytes) -> bytes:
        return hash_tree_root([data[i:i + 32] for i in range(0, len(data), 32)])

    def zpad(data: bytes, length: uint64) -> bytes:
        return data + b'\x00' * (length - len(data))

    return hash(
        # TODO untested code.
        #  Need to either pass a typed list to hash-tree-root, or merkleize_chunks(values, pad_to=2**x)
        hash_tree_root(pad_to_power_of_2([
            hash_tree_root_of_bytes(
                zpad(serialize(get_shard_header(block)), BYTES_PER_SHARD_BLOCK_BODY)
            ) for block in blocks
        ]))
        + hash_tree_root(pad_to_power_of_2([
            hash_tree_root_of_bytes(block.body) for block in blocks
        ]))
    )
```

## Object validity

### Shard blocks

Let:

- `beacon_blocks` be the `BeaconBlock` list such that `beacon_blocks[slot]` is the canonical `BeaconBlock` at slot `slot`
- `beacon_state` be the canonical `BeaconState` after processing `beacon_blocks[-1]`
- `valid_shard_blocks` be the list of valid `ShardBlock`, recursively defined
- `candidate` be a candidate `ShardBlock` for which validity is to be determined by running `is_valid_shard_block`

```python
def is_valid_shard_block(beacon_blocks: Sequence[BeaconBlock],
                         beacon_state: BeaconState,
                         valid_shard_blocks: Sequence[ShardBlock],
                         candidate: ShardBlock) -> bool:
    # Check if block is already determined valid
    for _, block in enumerate(valid_shard_blocks):
        if candidate == block:
            return True

    # Check slot number
    assert candidate.slot >= PHASE_1_FORK_SLOT

    # Check shard number
    assert candidate.shard <= SHARD_COUNT

    # Check beacon block
    beacon_block = beacon_blocks[candidate.slot]
    assert candidate.beacon_block_root == signing_root(beacon_block)
    assert beacon_block.slot <= candidate.slot

    # Check state root
    assert candidate.state_root == Hash()  # [to be removed in phase 2]

    # Check parent block
    if candidate.slot == PHASE_1_FORK_SLOT:
        assert candidate.parent_root == Hash()
    else:
        parent_block = next(
            (block for block in valid_shard_blocks if signing_root(block) == candidate.parent_root),
            None
        )
        assert parent_block is not None
        assert parent_block.shard == candidate.shard
        assert parent_block.slot < candidate.slot
        assert signing_root(beacon_blocks[parent_block.slot]) == parent_block.beacon_chain_root

    # Check signatures
    assert verify_shard_attestation_signature(beacon_state, candidate)

    return True
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
