# Ethereum 2.0 Phase 1 -- Shards Data Chains

__NOTICE__: This document is a work-in-progress for researchers and implementers.

## Table of Contents

<!-- TOC -->

- [Ethereum 2.0 Phase 1 -- Shards Data Chains](#ethereum-20-phase-1----shard-data-chains)
    - [Table of Contents](#table-of-contents)
    - [Introduction](#introduction)
    - [Constants](#constants)
        - [Time parameters](#time-parameters)
    - [Data structures](#data-structures)
        - [`ShardBlock`](#shardblock)
        - [`ShardBlockHeader`](#shardblockheader)
        - [`ShardAttestation`](#shardattestation)
    - [Helper functions](#helper-functions)
        - [`get_period_committee`](#get_period_committee)
        - [`get_persistent_committee`](#get_persistent_committee)
        - [`get_shard_proposer_index`](#get_shard_proposer_index)
    - [Crosslink data root](#crosslink-data-root)
    - [Shard fork choice rule](#shard-fork-choice-rule)
    - [Shard attestation processing](#shard-attestation-processing)

<!-- /TOC -->

## Introduction

This document represents the expected behavior of an "honest validator" with respect to Phase 1 of the Ethereum 2.0 protocol.

## Constants

### Time parameters

| Name | Value | Unit | Duration |
| - | - | :-: | :-: |
| `CROSSLINK_LOOKBACK` | 2**5 (= 32) | slots  | 3.2 minutes |

## Data structures

### `ShardBlock`

```python
{
    'slot': 'uint64',
    'shard': 'uint64',
    'previous_block_root': 'bytes32',
    'beacon_chain_root': 'bytes32',
    'data': ['byte', BYTES_PER_SHARD_BLOCK],
    'state_root': 'bytes32',
    'signature': 'bytes96',
}
```

### `ShardBlockHeader`

```python
{
    'slot': 'uint64',
    'shard': 'uint64',
    'previous_block_root': 'bytes32',
    'beacon_chain_root': 'bytes32',
    'data_root': 'bytes32',
    'state_root': 'bytes32',
    'signature': 'bytes96',
}
```

### `ShardAttestation`

```python
{
    'header': ShardBlockHeader,
    'participation_bitfield': 'bytes',
    'aggregate_signature': 'bytes96',
}
```

## Helper functions

### `get_period_committee`

```python
def get_period_committee(state: BeaconState,
                         shard: Shard,
                         committee_start_epoch: Epoch,
                         index: int,
                         committee_count: int) -> List[ValidatorIndex]:
    """
    Return committee for a period. Used to construct persistent committees.
    """
    active_validator_indices = get_active_validator_indices(state.validator_registry, committee_start_epoch)
    seed = generate_seed(state, committee_start_epoch)
    return compute_committee(active_validator_indices, seed, shard * committee_count + index, SHARD_COUNT * committee_count)
```

### `get_persistent_committee`

```python
def get_persistent_committee(state: BeaconState,
                             shard: Shard,
                             slot: Slot) -> List[ValidatorIndex]:
    """
    Return the persistent committee for the given ``shard`` at the given ``slot``.
    """
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

    def get_switchover_epoch(index):
        return bytes_to_int(hash(earlier_seed + bytes3(index))[0:8]) % PERSISTENT_COMMITTEE_PERIOD

    # Take not-yet-cycled-out validators from earlier committee and already-cycled-in validators from
    # later committee; return a sorted list of the union of the two, deduplicated
    return sorted(list(set(
        [i for i in earlier_committee if epoch % PERSISTENT_COMMITTEE_PERIOD < get_switchover_epoch(i)] +
        [i for i in later_committee if epoch % PERSISTENT_COMMITTEE_PERIOD >= get_switchover_epoch(i)]
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

    # Try to find an active proposer
    for index in persistent_committee:
        if is_active_validator(state.validator_registry[index], get_current_epoch(state)):
            return index

    # No block can be proposed if no validator is active
    return None
```

## Crosslink data root

A node should only sign an `attestation` if `attestation.crosslink_data_root` has been reccursively verified for availability using `attestation.previous_crosslink.crosslink_data_root` up to genesis where `crosslink_data_root == ZERO_HASH`.

Let `store` be the store of observed block headers and bodies and let `get_shard_block_header(store, slot)` and `get_shard_block_body(store, slot)` return the canonical shard block header and body at the specified `slot`. The expected `get_shard_block_body` is then computed as:

```python
def compute_crosslink_data_root(state: BeaconState, store: Store) -> Bytes32:
    start_slot = state.latest_crosslinks[shard].epoch * SLOTS_PER_EPOCH + SLOTS_PER_EPOCH - CROSSLINK_LOOKBACK
    end_slot = attestation.data.slot - attestation.data.slot % SLOTS_PER_EPOCH - CROSSLINK_LOOKBACK

    headers = []
    bodies = []
    for slot in range(start_slot, end_slot):
        headers = get_shard_block_header(store, slot)
        bodies = get_shard_block_body(store, slot)

    return hash(
        merkle_root(pad_to_power_of_2([
            merkle_root_of_bytes(zpad(serialize(header), BYTES_PER_SHARD_BLOCK)) for header in headers
        ])) +
        merkle_root(pad_to_power_of_2([
                merkle_root_of_bytes(body) for body in bodies
        ]))
    )
```

using the following helpers:

```python
def is_power_of_two(value: int) -> bool:
    return (value > 0) and (value & (value - 1) == 0)

def pad_to_power_of_2(values: List[bytes]) -> List[bytes]:
    while not is_power_of_two(len(values)):
        values += [b'\x00' * BYTES_PER_SHARD_BLOCK]
    return values

def merkle_root_of_bytes(data: bytes) -> bytes:
    return merkle_root([data[i:i + 32] for i in range(0, len(data), 32)])
```

## Shard fork choice rule

For a `ShardBlockHeader` object `header` to be processed by a node the following conditions must be met:

* The `header.previous_block_root` is the root of `ShardBlock` that has been processed and accepted.
* The `header.beacon_chain_root` is the root of a `BeaconBlock` in the canonical beacon chain with slot less than or equal to `header.slot`.
* The `header.beacon_chain_root` is equal to or a descendant of the `beacon_chain_root` specified in the `ShardBlock` pointed to by `header.previous_block_root`.
* The `ShardBlock` object `shard_block` with the same root as `header` has been downloaded.

The fork choice rule for any shard is LMD GHOST using the shard chain attestations of the persistent committee and the beacon chain attestations of the crosslink committee currently assigned to that shard, but instead of being rooted in the genesis it is rooted in the block referenced in the most recent accepted crosslink (i.e. `state.crosslinks[shard].shard_block_root`). Only blocks whose `beacon_chain_root` is the block in the main beacon chain at the specified `slot` should be considered. (If the beacon chain skips a slot, then the block at that slot is considered to be the block in the beacon chain at the highest slot lower than a slot.)

## Shard attestation processing

Given a `shard_attestation` let `state` be the `BeaconState` referred to by `shard_attestation.header.beacon_chain_root` and run `verify_shard_attestation(state, shard_attestation)`.

```python
def verify_shard_attestation(state: BeaconState, shard_attestation: ShardAttestation) -> None:
    header = shard_attestation.header

    # Check proposer signature
    proposer_index = get_shard_proposer_index(state, header.shard, header.slot)
    assert proposer_index is not None
    assert bls_verify(
        pubkey=validators[proposer_index].pubkey,
        message_hash=signed_root(header),
        signature=header.signature,
        domain=get_domain(state, slot_to_epoch(header.slot), DOMAIN_SHARD_PROPOSER)
    )

    # Check attestations
    persistent_committee = get_persistent_committee(state, header.shard, header.slot)
    assert verify_bitfield(shard_attestation.participation_bitfield, len(persistent_committee))
    pubkeys = []
    for i, index in enumerate(persistent_committee):
        if get_bitfield_bit(shard_attestation.participation_bitfield, i) == 0b1
            validator = state.validator_registry[index]
            assert is_active_validator(validator, get_current_epoch(state))
            pubkeys.append(validator.pubkey)
    assert bls_verify(
        pubkey=bls_aggregate_pubkeys(pubkeys),
        message_hash=header.previous_block_root,
        signature=shard_attestation.aggregate_signature,
        domain=get_domain(state, slot_to_epoch(header.slot), DOMAIN_SHARD_ATTESTER)
    )
```
