# Minimal Light Client

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->


- [Introduction](#introduction)
- [Constants](#constants)
- [Configuration](#configuration)
  - [Misc](#misc)
  - [Time parameters](#time-parameters)
- [Containers](#containers)
    - [`LightClientSnapshot`](#lightclientsnapshot)
    - [`LightClientUpdate`](#lightclientupdate)
    - [`LightClientStore`](#lightclientstore)
- [Light client state updates](#light-client-state-updates)
    - [`is_valid_light_client_update`](#is_valid_light_client_update)
    - [`process_light_client_update`](#process_light_client_update)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

Eth2 is designed to be light client friendly for constrained environments to access Eth2 with reasonable satefy and liveness. Such environments include resource-constrained devices (e.g. phones for trust-minimised wallets) and metered VMs (e.g. blockchain VMs for cross-chain bridges).

This document suggests a minimal light client design for the beacon chain that uses sync committees introduced in [this beacon chain extension](./beacon-chain.md).

## Constants

| Name | Value |
| - | - |
| `NEXT_SYNC_COMMITTEE_INDEX` | `IndexConcat(Index(BeaconBlock, 'state_root'), Index(BeaconState, 'next_sync_committee'))` |

## Configuration

### Misc

| Name | Value |
| - | - |
| `MAX_VALID_LIGHT_CLIENT_UPDATES` | `uint64(2**64 - 1)` |

### Time parameters

| Name | Value | Unit | Duration |
| - | - | :-: | :-: |
| `LIGHT_CLIENT_UPDATE_TIMEOUT` | `Slot(2**13)` | slots | ~27 hours |

## Containers

#### `LightClientSnapshot`

```python
class LightClientSnapshot(Container):
    # Beacon block header
    header: BeaconBlockHeader
    # Sync committees corresponding to the header
    current_sync_committee: SyncCommittee
    next_sync_committee: SyncCommittee
```

#### `LightClientUpdate`

```python
class LightClientUpdate(Container):
    # Updated snapshot
    snapshot: LightClientSnapshot
    # Merkle branches for the next sync committee
    next_sync_committee_branch: Vector[Bytes32, log2(NEXT_SYNC_COMMITTEE_INDEX)]
    # Sync committee aggregate signature
    sync_committee_bits: Bitlist[MAX_SYNC_COMMITTEE_SIZE]
    sync_committee_signature: BLSSignature
    # Fork version corresponding to the aggregate signature
    fork_version
```

#### `LightClientStore`

```python
class LightClientStore(Container):
    snapshot: LightClientSnapshot
    valid_updates: List[LightClientUpdate, MAX_VALID_LIGHT_CLIENT_UPDATES]
```

## Light client state updates

A light client maintains its state in a `store` object of type `LightClientStore` and receives `update` objects of type `LightClientUpdate`. Every `update` triggers `process_light_client_update(store, update, current_slot)` where `current_slot` is the currect slot based on some local clock.

#### `is_valid_light_client_update`

```python
def is_valid_light_client_update(store: LightClientStore, update: LightClientUpdate) -> bool:
    # Verify new slot is larger than old slot
    old_snapshot = store.snapshot
    new_snapshot = update.snapshot
    assert new_snapshot.header.slot > old_snapshot.header.slot

    # Verify update does not skip a sync committee period
    old_period = compute_epoch_at_slot(old_snapshot.header.slot) // EPOCHS_PER_SYNC_COMMITTEE_PERIOD
    new_period = compute_epoch_at_slot(new_snapshot.header.slot) // EPOCHS_PER_SYNC_COMMITTEE_PERIOD
    assert new_period in (old_period, old_period + 1)

    # Verify new snapshot sync committees
    if new_period == old_period:
        assert new_snapshot.current_sync_committee == old_snapshot.current_sync_committee
        assert new_snapshot.next_sync_committee == old_snapshot.next_sync_committee
    else new_period == old_period + 1:
        assert new_snapshot.current_sync_committee == old_snapshot.next_sync_committee
        assert is_valid_merkle_branch(
            leaf=hash_tree_root(new_snapshot.next_sync_committee),
            branch=update.next_sync_committee_branch,
            depth=log2(NEXT_SYNC_COMMITTEE_INDEX),
            index=NEXT_SYNC_COMMITTEE_INDEX % 2**log2(NEXT_SYNC_COMMITTEE_INDEX),
            root=hash_tree_root(new_snapshot.header),
        )

    # Verify sync committee bitfield length 
    sync_committee = new_snapshot.current_sync_committee
    assert len(update.sync_committee_bits) == len(sync_committee)

    # Verify sync committee aggregate signature
    participant_pubkeys = [pubkey for (bit, pubkey) in zip(update.sync_committee_bits, sync_committee.pubkeys) if bit]
    domain = compute_domain(DOMAIN_SYNC_COMMITTEE, update.fork_version)
    signing_root = compute_signing_root(new_snapshot.header, domain)
    assert bls.FastAggregateVerify(participant_pubkeys, signing_root, update.sync_committee_signature)

    return True
```

#### `process_update`

```python
def process_light_client_update(store: LightClientStore, update: LightClientUpdate, current_slot: Slot) -> None:
    assert is_valid_light_client_update(store, update)
    if sum(update.sync_committee_bits) * 3 > len(update.sync_committee_bits) * 2:
        store.snapshot = update.snapshot
        valid_updates = []
    else:
        valid_updates.append(update)

    # Force an update after the update timeout has elapsed
    if current_slot > old_snapshot.header.slot + LIGHT_CLIENT_UPDATE_TIMEOUT:
        best_update = max(valid_updates, key=lambda update: sum(update.sync_committee_bits))
        store.snapshot = best_update.new_snapshot
```
