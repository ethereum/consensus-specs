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
  - [`is_sync_committee_update`](#is_sync_committee_update)
  - [`is_finality_update`](#is_finality_update)
  - [`is_better_update`](#is_better_update)
  - [`get_safety_threshold`](#get_safety_threshold)
  - [`get_subtree_index`](#get_subtree_index)
  - [`compute_sync_committee_period_at_slot`](#compute_sync_committee_period_at_slot)
- [Light client state updates](#light-client-state-updates)
    - [`process_slot_for_light_client_store`](#process_slot_for_light_client_store)
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
| `FINALIZED_ROOT_INDEX` | `get_generalized_index(BeaconState, 'finalized_checkpoint', 'root')` (= 105) |
| `NEXT_SYNC_COMMITTEE_INDEX` | `get_generalized_index(BeaconState, 'next_sync_committee')` (= 55) |

## Preset

### Misc

| Name | Value | Unit | Duration |
| - | - | - | - |
| `MIN_SYNC_COMMITTEE_PARTICIPANTS` | `1` | validators | |
| `UPDATE_TIMEOUT` | `SLOTS_PER_EPOCH * EPOCHS_PER_SYNC_COMMITTEE_PERIOD` | slots | ~27.3 hours |

## Containers

### `LightClientUpdate`

```python
class LightClientUpdate(Container):
    # The beacon block header that is attested to by the sync committee
    attested_header: BeaconBlockHeader
    # Next sync committee corresponding to `attested_header`
    next_sync_committee: SyncCommittee
    next_sync_committee_branch: Vector[Bytes32, floorlog2(NEXT_SYNC_COMMITTEE_INDEX)]
    # The finalized beacon block header attested to by Merkle branch
    finalized_header: BeaconBlockHeader
    finality_branch: Vector[Bytes32, floorlog2(FINALIZED_ROOT_INDEX)]
    # Sync committee aggregate signature
    sync_aggregate: SyncAggregate
    # Slot at which the aggregate signature was created (untrusted)
    signature_slot: Slot
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

### `is_sync_committee_update`

```python
def is_sync_committee_update(update: LightClientUpdate) -> bool:
    return update.next_sync_committee_branch != [Bytes32() for _ in range(floorlog2(NEXT_SYNC_COMMITTEE_INDEX))]
```

### `is_finality_update`

```python
def is_finality_update(update: LightClientUpdate) -> bool:
    return update.finality_branch != [Bytes32() for _ in range(floorlog2(FINALIZED_ROOT_INDEX))]
```

### `is_better_update`

```python
def is_better_update(new_update: LightClientUpdate, old_update: LightClientUpdate) -> bool:
    # Compare supermajority (> 2/3) sync committee participation
    max_active_participants = len(new_update.sync_aggregate.sync_committee_bits)
    new_num_active_participants = sum(new_update.sync_aggregate.sync_committee_bits)
    old_num_active_participants = sum(old_update.sync_aggregate.sync_committee_bits)
    new_has_supermajority = new_num_active_participants * 3 >= max_active_participants * 2
    old_has_supermajority = old_num_active_participants * 3 >= max_active_participants * 2
    if new_has_supermajority != old_has_supermajority:
        return new_has_supermajority > old_has_supermajority
    if not new_has_supermajority and new_num_active_participants != old_num_active_participants:
        return new_num_active_participants > old_num_active_participants

    # Compare indication of any finality
    new_has_finality = is_finality_update(new_update)
    old_has_finality = is_finality_update(old_update)
    if new_has_finality != old_has_finality:
        return new_has_finality

    # Compare sync committee finality
    if new_has_finality:
        new_has_sync_committee_finality = (
            compute_sync_committee_period_at_slot(new_update.finalized_header.slot) ==
            compute_sync_committee_period_at_slot(new_update.attested_header.slot)
        )
        old_has_sync_committee_finality = (
            compute_sync_committee_period_at_slot(old_update.finalized_header.slot) ==
            compute_sync_committee_period_at_slot(old_update.attested_header.slot)
        )
        if new_has_sync_committee_finality != old_has_sync_committee_finality:
            return new_has_sync_committee_finality > old_has_sync_committee_finality

    # Tiebreaker 1: Sync committee participation beyond supermajority
    if new_num_active_participants != old_num_active_participants:
        return new_num_active_participants > old_num_active_participants

    # Tiebreaker 2: Prefer older data (fewer changes to best)
    if new_update.attested_header.slot != old_update.attested_header.slot:
        return new_update.attested_header.slot < old_update.attested_header.slot
    return new_update.signature_slot < old_update.signature_slot
```

### `get_safety_threshold`

```python
def get_safety_threshold(store: LightClientStore) -> uint64:
    return max(
        store.previous_max_active_participants,
        store.current_max_active_participants,
    ) // 2
```

### `get_subtree_index`

```python
def get_subtree_index(generalized_index: GeneralizedIndex) -> uint64:
    return uint64(generalized_index % 2**(floorlog2(generalized_index)))
```

### `compute_sync_committee_period_at_slot`

```python
def compute_sync_committee_period_at_slot(slot: Slot) -> uint64:
    return compute_sync_committee_period(compute_epoch_at_slot(slot))
```

## Light client state updates

A light client maintains its state in a `store` object of type `LightClientStore` and receives `update` objects of type `LightClientUpdate`. Every `update` triggers `process_light_client_update(store, update, current_slot, genesis_validators_root)` where `current_slot` is the current slot based on a local clock. `process_slot_for_light_client_store` is triggered every time the current slot increments.

#### `process_slot_for_light_client_store`

```python
def process_slot_for_light_client_store(store: LightClientStore, current_slot: Slot) -> None:
    if current_slot % UPDATE_TIMEOUT == 0:
        store.previous_max_active_participants = store.current_max_active_participants
        store.current_max_active_participants = 0
    if (
        current_slot > store.finalized_header.slot + UPDATE_TIMEOUT
        and store.best_valid_update is not None
    ):
        # Forced best update when the update timeout has elapsed
        if store.best_valid_update.finalized_header.slot <= store.finalized_header.slot:
            store.best_valid_update.finalized_header = store.best_valid_update.attested_header
        apply_light_client_update(store, store.best_valid_update)
        store.best_valid_update = None
```

#### `validate_light_client_update`

```python
def validate_light_client_update(store: LightClientStore,
                                 update: LightClientUpdate,
                                 current_slot: Slot,
                                 genesis_validators_root: Root) -> None:
    # Verify sync committee has sufficient participants
    sync_aggregate = update.sync_aggregate
    assert sum(sync_aggregate.sync_committee_bits) >= MIN_SYNC_COMMITTEE_PARTICIPANTS

    # Verify update does not skip a sync committee period
    assert current_slot >= update.signature_slot > update.attested_header.slot >= update.finalized_header.slot
    store_period = compute_sync_committee_period_at_slot(store.finalized_header.slot)
    signature_period = compute_sync_committee_period_at_slot(update.signature_slot)
    assert signature_period in (store_period, store_period + 1)

    # Verify update is relevant
    attested_period = compute_sync_committee_period_at_slot(update.attested_header.slot)
    assert update.attested_header.slot > store.finalized_header.slot

    # Verify that the `finality_branch`, if present, confirms `finalized_header`
    # to match the finalized checkpoint root saved in the state of `attested_header`.
    # Note that the genesis finalized checkpoint root is represented as a zero hash.
    if not is_finality_update(update):
        assert update.finalized_header == BeaconBlockHeader()
    else:
        if update.finalized_header.slot == GENESIS_SLOT:
            finalized_root = Bytes32()
            assert update.finalized_header == BeaconBlockHeader()
        else:
            finalized_root = hash_tree_root(update.finalized_header)
        assert is_valid_merkle_branch(
            leaf=finalized_root,
            branch=update.finality_branch,
            depth=floorlog2(FINALIZED_ROOT_INDEX),
            index=get_subtree_index(FINALIZED_ROOT_INDEX),
            root=update.attested_header.state_root,
        )

    # Verify that the `next_sync_committee`, if present, actually is the next sync committee saved in the
    # state of the `attested_header`
    if not is_sync_committee_update(update):
        assert attested_period == store_period
        assert update.next_sync_committee == SyncCommittee()
    else:
        if attested_period == store_period:
            assert update.next_sync_committee == store.next_sync_committee
        assert is_valid_merkle_branch(
            leaf=hash_tree_root(update.next_sync_committee),
            branch=update.next_sync_committee_branch,
            depth=floorlog2(NEXT_SYNC_COMMITTEE_INDEX),
            index=get_subtree_index(NEXT_SYNC_COMMITTEE_INDEX),
            root=update.attested_header.state_root,
        )

    # Verify sync committee aggregate signature
    if signature_period == store_period:
        sync_committee = store.current_sync_committee
    else:
        sync_committee = store.next_sync_committee
    participant_pubkeys = [
        pubkey for (bit, pubkey) in zip(sync_aggregate.sync_committee_bits, sync_committee.pubkeys)
        if bit
    ]
    fork_version = compute_fork_version(compute_epoch_at_slot(update.signature_slot))
    domain = compute_domain(DOMAIN_SYNC_COMMITTEE, fork_version, genesis_validators_root)
    signing_root = compute_signing_root(update.attested_header, domain)
    assert bls.FastAggregateVerify(participant_pubkeys, signing_root, sync_aggregate.sync_committee_signature)
```

#### `apply_light_client_update`

```python
def apply_light_client_update(store: LightClientStore, update: LightClientUpdate) -> None:
    store_period = compute_sync_committee_period_at_slot(store.finalized_header.slot)
    finalized_period = compute_sync_committee_period_at_slot(update.finalized_header.slot)
    if finalized_period == store_period + 1:
        store.current_sync_committee = store.next_sync_committee
        store.next_sync_committee = update.next_sync_committee
    store.finalized_header = update.finalized_header
    if store.finalized_header.slot > store.optimistic_header.slot:
        store.optimistic_header = store.finalized_header
```

#### `process_light_client_update`

```python
def process_light_client_update(store: LightClientStore,
                                update: LightClientUpdate,
                                current_slot: Slot,
                                genesis_validators_root: Root) -> None:
    validate_light_client_update(store, update, current_slot, genesis_validators_root)

    sync_committee_bits = update.sync_aggregate.sync_committee_bits

    # Update the best update in case we have to force-update to it if the timeout elapses
    if (
        store.best_valid_update is None
        or is_better_update(update, store.best_valid_update)
    ):
        store.best_valid_update = update

    # Track the maximum number of active participants in the committee signatures
    store.current_max_active_participants = max(
        store.current_max_active_participants,
        sum(sync_committee_bits),
    )

    # Update the optimistic header
    if (
        sum(sync_committee_bits) > get_safety_threshold(store)
        and update.attested_header.slot > store.optimistic_header.slot
    ):
        store.optimistic_header = update.attested_header

    # Update finalized header
    if (
        sum(sync_committee_bits) * 3 >= len(sync_committee_bits) * 2
        and update.finalized_header.slot > store.finalized_header.slot
    ):
        # Normal update through 2/3 threshold
        apply_light_client_update(store, update)
        store.best_valid_update = None
```
