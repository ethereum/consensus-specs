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
    - [`apply_light_client_update`](#apply_light_client_update)
    - [`process_light_client_update`](#process_light_client_update)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

Eth2 is designed to be light client friendly for constrained environments to
access Eth2 with reasonable safety and liveness.
Such environments include resource-constrained devices (e.g. phones for trust-minimised wallets)
and metered VMs (e.g. blockchain VMs for cross-chain bridges).

This document suggests a minimal light client design for the beacon chain that
uses sync committees introduced in [this beacon chain extension](./beacon-chain.md).

## Constants

| Name | Value |
| - | - |
| `FINALIZED_ROOT_INDEX` | `get_generalized_index(BeaconState, 'finalized_checkpoint', 'root')` |
| `NEXT_SYNC_COMMITTEE_INDEX` | `get_generalized_index(BeaconState, 'next_sync_committee')` |

## Configuration

### Misc

| Name | Value |
| - | - |
| `MIN_SYNC_COMMITTEE_PARTICIPANTS` | `1` |
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
    # Update beacon block header
    header: BeaconBlockHeader
    # Next sync committee corresponding to the header
    next_sync_committee: SyncCommittee
    next_sync_committee_branch: Vector[Bytes32, ceillog2(NEXT_SYNC_COMMITTEE_INDEX)]
    # Finality proof for the update header
    finality_header: BeaconBlockHeader
    finality_branch: Vector[Bytes32, ceillog2(FINALIZED_ROOT_INDEX)]
    # Sync committee aggregate signature
    sync_committee_bits: Bitvector[SYNC_COMMITTEE_SIZE]
    sync_committee_signature: BLSSignature
    # Fork version for the aggregate signature
    fork_version: Version
```

#### `LightClientStore`

```python
class LightClientStore(Container):
    snapshot: LightClientSnapshot
    valid_updates: List[LightClientUpdate, MAX_VALID_LIGHT_CLIENT_UPDATES]
```

## Light client state updates

A light client maintains its state in a `store` object of type `LightClientStore` and receives `update` objects of type `LightClientUpdate`. Every `update` triggers `process_light_client_update(store, update, current_slot)` where `current_slot` is the current slot based on some local clock.

#### `is_valid_light_client_update`

```python
def is_valid_light_client_update(snapshot: LightClientSnapshot, update: LightClientUpdate) -> bool:
    # Verify update slot is larger than snapshot slot
    assert update.header.slot > snapshot.header.slot

    # Verify update does not skip a sync committee period
    snapshot_period = compute_epoch_at_slot(snapshot.header.slot) // EPOCHS_PER_SYNC_COMMITTEE_PERIOD
    update_period = compute_epoch_at_slot(update.header.slot) // EPOCHS_PER_SYNC_COMMITTEE_PERIOD
    assert update_period in (snapshot_period, snapshot_period + 1)

    # Verify update header root is the finalized root of the finality header, if specified
    if update.finality_header == BeaconBlockHeader():
        signed_header = update.header
        assert update.finality_branch == [Bytes32() for _ in range(ceillog2(FINALIZED_ROOT_INDEX))]
    else:
        signed_header = update.finality_header
        assert is_valid_merkle_branch(
            leaf=hash_tree_root(update.header),
            branch=update.finality_branch,
            depth=ceillog2(FINALIZED_ROOT_INDEX),
            index=FINALIZED_ROOT_INDEX % 2**ceillog2(FINALIZED_ROOT_INDEX),
            root=update.finality_header.state_root,
        )

    # Verify update next sync committee if the update period incremented
    if update_period == snapshot_period:
        sync_committee = snapshot.current_sync_committee
        assert update.next_sync_committee_branch == [Bytes32() for _ in range(ceillog2(NEXT_SYNC_COMMITTEE_INDEX))]
    else:
        sync_committee = snapshot.next_sync_committee
        assert is_valid_merkle_branch(
            leaf=hash_tree_root(update.next_sync_committee),
            branch=update.next_sync_committee_branch,
            depth=ceillog2(NEXT_SYNC_COMMITTEE_INDEX),
            index=NEXT_SYNC_COMMITTEE_INDEX % 2**ceillog2(NEXT_SYNC_COMMITTEE_INDEX),
            root=update.header.state_root,
        )

    # Verify sync committee has sufficient participants
    assert sum(update.sync_committee_bits) >= MIN_SYNC_COMMITTEE_PARTICIPANTS

    # Verify sync committee aggregate signature
    participant_pubkeys = [pubkey for (bit, pubkey) in zip(update.sync_committee_bits, sync_committee.pubkeys) if bit]
    domain = compute_domain(DOMAIN_SYNC_COMMITTEE, update.fork_version)
    signing_root = compute_signing_root(signed_header, domain)
    assert bls.FastAggregateVerify(participant_pubkeys, signing_root, update.sync_committee_signature)

    return True
```

#### `apply_light_client_update`

```python
def apply_light_client_update(snapshot: LightClientSnapshot, update: LightClientUpdate) -> None:
    snapshot_period = compute_epoch_at_slot(snapshot.header.slot) // EPOCHS_PER_SYNC_COMMITTEE_PERIOD
    update_period = compute_epoch_at_slot(update.header.slot) // EPOCHS_PER_SYNC_COMMITTEE_PERIOD
    if update_period == snapshot_period + 1:
        snapshot.current_sync_committee = snapshot.next_sync_committee
        snapshot.next_sync_committee = update.next_sync_committee
    snapshot.header = update.header
```

#### `process_light_client_update`

```python
def process_light_client_update(store: LightClientStore, update: LightClientUpdate, current_slot: Slot) -> None:
    # Validate update
    assert is_valid_light_client_update(store.snapshot, update)
    store.valid_updates.append(update)

    if (
        sum(update.sync_committee_bits) * 3 > len(update.sync_committee_bits) * 2
        and update.header != update.finality_header
    ):
        # Apply update if 2/3 quorum is reached and we have a finality proof
        apply_light_client_update(store, update)
        store.valid_updates = []
    elif current_slot > store.snapshot.header.slot + LIGHT_CLIENT_UPDATE_TIMEOUT:
        # Forced best update when the update timeout has elapsed
        apply_light_client_update(store, max(store.valid_updates, key=lambda update: sum(update.sync_committee_bits)))
        store.valid_updates = []
```
