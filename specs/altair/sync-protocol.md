# Altair -- Minimal Light Client

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Constants](#constants)
- [Preset](#preset)
  - [Misc](#misc)
- [Containers](#containers)
  - [`LightClientUpdate`](#lightclientupdate)
  - [`LightClientStore`](#lightclientstore)
- [Helper functions](#helper-functions)
  - [`get_subtree_index`](#get_subtree_index)
  - [`get_active_header`](#get_active_header)
  - [`get_safety_threshold`](#get_safety_threshold)
- [Light client state updates](#light-client-state-updates)
    - [`process_slot`](#process_slot)
    - [`validate_light_client_update`](#validate_light_client_update)
    - [`apply_light_client_update`](#apply_light_client_update)
    - [`process_light_client_update`](#process_light_client_update)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

The beacon chain is designed to be light client friendly for constrained environments to
access Ethereum with reasonable safety and liveness.
Such environments include resource-constrained devices (e.g. phones for trust-minimised wallets)
and metered VMs (e.g. blockchain VMs for cross-chain bridges).

This document suggests a minimal light client design for the beacon chain that
uses sync committees introduced in [this beacon chain extension](./beacon-chain.md).

## Constants

| Name | Value |
| - | - |
| `FINALIZED_ROOT_INDEX` | `get_generalized_index(BeaconState, 'finalized_checkpoint', 'root')` |
| `NEXT_SYNC_COMMITTEE_INDEX` | `get_generalized_index(BeaconState, 'next_sync_committee')` |

## Preset

### Misc

| Name | Value | Notes |
| - | - | - |
| `MIN_SYNC_COMMITTEE_PARTICIPANTS` | `1` | |
| `UPDATE_TIMEOUT` | `SLOTS_PER_EPOCH * EPOCHS_PER_SYNC_COMMITTEE_PERIOD` | ~27.3 hours |
| `SAFETY_THRESHOLD_PERIOD` | `SLOTS_PER_EPOCH * EPOCHS_PER_SYNC_COMMITTEE_PERIOD // 2` | ~13.6 hours |

## Containers

### `LightClientUpdate`

```python
class LightClientUpdate(Container):
    # The beacon block header that is attested to by the sync committee
    attested_header: BeaconBlockHeader
    # Next sync committee corresponding to the active header
    next_sync_committee: SyncCommittee
    next_sync_committee_branch: Vector[Bytes32, floorlog2(NEXT_SYNC_COMMITTEE_INDEX)]
    # The finalized beacon block header attested to by Merkle branch
    finalized_header: BeaconBlockHeader
    finality_branch: Vector[Bytes32, floorlog2(FINALIZED_ROOT_INDEX)]
    # Sync committee aggregate signature
    sync_committee_bits: Bitvector[SYNC_COMMITTEE_SIZE]
    sync_committee_signature: BLSSignature
    # Fork version for the aggregate signature
    fork_version: Version
```

### `LightClientStore`

```python
@dataclass
class LightClientStore(object):
    # Beacon block header that is finalized
    finalized_header: BeaconBlockHeader
    # Sync committees corresponding to the header
    current_sync_committee: SyncCommittee
    next_sync_committee: SyncCommittee
    # Best available header to switch finalized head to if we see nothing else
    best_valid_update: Optional[LightClientUpdate]
    # Most recent available reasonably-safe header
    optimistic_header: BeaconBlockHeader
    # Max number of active participants in a sync committee (used to calculate safety threshold)
    previous_max_active_participants: uint64
    current_max_active_participants: uint64
```

## Helper functions

### `get_subtree_index`

```python
def get_subtree_index(generalized_index: GeneralizedIndex) -> uint64:
    return uint64(generalized_index % 2**(floorlog2(generalized_index)))
```

### `get_active_header`

```python
def get_active_header(update: LightClientUpdate) -> BeaconBlockHeader:
    # The "active header" is the header that the update is trying to convince us
    # to accept. If a finalized header is present, it's the finalized header,
    # otherwise it's the attested header
    if update.finalized_header != BeaconBlockHeader():
        return update.finalized_header
    else:
        return update.attested_header
```

### `get_safety_threshold`

```python
def get_safety_threshold(store: LightClientStore) -> uint64:
    return max(
        store.previous_max_active_participants,     
        store.current_max_active_participants
    ) // 2
```

## Light client state updates

A light client maintains its state in a `store` object of type `LightClientStore` and receives `update` objects of type `LightClientUpdate`. Every `update` triggers `process_light_client_update(store, update, current_slot)` where `current_slot` is the current slot based on some local clock. `process_slot` is processed every time the current slot increments.

#### `process_slot`

```python
def process_slot_for_light_client_store(store: LightClientStore, current_slot: Slot) -> None:
    if current_slot % SAFETY_THRESHOLD_PERIOD == 0:
        store.previous_max_active_participants = store.current_max_active_participants
        store.current_max_active_participants = 0
```

#### `validate_light_client_update`

```python
def validate_light_client_update(store: LightClientStore,
                                 update: LightClientUpdate,
                                 current_slot: Slot,
                                 genesis_validators_root: Root) -> None:
                                 
    # Verify update slot is larger than slot of current best finalized header
    active_header = get_active_header(update)
    assert current_slot >= active_header.slot > store.finalized_header.slot

    # Verify update does not skip a sync committee period
    finalized_period = compute_epoch_at_slot(store.finalized_header.slot) // EPOCHS_PER_SYNC_COMMITTEE_PERIOD
    update_period = compute_epoch_at_slot(active_header.slot) // EPOCHS_PER_SYNC_COMMITTEE_PERIOD
    assert update_period in (finalized_period, finalized_period + 1)

    # Verify update header root is the finalized root of the finality header, if specified
    if update.finalized_header == BeaconBlockHeader():
        assert update.finality_branch == [Bytes32() for _ in range(floorlog2(FINALIZED_ROOT_INDEX))]
    else:
        assert is_valid_merkle_branch(
            leaf=hash_tree_root(update.finalized_header),
            branch=update.finality_branch,
            depth=floorlog2(FINALIZED_ROOT_INDEX),
            index=get_subtree_index(FINALIZED_ROOT_INDEX),
            root=update.attested_header.state_root,
        )

    # Verify update next sync committee if the update period incremented
    if update_period == finalized_period:
        sync_committee = store.current_sync_committee
        assert update.next_sync_committee_branch == [Bytes32() for _ in range(floorlog2(NEXT_SYNC_COMMITTEE_INDEX))]
    else:
        sync_committee = store.next_sync_committee
        assert is_valid_merkle_branch(
            leaf=hash_tree_root(update.next_sync_committee),
            branch=update.next_sync_committee_branch,
            depth=floorlog2(NEXT_SYNC_COMMITTEE_INDEX),
            index=get_subtree_index(NEXT_SYNC_COMMITTEE_INDEX),
            root=active_header.state_root,
        )

    # Verify sync committee has sufficient participants
    assert sum(update.sync_committee_bits) >= MIN_SYNC_COMMITTEE_PARTICIPANTS

    # Verify sync committee aggregate signature
    participant_pubkeys = [pubkey for (bit, pubkey) in zip(update.sync_committee_bits, sync_committee.pubkeys) if bit]
    domain = compute_domain(DOMAIN_SYNC_COMMITTEE, update.fork_version, genesis_validators_root)
    signing_root = compute_signing_root(update.attested_header, domain)
    assert bls.FastAggregateVerify(participant_pubkeys, signing_root, update.sync_committee_signature)
```

#### `apply_light_client_update`

```python
def apply_light_client_update(store: LightClientStore, update: LightClientUpdate) -> None:
    active_header = get_active_header(update)
    finalized_period = compute_epoch_at_slot(store.finalized_header.slot) // EPOCHS_PER_SYNC_COMMITTEE_PERIOD
    update_period = compute_epoch_at_slot(active_header.slot) // EPOCHS_PER_SYNC_COMMITTEE_PERIOD
    if update_period == finalized_period + 1:
        store.current_sync_committee = store.next_sync_committee
        store.next_sync_committee = update.next_sync_committee
    store.finalized_header = active_header
```

#### `process_light_client_update`

```python
def process_light_client_update(store: LightClientStore,
                                update: LightClientUpdate,
                                current_slot: Slot,
                                genesis_validators_root: Root) -> None:
                                
    validate_light_client_update(store, update, current_slot, genesis_validators_root)
    
    # Update the best update in case we have to force-update to it if the timeout elapses
    if (
        store.best_valid_update is None
        or sum(update.sync_committee_bits) > sum(store.best_valid_update.sync_committee_bits)
    ):
        store.best_valid_update = update
    
    # Track the maximum number of active participants in the committee signatures
    store.current_max_active_participants = max(
        store.current_max_active_participants,
        update.sync_committee_bits.count(1),
    )
    
    # Update the optimistic header
    if (
        sum(update.sync_committee_bits) > get_safety_threshold(store) and
        update.attested_header.slot > store.optimistic_header.slot
    ):
        store.optimistic_header = update.attested_header
    
    # Update finalized header
    if (
        sum(update.sync_committee_bits) * 3 >= len(update.sync_committee_bits) * 2
        and update.finalized_header != BeaconBlockHeader()
    ):
        # Normal update through 2/3 threshold
        apply_light_client_update(store, update)
        store.best_valid_update = None
    elif (
        current_slot > store.finalized_header.slot + UPDATE_TIMEOUT
        and store.best_valid_update is not None
    ):
        # Forced best update when the update timeout has elapsed
        apply_light_client_update(store, store.best_valid_update)
        store.best_valid_update = None
```
