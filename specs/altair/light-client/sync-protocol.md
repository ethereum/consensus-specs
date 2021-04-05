# Ethereum Altair Minimal Light Client

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Sync protocol](#sync-protocol)
  - [Initialization](#initialization)
  - [Minimal light client update](#minimal-light-client-update)
- [Constants](#constants)
- [Configuration](#configuration)
  - [Misc](#misc)
  - [Time parameters](#time-parameters)
- [Containers](#containers)
  - [`LightClientSnapshot`](#lightclientsnapshot)
  - [`LightClientUpdate`](#lightclientupdate)
  - [`LightClientStore`](#lightclientstore)
- [Helper functions](#helper-functions)
  - [`get_subtree_index`](#get_subtree_index)
  - [`get_light_client_store`](#get_light_client_store)
  - [`get_light_client_slots_since_genesis`](#get_light_client_slots_since_genesis)
  - [`get_light_client_current_slot`](#get_light_client_current_slot)
  - [`validate_light_client_update`](#validate_light_client_update)
  - [`apply_light_client_update`](#apply_light_client_update)
- [Client side handlers](#client-side-handlers)
  - [`on_light_client_tick`](#on_light_client_tick)
  - [`on_light_client_update`](#on_light_client_update)
- [Server side handlers](#server-side-handlers)
- [Reorg mechanism](#reorg-mechanism)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

Eth2 is designed to be light client friendly for constrained environments to
access Eth2 with reasonable safety and liveness.
Such environments include resource-constrained devices (e.g. phones for trust-minimized wallets)
and metered VMs (e.g. blockchain VMs for cross-chain bridges).

This document suggests a minimal light client design for the beacon chain that
uses sync committees introduced in [this beacon chain extension](./../beacon-chain.md).

## Sync protocol

Note that in this syncing mechanism, the server is trusted.

### Initialization

1. The client sends `Status` message to the server to exchange the status information.
2. Instead of sending `BeaconBlocksByRange` in the beacon chain syncing, the client sends `GetLightClientSnapshot` request to the server.
3. The server responds with the `LightClientSnapshot` object of the finalized beacon chain head.
4. The client would:
    1. check if the hash tree root of the given `header` matches the `finalized_root` in the server's `Status` message.
    2. check if the given response is valid for client to call `get_light_client_store` function to get the initial `store: LightClientStore`.
    - If it's invalid, disconnect from the server; otherwise, keep syncing.

### Minimal light client update

In this minimal light client design, the light client only follows finality updates.

#### Server side

- Whenever `state.finalized_checkpoint` is changed, call `get_light_client_update` to generate the `LightClientUpdate` and then send to its light clients.

#### Client side

- `on_light_client_tick(store, time)` whenever `time > store.time` where `time` is the current Unix time
- `on_light_client_update(store, update)` whenever a block `update: LightClientUpdate` is received

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

### `LightClientSnapshot`

```python
class LightClientSnapshot(Container):
    # Beacon block header
    header: BeaconBlockHeader
    # Sync committees corresponding to the header
    current_sync_committee: SyncCommittee
    next_sync_committee: SyncCommittee
```

### `LightClientUpdate`

```python
class LightClientUpdate(Container):
    # Update beacon block header
    header: BeaconBlockHeader
    # Next sync committee corresponding to the header
    next_sync_committee: SyncCommittee
    next_sync_committee_branch: Vector[Bytes32, floorlog2(NEXT_SYNC_COMMITTEE_INDEX)]
    # Finality proof for the update header
    finality_header: BeaconBlockHeader
    finality_branch: Vector[Bytes32, floorlog2(FINALIZED_ROOT_INDEX)]
    # Sync committee aggregate signature
    sync_aggregate: SyncAggregate
    # Fork version for the aggregate signature
    fork_version: Version
```

### `LightClientStore`

```python
class LightClientStore(Container):
    time: uint64
    genesis_time: uint64
    genesis_validators_root: Root
    snapshot: LightClientSnapshot
    valid_updates: List[LightClientUpdate, MAX_VALID_LIGHT_CLIENT_UPDATES]
```

## Helper functions

### `get_subtree_index`

```python
def get_subtree_index(generalized_index: GeneralizedIndex) -> uint64:
    return uint64(generalized_index % 2**(floorlog2(generalized_index)))
```

### `get_light_client_store`

```python
def get_light_client_store(snapshot: LightClientSnapshot,
                           genesis_time: uint64, genesis_validators_root: Root) -> LightClientStore:
    return LightClientStore(
        time=uint64(genesis_time + SECONDS_PER_SLOT * snapshot.header.slot),
        genesis_time=genesis_time,
        genesis_validators_root=genesis_validators_root,
        snapshot=snapshot,
        valid_updates=[],
    )
```

### `get_light_client_slots_since_genesis`

```python
def get_light_client_slots_since_genesis(store: LightClientStore) -> int:
    return (store.time - store.genesis_time) // SECONDS_PER_SLOT
```

### `get_light_client_current_slot`

```python
def get_light_client_current_slot(store: LightClientStore) -> Slot:
    return Slot(GENESIS_SLOT + get_light_client_slots_since_genesis(store))
```

### `validate_light_client_update`

```python
def validate_light_client_update(store: LightClientStore, update: LightClientUpdate) -> None:
    snapshot = store.snapshot

    # Verify update slot is larger than snapshot slot
    assert update.header.slot > snapshot.header.slot

    # Verify time
    update_time = uint64(store.genesis_time + SECONDS_PER_SLOT * update.header.slot)
    assert store.time >= update_time

    # Verify update does not skip a sync committee period
    snapshot_epoch = compute_epoch_at_slot(snapshot.header.slot)
    update_epoch = compute_epoch_at_slot(update.header.slot)
    snapshot_period = compute_sync_committee_period(snapshot_epoch)
    update_period = compute_sync_committee_period(update_epoch)
    assert update_period in (snapshot_period, snapshot_period + 1)

    # Verify update header root is the finalized root of the finality header, if specified
    if update.finality_header == BeaconBlockHeader():
        signed_header = update.header
        assert update.finality_branch == [Bytes32() for _ in range(floorlog2(FINALIZED_ROOT_INDEX))]
    else:
        signed_header = update.finality_header
        assert is_valid_merkle_branch(
            leaf=hash_tree_root(update.header),
            branch=update.finality_branch,
            depth=floorlog2(FINALIZED_ROOT_INDEX),
            index=get_subtree_index(FINALIZED_ROOT_INDEX),
            root=update.finality_header.state_root,
        )

    # Verify update next sync committee if the update period incremented
    if update_period == snapshot_period:
        sync_committee = snapshot.current_sync_committee
        assert update.next_sync_committee_branch == [Bytes32() for _ in range(floorlog2(NEXT_SYNC_COMMITTEE_INDEX))]
    else:
        sync_committee = snapshot.next_sync_committee
        assert is_valid_merkle_branch(
            leaf=hash_tree_root(update.next_sync_committee),
            branch=update.next_sync_committee_branch,
            depth=floorlog2(NEXT_SYNC_COMMITTEE_INDEX),
            index=get_subtree_index(NEXT_SYNC_COMMITTEE_INDEX),
            root=update.header.state_root,
        )

    # Verify sync committee has sufficient participants
    assert sum(update.sync_aggregate.sync_committee_bits) >= MIN_SYNC_COMMITTEE_PARTICIPANTS

    # Verify sync committee aggregate signature
    participant_pubkeys = [pubkey for (bit, pubkey)
                           in zip(update.sync_aggregate.sync_committee_bits, sync_committee.pubkeys) if bit]
    domain = compute_domain(DOMAIN_SYNC_COMMITTEE, update.fork_version, store.genesis_validators_root)
    signing_root = compute_signing_root(signed_header, domain)
    assert bls.FastAggregateVerify(participant_pubkeys, signing_root, update.sync_aggregate.sync_committee_signature)
```

### `apply_light_client_update`

```python
def apply_light_client_update(snapshot: LightClientSnapshot, update: LightClientUpdate) -> None:
    snapshot_epoch = compute_epoch_at_slot(snapshot.header.slot)
    update_epoch = compute_epoch_at_slot(update.header.slot)
    snapshot_period = compute_sync_committee_period(snapshot_epoch)
    update_period = compute_sync_committee_period(update_epoch)
    if update_period == snapshot_period + 1:
        snapshot.current_sync_committee = snapshot.next_sync_committee
        snapshot.next_sync_committee = update.next_sync_committee
    snapshot.header = update.header
```

## Client side handlers

### `on_light_client_tick`

```python
def on_light_client_tick(store: LightClientStore, time: uint64) -> None:
    # update store time
    store.time = time
```

### `on_light_client_update`

A light client maintains its state in a `store` object of type `LightClientStore` and receives `update` objects of type `LightClientUpdate`. Every `update` triggers `on_light_client_update(store, update)`.

```python
def on_light_client_update(store: LightClientStore, update: LightClientUpdate) -> None:
    validate_light_client_update(store, update)
    store.valid_updates.append(update)

    if (
        sum(update.sync_aggregate.sync_committee_bits) * 3 > len(update.sync_aggregate.sync_committee_bits) * 2
        and update.finality_header != BeaconBlockHeader()
    ):
        # Apply update if (1) 2/3 quorum is reached and (2) we have a finality proof.
        # Note that (2) means that the current light client design needs finality.
        # It may be changed to re-organizable light client design. See the on-going issue eth2.0-specs#2182.
        apply_light_client_update(store.snapshot, update)
        store.valid_updates = []
    elif get_light_client_current_slot(store) > store.snapshot.header.slot + LIGHT_CLIENT_UPDATE_TIMEOUT:
        # Forced best update when the update timeout has elapsed
        apply_light_client_update(
            store.snapshot,
            max(store.valid_updates, key=lambda update: sum(update.sync_aggregate.sync_committee_bits))
        )
        store.valid_updates = []
```

## Server side handlers

[TODO]

```python
def get_light_client_update(state: BeaconState) -> LightClientUpdate:
    # [TODO]
    pass
```

## Reorg mechanism

[TODO] PR#2182 discussion
