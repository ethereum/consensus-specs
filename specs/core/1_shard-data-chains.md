# Ethereum 2.0 Phase 1 -- Shard Data Chains

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- TOC -->

- [Ethereum 2.0 Phase 1 -- Shard Data Chains](#ethereum-20-phase-1----shard-data-chains)
    - [Table of contents](#table-of-contents)
    - [Introduction](#introduction)
    - [Constants](#constants)
        - [Misc](#misc)
        - [Time parameters](#time-parameters)
        - [Signature domains](#signature-domains)
    - [Data structures](#data-structures)
        - [`ShardBlockBody`](#shardblockbody)
        - [`ShardBlock`](#shardblock)
        - [`ShardBlockHeader`](#shardblockheader)
        - [`ShardAttestation`](#shardattestation)
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

## Constants

### Misc

| Name | Value |
| - | - |
| `BYTES_PER_SHARD_BLOCK_BODY` | `2**14` (= 16,384) |
| `MAX_SHARD_ATTESTIONS` | `2**4` (= 16) |
| `PHASE_1_GENESIS_EPOCH` | **TBD** |
| `PHASE_1_GENESIS_SLOT` | get_epoch_start_slot(PHASE_1_GENESIS_EPOCH) |

### Time parameters

| Name | Value | Unit | Duration |
| - | - | :-: | :-: |
| `CROSSLINK_LOOKBACK` | `2**0` (= 1) | epochs  | 6.2 minutes |
| `PERSISTENT_COMMITTEE_PERIOD` | `2**11` (= 2,048) | epochs | ~9 days |

### Signature domains

| Name | Value |
| - | - |
| `DOMAIN_SHARD_PROPOSER` | `128` |
| `DOMAIN_SHARD_ATTESTER` | `129` |

## Data structures

### `ShardBlockBody`

```python
['byte', BYTES_PER_SHARD_BLOCK_BODY]
```

### `ShardBlock`

```python
{
    'slot': Slot,
    'shard': Shard,
    'beacon_chain_root': Hash,
    'previous_block_root': Hash,
    'data': ShardBlockBody,
    'state_root': Hash,
    'attestations': [ShardAttestation],
    'signature': BLSSignature,
}
```

### `ShardBlockHeader`

```python
{
    'slot': Slot,
    'shard': Shard,
    'beacon_chain_root': Hash,
    'previous_block_root': Hash,
    'body_root': Hash,
    'state_root': Hash,
    'attestations': [ShardAttestation],
    'signature': BLSSignature,
}
```

### `ShardAttestation`

```python
{
    'data': {
        'slot': Slot,
        'shard': Shard,
        'shard_block_root': Hash,
    },
    'aggregation_bitfield': Bitfield,
    'aggregate_signature': BLSSignature,
}
```

## Helper functions

### `get_period_committee`

```python
def get_period_committee(state: BeaconState, epoch: Epoch, shard: Shard, index: int, count: int) -> List[ValidatorIndex]:
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
def get_switchover_epoch(state: BeaconState, epoch: Epoch, index: ValidatorIndex):
    earlier_start_epoch = epoch - (epoch % PERSISTENT_COMMITTEE_PERIOD) - PERSISTENT_COMMITTEE_PERIOD * 2
    return bytes_to_int(hash(generate_seed(state, earlier_start_epoch) + bytes3(index))[0:8]) % PERSISTENT_COMMITTEE_PERIOD
```

### `get_persistent_committee`

```python
def get_persistent_committee(state: BeaconState,
                             shard: Shard,
                             slot: Slot) -> List[ValidatorIndex]:
    """
    Return the persistent committee for the given ``shard`` at the given ``slot``.
    """
    epoch = slot_to_epoch(slot)
    earlier_start_epoch = epoch - (epoch % PERSISTENT_COMMITTEE_PERIOD) - PERSISTENT_COMMITTEE_PERIOD * 2
    later_start_epoch = epoch - (epoch % PERSISTENT_COMMITTEE_PERIOD) - PERSISTENT_COMMITTEE_PERIOD

    committee_count = max(
        len(get_active_validator_indices(state.validator_registry, earlier_start_epoch)) //
        (SHARD_COUNT * TARGET_COMMITTEE_SIZE),
        len(get_active_validator_indices(state.validator_registry, later_start_epoch)) //
        (SHARD_COUNT * TARGET_COMMITTEE_SIZE),
    ) + 1

    index = slot % committee_count
    earlier_committee = get_period_committee(state, shard, earlier_start_epoch, index, committee_count)
    later_committee = get_period_committee(state, shard, later_start_epoch, index, committee_count)

    # Take not-yet-cycled-out validators from earlier committee and already-cycled-in validators from
    # later committee; return a sorted list of the union of the two, deduplicated
    return sorted(list(set(
        [i for i in earlier_committee if epoch % PERSISTENT_COMMITTEE_PERIOD < get_switchover_epoch(state, epoch, i)] +
        [i for i in later_committee if epoch % PERSISTENT_COMMITTEE_PERIOD >= get_switchover_epoch(state, epoch, i)]
    )))
```

### `get_shard_proposer_index`

```python
def get_shard_proposer_index(state: BeaconState,
                             shard: Shard,
                             slot: Slot) -> ValidatorIndex:
    # Randomly shift persistent committee
    persistent_committee = get_persistent_committee(state, shard, slot)
    seed = hash(state.current_shuffling_seed + int_to_bytes8(shard) + int_to_bytes8(slot))
    random_index = bytes_to_int(seed[0:8]) % len(persistent_committee)
    persistent_committee = persistent_committee[random_index:] + persistent_committee[:random_index]

    # Search for an active proposer
    for index in persistent_committee:
        if is_active_validator(state.validator_registry[index], get_current_epoch(state)):
            return index

    # No block can be proposed if no validator is active
    return None
```

### `get_shard_header`

```python
def get_shard_header(block: ShardBlock) -> ShardBlockHeader:
    return ShardBlockHeader(
        slot: block.slot,
        shard: block.shard,
        beacon_chain_root: block.beacon_chain_root,
        previous_block_root: block.previous_block_root,
        body_root: hash_tree_root(block.body),
        state_root: block.state_root,
        attestations: block.attestations,
        signature: block.signature,
    )
```

### `verify_shard_attestation_signature`

```python
def verify_shard_attestation_signature(state: BeaconState,
                                       attestation: ShardAttestation) -> None:
    data = attestation.data
    persistent_committee = get_persistent_committee(state, data.crosslink.shard, data.slot)
    assert verify_bitfield(attestation.aggregation_bitfield, len(persistent_committee))
    pubkeys = []
    for i, index in enumerate(persistent_committee):
        if get_bitfield_bit(attestation.aggregation_bitfield, i) == 0b1
            validator = state.validator_registry[index]
            assert is_active_validator(validator, get_current_epoch(state))
            pubkeys.append(validator.pubkey)
    assert bls_verify(
        pubkey=bls_aggregate_pubkeys(pubkeys),
        message_hash=data.crosslink.shard_block_root,
        signature=attestation.aggregate_signature,
        domain=get_domain(state, slot_to_epoch(data.slot), DOMAIN_SHARD_ATTESTER)
    )
```

### `compute_crosslink_data_root`

```python
def compute_crosslink_data_root(blocks: List[ShardBlock]) -> Hash:
    def is_power_of_two(value: int) -> bool:
        return (value > 0) and (value & (value - 1) == 0)

    def pad_to_power_of_2(values: List[bytes]) -> List[bytes]:
        while not is_power_of_two(len(values)):
            values += [b'\x00' * BYTES_PER_SHARD_BLOCK_BODY]
        return values

    def merkle_root_of_bytes(data: bytes) -> bytes:
        return merkle_root([data[i:i + 32] for i in range(0, len(data), 32)])

    return hash(
        merkle_root(pad_to_power_of_2([
            merkle_root_of_bytes(zpad(serialize(get_shard_header(block)), BYTES_PER_SHARD_BLOCK_BODY)) for block in blocks
        ])) +
        merkle_root(pad_to_power_of_2([
                merkle_root_of_bytes(block.body) for block in blocks
        ]))
    )
```

## Object validity

### Shard blocks

Let:

* `beacon_blocks` be the `BeaconBlock` list such that `beacon_blocks[slot]` is the canonical `BeaconBlock` at slot `slot`
* `beacon_state` be the canonical `BeaconState` after processing `beacon_blocks[-1]`
* `valid_shard_blocks` be the list of valid `ShardBlock`, recursively defined
* `unix_time` be the current unix time
* `candidate` be a candidate `ShardBlock` for which validity is to be determined by running `is_valid_shard_block`

```python
def is_valid_shard_block(beacon_blocks: List[BeaconBlock],
                         beacon_state: BeaconState,
                         valid_shard_blocks: List[ShardBlock],
                         unix_time: uint64,
                         candidate: ShardBlock) -> bool
    # Check if block is already determined valid
    for _, block in enumerate(valid_shard_blocks):
        if candidate == block:
            return True

    # Check slot number
    assert block.slot >= PHASE_1_GENESIS_SLOT
    assert unix_time >= beacon_state.genesis_time + (block.slot - GENESIS_SLOT) * SECONDS_PER_SLOT

    # Check shard number
    assert block.shard <= SHARD_COUNT

    # Check beacon block
    beacon_block = beacon_blocks[block.slot]
    assert block.beacon_block_root == signing_root(beacon_block)
    assert beacon_block.slot <= block.slot:

    # Check state root
    assert block.state_root == ZERO_HASH  # [to be removed in phase 2]

    # Check parent block
    if block.slot == PHASE_1_GENESIS_SLOT:
        assert candidate.previous_block_root == ZERO_HASH
    else:
        parent_block = next(
            block for block in valid_shard_blocks if
            signing_root(block) == candidate.previous_block_root
        , None)
        assert parent_block != None
        assert parent_block.shard == block.shard
        assert parent_block.slot < block.slot
        assert signing_root(beacon_blocks[parent_block.slot]) == parent_block.beacon_chain_root

    # Check attestations
    assert len(block.attestations) <= MAX_SHARD_ATTESTIONS
    for _, attestation in enumerate(block.attestations):
        assert max(GENESIS_SHARD_SLOT, block.slot - SLOTS_PER_EPOCH) <= attestation.data.slot
        assert attestation.data.slot <= block.slot - MIN_ATTESTATION_INCLUSION_DELAY
        assert attestation.data.crosslink.shard == block.shard
        verify_shard_attestation_signature(beacon_state, attestation)

    # Check signature
    proposer_index = get_shard_proposer_index(beacon_state, block.shard, block.slot)
    assert proposer_index is not None
    assert bls_verify(
        pubkey=validators[proposer_index].pubkey,
        message_hash=signing_root(block),
        signature=block.signature,
        domain=get_domain(beacon_state, slot_to_epoch(block.slot), DOMAIN_SHARD_PROPOSER)
    )

    return True
```

### Shard attestations

Let:

* `valid_shard_blocks` be the list of valid `ShardBlock`
* `beacon_state` be the canonical `BeaconState`
* `candidate` be a candidate `ShardAttestation` for which validity is to be determined by running `is_valid_shard_attestation`

```python
def is_valid_shard_attestation(valid_shard_blocks: List[ShardBlock],
                               beacon_state: BeaconState,
                               candidate: Attestation) -> bool:
    # Check shard block
    shard_block = next(
        block for block in valid_shard_blocks if
        signing_root(block) == candidate.attestation.data.crosslink.shard_block_root
    , None)
    assert shard_block != None
    assert shard_block.slot == attestation.data.slot
    assert shard_block.shard == attestation.data.crosslink.shard

    # Check signature
    verify_shard_attestation_signature(beacon_state, attestation)

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
                                shard_blocks: List[ShardBlock],
                                beacon_state: BeaconState,
                                valid_attestations: List[Attestation],
                                candidate: Attestation) -> bool:
    # Check if attestation is already determined valid
    for _, attestation in enumerate(valid_attestations):
        if candidate == attestation:
            return True

    # Check previous attestation
    if candidate.data.previous_crosslink.epoch <= PHASE_1_GENESIS_EPOCH:
        assert candidate.data.previous_crosslink.crosslink_data_root == ZERO_HASH
    else:
        previous_attestation = next(
            attestation for attestation in valid_attestations if
            attestation.data.crosslink.crosslink_data_root == candidate.data.previous_crosslink.crosslink_data_root
        , None)
        assert previous_attestation != None
        assert candidate.data.previous_attestation.epoch < slot_to_epoch(candidate.data.slot)

    # Check crosslink data root
    start_epoch = state.latest_crosslinks[shard].epoch
    end_epoch = min(slot_to_epoch(candidate.data.slot) - CROSSLINK_LOOKBACK, start_epoch + MAX_EPOCHS_PER_CROSSLINK)
    blocks = []
    for slot in range(start_epoch * SLOTS_PER_EPOCH, end_epoch * SLOTS_PER_EPOCH):
        blocks.append(shard_blocks[slot])
    assert candidate.data.crosslink.crosslink_data_root == compute_crosslink_data_root(blocks)

    return True
```

## Shard fork choice rule

The fork choice rule for any shard is LMD GHOST using the shard attestations of the persistent committee and the beacon chain attestations of the crosslink committee currently assigned to that shard, but instead of being rooted in the genesis it is rooted in the block referenced in the most recent accepted crosslink (i.e. `state.crosslinks[shard].shard_block_root`). Only blocks whose `beacon_chain_root` is the block in the main beacon chain at the specified `slot` should be considered. (If the beacon chain skips a slot, then the block at that slot is considered to be the block in the beacon chain at the highest slot lower than that slot.)
