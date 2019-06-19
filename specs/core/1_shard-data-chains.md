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
        - [Signature domains](#signature-domains)
    - [Data structures](#data-structures)
        - [`ShardBlockBody`](#shardblockbody)
        - [`ShardAttestation`](#shardattestation)
        - [`ShardBlock`](#shardblock)
        - [`ShardBlockHeader`](#shardblockheader)
    - [Helper functions](#helper-functions)
        - [`get_period_committee`](#get_period_committee)
        - [`get_switchover_epoch`](#get_switchover_epoch)
        - [`get_persistent_committee`](#get_persistent_committee)
        - [`get_shard_proposer_index`](#get_shard_proposer_index)
        - [`get_shard_header`](#get_shard_header)
        - [`verify_shard_attestation_signature`](#verify_shard_attestation_signature)
        - [`compute_crosslink_data_root`](#compute_crosslink_data_root)
    - [Object validity](#object-validity)
        - [Shard blocks](#shard-blocks)
        - [Shard attestations](#shard-attestations)
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
| `SECONDS_PER_SLOT` | `2**1 * 3**1` (= 6) | 6 seconds |

### Signature domains

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

### `ShardAttestation`

```python
class ShardAttestation(Container):
    class data(Container):
        slot: Slot
        shard: Shard
        shard_block_root: Bytes32
    aggregation_bitfield: Bytes[PLACEHOLDER]
    aggregate_signature: BLSSignature
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
    attestations: List[ShardAttestation, PLACEHOLDER]
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
    attestations: List[ShardAttestation, PLACEHOLDER]
    signature: BLSSignature
```

## Helper functions

### `get_period_committee`

```python
def get_period_committee(state: BeaconState,
                         epoch: Epoch,
                         shard: Shard,
                         index: int,
                         count: int) -> Tuple[ValidatorIndex, ...]:
    """
    Return committee for a period. Used to construct persistent committees.
    """
    return compute_committee(
        indices=get_active_validator_indices(state, epoch),
        seed=generate_seed(state, epoch),
        index=shard * count + index,
        count=SHARD_COUNT * count,
    )
```

### `get_switchover_epoch`

```python
def get_switchover_epoch(state: BeaconState, epoch: Epoch, index: ValidatorIndex) -> int:
    earlier_start_epoch = Epoch(epoch - (epoch % PERSISTENT_COMMITTEE_PERIOD) - PERSISTENT_COMMITTEE_PERIOD * 2)
    return (bytes_to_int(hash(generate_seed(state, earlier_start_epoch) + int_to_bytes(index, length=3)[0:8]))
            % PERSISTENT_COMMITTEE_PERIOD)
```

### `get_persistent_committee`

```python
def get_persistent_committee(state: BeaconState,
                             shard: Shard,
                             slot: Slot) -> Tuple[ValidatorIndex, ...]:
    """
    Return the persistent committee for the given ``shard`` at the given ``slot``.
    """
    epoch = slot_to_epoch(slot)
    earlier_start_epoch = Epoch(epoch - (epoch % PERSISTENT_COMMITTEE_PERIOD) - PERSISTENT_COMMITTEE_PERIOD * 2)
    later_start_epoch = Epoch(epoch - (epoch % PERSISTENT_COMMITTEE_PERIOD) - PERSISTENT_COMMITTEE_PERIOD)

    committee_count = max(
        len(get_active_validator_indices(state, earlier_start_epoch)) //
        (SHARD_COUNT * TARGET_COMMITTEE_SIZE),
        len(get_active_validator_indices(state, later_start_epoch)) //
        (SHARD_COUNT * TARGET_COMMITTEE_SIZE),
    ) + 1

    index = slot % committee_count
    earlier_committee = get_period_committee(state, earlier_start_epoch, shard, index, committee_count)
    later_committee = get_period_committee(state, later_start_epoch, shard, index, committee_count)

    # Take not-yet-cycled-out validators from earlier committee and already-cycled-in validators from
    # later committee; return a sorted list of the union of the two, deduplicated
    return tuple(sorted(list(set(
        [i for i in earlier_committee if epoch % PERSISTENT_COMMITTEE_PERIOD < get_switchover_epoch(state, epoch, i)] +
        [i for i in later_committee if epoch % PERSISTENT_COMMITTEE_PERIOD >= get_switchover_epoch(state, epoch, i)]
    ))))
```

### `get_shard_proposer_index`

```python
def get_shard_proposer_index(state: BeaconState,
                             shard: Shard,
                             slot: Slot) -> Optional[ValidatorIndex]:
    # Randomly shift persistent committee
    persistent_committee = get_persistent_committee(state, shard, slot)
    seed = hash(state.current_shuffling_seed + int_to_bytes(shard, length=8) + int_to_bytes(slot, length=8))
    random_index = bytes_to_int(seed[0:8]) % len(persistent_committee)
    persistent_committee = persistent_committee[random_index:] + persistent_committee[:random_index]

    # Search for an active proposer
    for index in persistent_committee:
        if is_active_validator(state.validators[index], get_current_epoch(state)):
            return index

    # No block can be proposed if no validator is active
    return None
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
        attestations=block.attestations,
        signature=block.signature,
    )
```

### `verify_shard_attestation_signature`

```python
def verify_shard_attestation_signature(state: BeaconState,
                                       attestation: ShardAttestation) -> None:
    data = attestation.data
    persistent_committee = get_persistent_committee(state, data.shard, data.slot)
    assert verify_bitfield(attestation.aggregation_bitfield, len(persistent_committee))
    pubkeys = []
    for i, index in enumerate(persistent_committee):
        if get_bitfield_bit(attestation.aggregation_bitfield, i) == 0b1:
            validator = state.validators[index]
            assert is_active_validator(validator, get_current_epoch(state))
            pubkeys.append(validator.pubkey)
    assert bls_verify(
        pubkey=bls_aggregate_pubkeys(pubkeys),
        message_hash=data.shard_block_root,
        signature=attestation.aggregate_signature,
        domain=get_domain(state, DOMAIN_SHARD_ATTESTER, slot_to_epoch(data.slot))
    )
```

### `compute_crosslink_data_root`

```python
def compute_crosslink_data_root(blocks: Iterable[ShardBlock]) -> Bytes32:
    def is_power_of_two(value: int) -> bool:
        return (value > 0) and (value & (value - 1) == 0)

    def pad_to_power_of_2(values: TypingList[bytes]) -> TypingList[bytes]:
        while not is_power_of_two(len(values)):
            values += [b'\x00' * BYTES_PER_SHARD_BLOCK_BODY]
        return values

    def hash_tree_root_of_bytes(data: bytes) -> bytes:
        return hash_tree_root([data[i:i + 32] for i in range(0, len(data), 32)])

    def zpad(data: bytes, length: int) -> bytes:
        return data + b'\x00' * (length - len(data))

    return hash(
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

* `beacon_blocks` be the `BeaconBlock` list such that `beacon_blocks[slot]` is the canonical `BeaconBlock` at slot `slot`
* `beacon_state` be the canonical `BeaconState` after processing `beacon_blocks[-1]`
* `valid_shard_blocks` be the list of valid `ShardBlock`, recursively defined
* `candidate` be a candidate `ShardBlock` for which validity is to be determined by running `is_valid_shard_block`

```python
def is_valid_shard_block(beacon_blocks: TypingList[BeaconBlock],
                         beacon_state: BeaconState,
                         valid_shard_blocks: Iterable[ShardBlock],
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
    assert candidate.state_root == ZERO_HASH  # [to be removed in phase 2]

    # Check parent block
    if candidate.slot == PHASE_1_FORK_SLOT:
        assert candidate.parent_root == ZERO_HASH
    else:
        parent_block = next(
            (block for block in valid_shard_blocks if signing_root(block) == candidate.parent_root),
            None
        )
        assert parent_block is not None
        assert parent_block.shard == candidate.shard
        assert parent_block.slot < candidate.slot
        assert signing_root(beacon_blocks[parent_block.slot]) == parent_block.beacon_chain_root

    # Check attestations
    assert len(candidate.attestations) <= MAX_SHARD_ATTESTIONS
    for _, attestation in enumerate(candidate.attestations):
        assert max(GENESIS_SHARD_SLOT, candidate.slot - SLOTS_PER_EPOCH) <= attestation.data.slot
        assert attestation.data.slot <= candidate.slot - MIN_ATTESTATION_INCLUSION_DELAY
        assert attestation.data.crosslink.shard == candidate.shard
        verify_shard_attestation_signature(beacon_state, attestation)

    # Check signature
    proposer_index = get_shard_proposer_index(beacon_state, candidate.shard, candidate.slot)
    assert proposer_index is not None
    assert bls_verify(
        pubkey=beacon_state.validators[proposer_index].pubkey,
        message_hash=signing_root(block),
        signature=candidate.signature,
        domain=get_domain(beacon_state, DOMAIN_SHARD_PROPOSER, slot_to_epoch(candidate.slot)),
    )

    return True
```

### Shard attestations

Let:

* `valid_shard_blocks` be the list of valid `ShardBlock`
* `beacon_state` be the canonical `BeaconState`
* `candidate` be a candidate `ShardAttestation` for which validity is to be determined by running `is_valid_shard_attestation`

```python
def is_valid_shard_attestation(valid_shard_blocks: Iterable[ShardBlock],
                               beacon_state: BeaconState,
                               candidate: ShardAttestation) -> bool:
    # Check shard block
    shard_block = next(
        (block for block in valid_shard_blocks if signing_root(block) == candidate.data.shard_block_root),
        None,
    )
    assert shard_block is not None
    assert shard_block.slot == candidate.data.slot
    assert shard_block.shard == candidate.data.shard

    # Check signature
    verify_shard_attestation_signature(beacon_state, candidate)

    return True
```

### Beacon attestations

Let:

* `shard` be a valid `Shard`
* `shard_blocks` be the `ShardBlock` list such that `shard_blocks[slot]` is the canonical `ShardBlock` for shard `shard` at slot `slot`
* `beacon_state` be the canonical `BeaconState`
* `valid_attestations` be the list of valid `Attestation`, recursively defined
* `candidate` be a candidate `Attestation` which is valid under Phase 0 rules, and for which validity is to be determined under Phase 1 rules by running `is_valid_beacon_attestation`

```python
def is_valid_beacon_attestation(shard: Shard,
                                shard_blocks: TypingList[ShardBlock],
                                beacon_state: BeaconState,
                                valid_attestations: Set[Attestation],
                                candidate: Attestation) -> bool:
    # Check if attestation is already determined valid
    for _, attestation in enumerate(valid_attestations):
        if candidate == attestation:
            return True

    # Check previous attestation
    if candidate.data.previous_crosslink.epoch <= PHASE_1_FORK_EPOCH:
        assert candidate.data.previous_crosslink.data_root == ZERO_HASH
    else:
        previous_attestation = next(
            (attestation for attestation in valid_attestations if
                attestation.data.crosslink.data_root == candidate.data.previous_crosslink.data_root),
            None,
        )
        assert previous_attestation is not None
        assert candidate.data.previous_attestation.epoch < slot_to_epoch(candidate.data.slot)

    # Check crosslink data root
    start_epoch = beacon_state.crosslinks[shard].epoch
    end_epoch = min(slot_to_epoch(candidate.data.slot) - CROSSLINK_LOOKBACK, start_epoch + MAX_EPOCHS_PER_CROSSLINK)
    blocks = []
    for slot in range(start_epoch * SLOTS_PER_EPOCH, end_epoch * SLOTS_PER_EPOCH):
        blocks.append(shard_blocks[slot])
    assert candidate.data.crosslink.data_root == compute_crosslink_data_root(blocks)

    return True
```

## Shard fork choice rule

The fork choice rule for any shard is LMD GHOST using the shard attestations of the persistent committee and the beacon chain attestations of the crosslink committee currently assigned to that shard, but instead of being rooted in the genesis it is rooted in the block referenced in the most recent accepted crosslink (i.e. `state.crosslinks[shard].shard_block_root`). Only blocks whose `beacon_chain_root` is the block in the main beacon chain at the specified `slot` should be considered. (If the beacon chain skips a slot, then the block at that slot is considered to be the block in the beacon chain at the highest slot lower than that slot.)
