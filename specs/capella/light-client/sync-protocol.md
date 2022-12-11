# Capella Light Client -- Sync Protocol

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Constants](#constants)
- [Containers](#containers)
  - [`LightClientHeader`](#lightclientheader)
  - [Modified `LightClientBootstrap`](#modified-lightclientbootstrap)
  - [Modified `LightClientUpdate`](#modified-lightclientupdate)
  - [Modified `LightClientFinalityUpdate`](#modified-lightclientfinalityupdate)
  - [Modified `LightClientOptimisticUpdate`](#modified-lightclientoptimisticupdate)
  - [Modified `LightClientStore`](#modified-lightclientstore)
- [Helper functions](#helper-functions)
  - [Modified `get_lc_beacon_slot`](#modified-get_lc_beacon_slot)
  - [Modified `get_lc_beacon_root`](#modified-get_lc_beacon_root)
  - [`get_lc_execution_root`](#get_lc_execution_root)
  - [`is_valid_light_client_header`](#is_valid_light_client_header)
- [Light client initialization](#light-client-initialization)
  - [Modified `initialize_light_client_store`](#modified-initialize_light_client_store)
- [Light client state updates](#light-client-state-updates)
  - [Modified `validate_light_client_update`](#modified-validate_light_client_update)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This upgrade adds information about the execution payload to light client data as part of the Capella upgrade. It extends the [Altair Light Client specifications](../../altair/light-client/sync-protocol.md). The [fork document](./fork.md) explains how to upgrade existing Altair based deployments to Capella.

Additional documents describes the impact of the upgrade on certain roles:
- [Full node](./full-node.md)
- [Networking](./p2p-interface.md)

## Constants

| Name | Value |
| - | - |
| `EXECUTION_PAYLOAD_INDEX` | `get_generalized_index(BeaconBlockBody, 'execution_payload')` (= 25) |

## Containers

### `LightClientHeader`

```python
class LightClientHeader(Container):
    # Beacon block header
    beacon: BeaconBlockHeader
    # Execution payload header corresponding to `beacon.body_root` (from Capella onward)
    execution: ExecutionPayloadHeader
    execution_branch: Vector[Bytes32, floorlog2(EXECUTION_PAYLOAD_INDEX)]
```

### Modified `LightClientBootstrap`

```python
class LightClientBootstrap(Container):
    # Header matching the requested beacon block root
    header: LightClientHeader  # [Modified in Capella]
    # Current sync committee corresponding to `header.beacon.state_root`
    current_sync_committee: SyncCommittee
    current_sync_committee_branch: Vector[Bytes32, floorlog2(CURRENT_SYNC_COMMITTEE_INDEX)]
```

### Modified `LightClientUpdate`

```python
class LightClientUpdate(Container):
    # Header attested to by the sync committee
    attested_header: LightClientHeader  # [Modified in Capella]
    # Next sync committee corresponding to `attested_header.beacon.state_root`
    next_sync_committee: SyncCommittee
    next_sync_committee_branch: Vector[Bytes32, floorlog2(NEXT_SYNC_COMMITTEE_INDEX)]
    # Finalized header corresponding to `attested_header.beacon.state_root`
    finalized_header: LightClientHeader  # [Modified in Capella]
    finality_branch: Vector[Bytes32, floorlog2(FINALIZED_ROOT_INDEX)]
    # Sync committee aggregate signature
    sync_aggregate: SyncAggregate
    # Slot at which the aggregate signature was created (untrusted)
    signature_slot: Slot
```

### Modified `LightClientFinalityUpdate`

```python
class LightClientFinalityUpdate(Container):
    # Header attested to by the sync committee
    attested_header: LightClientHeader  # [Modified in Capella]
    # Finalized header corresponding to `attested_header.beacon.state_root`
    finalized_header: LightClientHeader  # [Modified in Capella]
    finality_branch: Vector[Bytes32, floorlog2(FINALIZED_ROOT_INDEX)]
    # Sync committee aggregate signature
    sync_aggregate: SyncAggregate
    # Slot at which the aggregate signature was created (untrusted)
    signature_slot: Slot
```

### Modified `LightClientOptimisticUpdate`

```python
class LightClientOptimisticUpdate(Container):
    # Header attested to by the sync committee
    attested_header: LightClientHeader  # [Modified in Capella]
    # Sync committee aggregate signature
    sync_aggregate: SyncAggregate
    # Slot at which the aggregate signature was created (untrusted)
    signature_slot: Slot
```

### Modified `LightClientStore`

```python
@dataclass
class LightClientStore(object):
    # Header that is finalized
    finalized_header: LightClientHeader  # [Modified in Capella]
    # Sync committees corresponding to the finalized header
    current_sync_committee: SyncCommittee
    next_sync_committee: SyncCommittee
    # Best available header to switch finalized head to if we see nothing else
    best_valid_update: Optional[LightClientUpdate]
    # Most recent available reasonably-safe header
    optimistic_header: LightClientHeader  # [Modified in Capella]
    # Max number of active participants in a sync committee (used to calculate safety threshold)
    previous_max_active_participants: uint64
    current_max_active_participants: uint64
```

## Helper functions

### Modified `get_lc_beacon_slot`

```python
def get_lc_beacon_slot(header: LightClientHeader) -> Slot:
    return header.beacon.slot
```

### Modified `get_lc_beacon_root`

```python
def get_lc_beacon_root(header: LightClientHeader) -> Root:
    return hash_tree_root(header.beacon)
```

### `get_lc_execution_root`

```python
def get_lc_execution_root(header: LightClientHeader) -> Root:
    if compute_epoch_at_slot(get_lc_beacon_slot(header)) >= CAPELLA_FORK_EPOCH:
        return hash_tree_root(header.execution)

    return Root()
```

### `is_valid_light_client_header`

```python
def is_valid_light_client_header(header: LightClientHeader) -> bool:
    if compute_epoch_at_slot(get_lc_beacon_slot(header)) >= CAPELLA_FORK_EPOCH:
        return is_valid_merkle_branch(
            leaf=get_lc_execution_root(header),
            branch=header.execution_branch,
            depth=floorlog2(EXECUTION_PAYLOAD_INDEX),
            index=get_subtree_index(EXECUTION_PAYLOAD_INDEX),
            root=header.beacon.body_root,
        )

    return (
        header.execution == ExecutionPayloadHeader()
        and header.execution_branch == [Bytes32() for _ in range(floorlog2(EXECUTION_PAYLOAD_INDEX))]
    )
```

## Light client initialization

### Modified `initialize_light_client_store`

```python
def initialize_light_client_store(trusted_block_root: Root,
                                  bootstrap: LightClientBootstrap) -> LightClientStore:
    assert is_valid_light_client_header(bootstrap.header)  # [New in Capella]
    assert get_lc_beacon_root(bootstrap.header) == trusted_block_root

    assert is_valid_merkle_branch(
        leaf=hash_tree_root(bootstrap.current_sync_committee),
        branch=bootstrap.current_sync_committee_branch,
        depth=floorlog2(CURRENT_SYNC_COMMITTEE_INDEX),
        index=get_subtree_index(CURRENT_SYNC_COMMITTEE_INDEX),
        root=bootstrap.header.beacon.state_root,  # [Modified in Capella]
    )

    return LightClientStore(
        finalized_header=bootstrap.header,
        current_sync_committee=bootstrap.current_sync_committee,
        next_sync_committee=SyncCommittee(),
        best_valid_update=None,
        optimistic_header=bootstrap.header,
        previous_max_active_participants=0,
        current_max_active_participants=0,
    )
```

## Light client state updates

### Modified `validate_light_client_update`

```python
def validate_light_client_update(store: LightClientStore,
                                 update: LightClientUpdate,
                                 current_slot: Slot,
                                 genesis_validators_root: Root) -> None:
    # Verify sync committee has sufficient participants
    sync_aggregate = update.sync_aggregate
    assert sum(sync_aggregate.sync_committee_bits) >= MIN_SYNC_COMMITTEE_PARTICIPANTS

    # Verify update does not skip a sync committee period
    assert is_valid_light_client_header(update.attested_header)  # [New in Capella]
    update_attested_slot = get_lc_beacon_slot(update.attested_header)
    update_finalized_slot = get_lc_beacon_slot(update.finalized_header)
    assert current_slot >= update.signature_slot > update_attested_slot >= update_finalized_slot
    store_period = compute_sync_committee_period_at_slot(get_lc_beacon_slot(store.finalized_header))
    update_signature_period = compute_sync_committee_period_at_slot(update.signature_slot)
    if is_next_sync_committee_known(store):
        assert update_signature_period in (store_period, store_period + 1)
    else:
        assert update_signature_period == store_period

    # Verify update is relevant
    update_attested_period = compute_sync_committee_period_at_slot(update_attested_slot)
    update_has_next_sync_committee = not is_next_sync_committee_known(store) and (
        is_sync_committee_update(update) and update_attested_period == store_period
    )
    assert update_attested_slot > update_finalized_slot or update_has_next_sync_committee

    # Verify that the `finality_branch`, if present, confirms `finalized_header.beacon`
    # to match the finalized checkpoint root saved in the state of `attested_header.beacon`.
    # Note that the genesis finalized checkpoint root is represented as a zero hash.
    if not is_finality_update(update):
        assert update.finalized_header == LightClientHeader()  # [Modified in Capella]
    else:
        if update_finalized_slot == GENESIS_SLOT:
            assert update.finalized_header == LightClientHeader()  # [Modified in Capella]
            finalized_root = Bytes32()
        else:
            assert is_valid_light_client_header(update.finalized_header)  # [New in Capella]
            finalized_root = get_lc_beacon_root(update.finalized_header)
        assert is_valid_merkle_branch(
            leaf=finalized_root,
            branch=update.finality_branch,
            depth=floorlog2(FINALIZED_ROOT_INDEX),
            index=get_subtree_index(FINALIZED_ROOT_INDEX),
            root=update.attested_header.beacon.state_root,  # [Modified in Capella]
        )

    # Verify that the `next_sync_committee`, if present, actually is the next sync committee saved in the
    # state of the `attested_header.beacon`
    if not is_sync_committee_update(update):
        assert update.next_sync_committee == SyncCommittee()
    else:
        if update_attested_period == store_period and is_next_sync_committee_known(store):
            assert update.next_sync_committee == store.next_sync_committee
        assert is_valid_merkle_branch(
            leaf=hash_tree_root(update.next_sync_committee),
            branch=update.next_sync_committee_branch,
            depth=floorlog2(NEXT_SYNC_COMMITTEE_INDEX),
            index=get_subtree_index(NEXT_SYNC_COMMITTEE_INDEX),
            root=update.attested_header.beacon.state_root,  # [Modified in Capella]
        )

    # Verify sync committee aggregate signature
    if update_signature_period == store_period:
        sync_committee = store.current_sync_committee
    else:
        sync_committee = store.next_sync_committee
    participant_pubkeys = [
        pubkey for (bit, pubkey) in zip(sync_aggregate.sync_committee_bits, sync_committee.pubkeys)
        if bit
    ]
    fork_version = compute_fork_version(compute_epoch_at_slot(update.signature_slot))
    domain = compute_domain(DOMAIN_SYNC_COMMITTEE, fork_version, genesis_validators_root)
    signing_root = compute_signing_root(update.attested_header.beacon, domain)  # [Modified in Capella]
    assert bls.FastAggregateVerify(participant_pubkeys, signing_root, sync_aggregate.sync_committee_signature)
```
