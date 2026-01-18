# Capella Light Client -- Sync Protocol

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Types](#types)
- [Constants](#constants)
- [Containers](#containers)
  - [Modified `LightClientHeader`](#modified-lightclientheader)
  - [Modified `LightClientBootstrap`](#modified-lightclientbootstrap)
  - [Modified `LightClientUpdate`](#modified-lightclientupdate)
  - [Modified `LightClientFinalityUpdate`](#modified-lightclientfinalityupdate)
  - [Modified `LightClientOptimisticUpdate`](#modified-lightclientoptimisticupdate)
  - [Modified `LightClientStore`](#modified-lightclientstore)
- [Helpers](#helpers)
  - [`get_lc_execution_root`](#get_lc_execution_root)
  - [Modified `is_valid_light_client_header`](#modified-is_valid_light_client_header)

<!-- mdformat-toc end -->

## Introduction

This upgrade adds information about the execution payload to light client data
as part of the Capella upgrade. It extends the
[Altair Light Client specifications](../../altair/light-client/sync-protocol.md).
The [fork document](./fork.md) explains how to upgrade existing Altair based
deployments to Capella.

Additional documents describes the impact of the upgrade on certain roles:

- [Full node](./full-node.md)
- [Networking](./p2p-interface.md)

## Types

| Name              | SSZ equivalent                                         | Description                                                   |
| ----------------- | ------------------------------------------------------ | ------------------------------------------------------------- |
| `ExecutionBranch` | `Vector[Bytes32, floorlog2(EXECUTION_PAYLOAD_GINDEX)]` | Merkle branch of `execution_payload` within `BeaconBlockBody` |

## Constants

| Name                       | Value                                                                |
| -------------------------- | -------------------------------------------------------------------- |
| `EXECUTION_PAYLOAD_GINDEX` | `get_generalized_index(BeaconBlockBody, 'execution_payload')` (= 25) |

## Containers

### Modified `LightClientHeader`

```python
class LightClientHeader(Container):
    beacon: BeaconBlockHeader
    # [New in Capella]
    execution: ExecutionPayloadHeader
    # [New in Capella]
    execution_branch: ExecutionBranch
```

### Modified `LightClientBootstrap`

```python
class LightClientBootstrap(Container):
    # [Modified in Capella]
    header: LightClientHeader
    current_sync_committee: SyncCommittee
    current_sync_committee_branch: CurrentSyncCommitteeBranch
```

### Modified `LightClientUpdate`

```python
class LightClientUpdate(Container):
    # [Modified in Capella]
    attested_header: LightClientHeader
    next_sync_committee: SyncCommittee
    next_sync_committee_branch: NextSyncCommitteeBranch
    # [Modified in Capella]
    finalized_header: LightClientHeader
    finality_branch: FinalityBranch
    sync_aggregate: SyncAggregate
    signature_slot: Slot
```

### Modified `LightClientFinalityUpdate`

```python
class LightClientFinalityUpdate(Container):
    # [Modified in Capella]
    attested_header: LightClientHeader
    # [Modified in Capella]
    finalized_header: LightClientHeader
    finality_branch: FinalityBranch
    sync_aggregate: SyncAggregate
    signature_slot: Slot
```

### Modified `LightClientOptimisticUpdate`

```python
class LightClientOptimisticUpdate(Container):
    # [Modified in Capella]
    attested_header: LightClientHeader
    sync_aggregate: SyncAggregate
    signature_slot: Slot
```

### Modified `LightClientStore`

```python
@dataclass
class LightClientStore(object):
    # [Modified in Capella]
    finalized_header: LightClientHeader
    current_sync_committee: SyncCommittee
    next_sync_committee: SyncCommittee
    # [Modified in Capella]
    best_valid_update: Optional[LightClientUpdate]
    # [Modified in Capella]
    optimistic_header: LightClientHeader
    previous_max_active_participants: uint64
    current_max_active_participants: uint64
```

## Helpers

### `get_lc_execution_root`

```python
def get_lc_execution_root(header: LightClientHeader) -> Root:
    epoch = compute_epoch_at_slot(header.beacon.slot)

    if epoch >= CAPELLA_FORK_EPOCH:
        return hash_tree_root(header.execution)

    return Root()
```

### Modified `is_valid_light_client_header`

```python
def is_valid_light_client_header(header: LightClientHeader) -> bool:
    epoch = compute_epoch_at_slot(header.beacon.slot)

    if epoch < CAPELLA_FORK_EPOCH:
        return (
            header.execution == ExecutionPayloadHeader()
            and header.execution_branch == ExecutionBranch()
        )

    return is_valid_merkle_branch(
        leaf=get_lc_execution_root(header),
        branch=header.execution_branch,
        depth=floorlog2(EXECUTION_PAYLOAD_GINDEX),
        index=get_subtree_index(EXECUTION_PAYLOAD_GINDEX),
        root=header.beacon.body_root,
    )
```
