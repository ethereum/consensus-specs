# Minimal Light Client Design

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->


- [Introduction](#introduction)
- [Custom types](#custom-types)
- [Constants](#constants)
- [Containers](#containers)
  - [`LightClientUpdate`](#lightclientupdate)
- [Helpers](#helpers)
  - [`LightClientMemory`](#lightclientmemory)
- [Light client state updates](#light-client-state-updates)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

Ethereum 2.0 is designed to be light client friendly. This allows low-resource clients such as mobile phones to access Ethereum 2.0 with reasonable safety and liveness. It also facilitates the development of "bridges" to external blockchains. This document suggests a minimal light client design for the beacon chain that uses the concept of "sync committees" introduced in [./beacon-chain.md](the the light-client-friendliness beacon chain extension).

## Custom types

We define the following Python custom types for type hinting and readability:

| Name | SSZ equivalent | Description |
| - | - | - |

## Constants

| Name | Value |
| - | - |
| `SYNC_COMMITTEES_GENERALIZED_INDEX` | `GeneralizedIndexConcat(GeneralizedIndex(BeaconBlock, 'state_root'), GeneralizedIndex(BeaconState, 'current_sync_committee'))` |
| `FORK_GENERALIZED_INDEX` | `GeneralizedIndexConcat(GeneralizedIndex(BeaconBlock, 'state_root'), GeneralizedIndex(BeaconState, 'fork'))` |
| `BEACON_CHAIN_ROOT_IN_SHARD_BLOCK_HEADER_DEPTH` | `4` |
| `BEACON_CHAIN_ROOT_IN_SHARD_BLOCK_HEADER_INDEX` | **TBD** |
| `PERIOD_COMMITTEE_ROOT_IN_BEACON_STATE_DEPTH` | `5` |
| `PERIOD_COMMITTEE_ROOT_IN_BEACON_STATE_INDEX` | **TBD** |

## Containers

### `LightClientUpdate`

```python
class LightClientUpdate(Container):
    # Updated beacon header (and authenticating branch)
    header: BeaconBlockHeader
    # Sync committee signature to that header
    aggregation_bits: Bitlist[MAX_SYNC_COMMITTEE_SIZE]
    signature: BLSSignature
    header_branch: Vector[Bytes32, BEACON_CHAIN_ROOT_IN_SHARD_BLOCK_HEADER_DEPTH]
    # Updates fork version
    new_fork: Fork
    fork_branch: Vector[Bytes32, log_2(FORK_GENERALIZED_INDEX)]
    # Updated period committee (and authenticating branch)
    new_current_sync_committee: SyncCommittee
    new_next_sync_committee: SyncCommittee
    sync_committee_branch: Vector[Bytes32, log_2(SYNC_COMMITTEES_GENERALIZED_INDEX)]
```

## Helpers

### `LightClientMemory`

```python
class LightClientMemory(Container):
    # Beacon header which is not expected to revert
    header: BeaconBlockHeader
    # Fork version data
    fork_version: Version
    # period committees corresponding to the beacon header
    current_sync_committee: SyncCommittee
    next_sync_committee: SyncCommittee
```

## Light client state updates

The state of a light client is stored in a `memory` object of type `LightClientMemory`. To advance its state a light client requests an `update` object of type `LightClientUpdate` from the network by sending a request containing `(memory.shard, memory.header.slot, slot_range_end)`. It calls `validate_update(memory, update)` on each update that it receives in response. If `sum(update.aggregate_bits) * 3 > len(update.aggregate_bits) * 2` for any valid update, it accepts that update immediately; otherwise, it waits around for some time and then finally calls `update_memory(memory, update)` on the valid update with the highest `sum(update.aggregate_bits)`.

#### `validate_update`

```python
def validate_update(memory: LightClientMemory, update: LightClientUpdate) -> bool:
    # Verify the update does not skip a period
    current_period = compute_epoch_at_slot(memory.header.slot) // EPOCHS_PER_SYNC_COMMITTEE_PERIOD
    new_epoch = compute_epoch_of_shard_slot(update.header.slot)
    new_period = new_epoch // EPOCHS_PER_SYNC_COMMITTEE_PERIOD
    assert new_period in (current_period, current_period + 1)  
    
    # Verify that it actually updates to a newer slot
    assert update.header.slot > memory.header.slot
    
    # Convenience as independent variable for convenience
    committee = memory.current_sync_committee if new_period == current_period else memory.next_sync_committee
    assert len(update.aggregation_bits) == len(committee)
    
    # Verify signature
    active_pubkeys = [p for (bit, p) in zip(update.aggregation_bits, committee.pubkeys) if bit]
    domain = compute_domain(DOMAIN_SYNC_COMMITTEE, memory.version)
    signing_root = compute_signing_root(update.header, domain)
    assert bls.FastAggregateVerify(pubkeys, signing_root, update.signature)

    # Verify Merkle branches of new info
    assert is_valid_merkle_branch(
        leaf=hash_tree_root(update.new_fork),
        branch=update.fork_branch,
        depth=log2(FORK_GENERALIZED_INDEX),
        index=FORK_GENERALIZED_INDEX % 2**log2(FORK_GENERALIZED_INDEX),
        root=hash_tree_root(update.header),
    )
    assert is_valid_merkle_branch(
        leaf=hash_tree_root(update.current_sync_committee),
        branch=update.sync_committee_branch,
        depth=log2(SYNC_COMMITTEES_GENERALIZED_INDEX),
        index=SYNC_COMMITTEES_GENERALIZED_INDEX % 2**log2(SYNC_COMMITTEES_GENERALIZED_INDEX),
        root=hash_tree_root(update.header),
    )
    # Verify consistency of committees
    if new_period == current_period:
        assert update.new_current_sync_committee == memory.current_sync_committee
        assert update.new_next_sync_committee == memory.next_sync_committee
    else:
        assert update.new_current_sync_committee == memory.next_sync_committee

    return True
```

#### `update_memory`

```
def update_memory(memory: LightClientMemory, update: LightClientUpdate) -> None:
    memory.header = update.header
    epoch = compute_epoch_at_slot(update.header.slot)
    memory.fork_version = update.new_fork.previous_version if epoch < update.new_fork.epoch else update.new_fork.current_version
    memory.current_sync_committee = update.new_current_sync_committee
    memory.next_sync_committee == update.new_next_sync_committee
```
