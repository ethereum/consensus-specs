# Capella Light Client -- Sync Protocol

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Custom types](#custom-types)
- [Constants](#constants)
- [Containers](#containers)
  - [Modified `LightClientHeader`](#modified-lightclientheader)
- [Helper functions](#helper-functions)
  - [`execution_payload_gindex_at_slot`](#execution_payload_gindex_at_slot)
  - [`get_lc_execution_root`](#get_lc_execution_root)
  - [Modified `is_valid_light_client_header`](#modified-is_valid_light_client_header)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This upgrade adds information about the execution payload to light client data as part of the Capella upgrade. It extends the [Altair Light Client specifications](../../altair/light-client/sync-protocol.md). The [fork document](./fork.md) explains how to upgrade existing Altair based deployments to Capella.

Additional documents describes the impact of the upgrade on certain roles:
- [Full node](./full-node.md)
- [Networking](./p2p-interface.md)

## Custom types

| Name | SSZ equivalent | Description |
| - | - | - |
| `ExecutionBranch` | `Vector[Bytes32, floorlog2(EXECUTION_PAYLOAD_GINDEX)]` | Merkle branch of `execution_payload` within `BeaconBlockBody` |

## Constants

| Name | Value |
| - | - |
| `EXECUTION_PAYLOAD_GINDEX` | `get_generalized_index(BeaconBlockBody, 'execution_payload')` (= 25) |

## Containers

### Modified `LightClientHeader`

```python
class LightClientHeader(Container):
    # Beacon block header
    beacon: BeaconBlockHeader
    # Execution payload header corresponding to `beacon.body_root` (from Capella onward)
    execution: ExecutionPayloadHeader
    execution_branch: ExecutionBranch
```

## Helper functions

### `execution_payload_gindex_at_slot`

```python
def execution_payload_gindex_at_slot(slot: Slot) -> GeneralizedIndex:
    epoch = compute_epoch_at_slot(slot)
    assert epoch >= CAPELLA_FORK_EPOCH

    return EXECUTION_PAYLOAD_GINDEX
```

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

    return is_valid_normalized_merkle_branch(
        leaf=get_lc_execution_root(header),
        branch=header.execution_branch,
        gindex=execution_payload_gindex_at_slot(header.beacon.slot),
        root=header.beacon.body_root,
    )
```
