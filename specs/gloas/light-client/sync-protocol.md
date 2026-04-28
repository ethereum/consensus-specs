# Gloas Light Client -- Sync Protocol

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Types](#types)
- [Constants](#constants)
  - [Frozen constants](#frozen-constants)
  - [New constants](#new-constants)
- [Containers](#containers)
  - [Modified `LightClientHeader`](#modified-lightclientheader)
- [Helpers](#helpers)
  - [Modified `finalized_root_gindex_at_slot`](#modified-finalized_root_gindex_at_slot)
  - [Modified `current_sync_committee_gindex_at_slot`](#modified-current_sync_committee_gindex_at_slot)
  - [Modified `next_sync_committee_gindex_at_slot`](#modified-next_sync_committee_gindex_at_slot)
  - [Modified `get_lc_execution_root`](#modified-get_lc_execution_root)
  - [Modified `is_valid_light_client_header`](#modified-is_valid_light_client_header)

<!-- mdformat-toc end -->

## Introduction

This upgrade extends light client data to reflect the Gloas changes in how
execution data is tracked in [`BeaconBlockBody`](../beacon-chain.md). It extends
the
[Electra Light Client specifications](../../electra/light-client/sync-protocol.md).
The [fork document](./fork.md) explains how to upgrade existing Electra based
deployments to Gloas.

Additional documents describes the impact of the upgrade on certain roles:

- [Full node](./full-node.md)
- [Networking](./p2p-interface.md)

## Types

| Name                         | SSZ equivalent                                                    | Description                                                                                                                                       |
| ---------------------------- | ----------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| `FinalityBranch`             | `Vector[Bytes32, floorlog2(FINALIZED_ROOT_GINDEX_GLOAS)]`         | Merkle branch of `finalized_checkpoint.root` within `BeaconState`                                                                                 |
| `CurrentSyncCommitteeBranch` | `Vector[Bytes32, floorlog2(CURRENT_SYNC_COMMITTEE_GINDEX_GLOAS)]` | Merkle branch of `current_sync_committee` within `BeaconState`                                                                                    |
| `NextSyncCommitteeBranch`    | `Vector[Bytes32, floorlog2(NEXT_SYNC_COMMITTEE_GINDEX_GLOAS)]`    | Merkle branch of `next_sync_committee` within `BeaconState`                                                                                       |
| `ExecutionBranch`            | `Vector[Bytes32, floorlog2(EXECUTION_BLOCK_HASH_GINDEX_GLOAS)]`   | Merkle branch of `signed_execution_payload_bid.message.parent_block_hash` (post-Gloas) or `execution_payload.block_hash` within `BeaconBlockBody` |

## Constants

### Frozen constants

Existing `GeneralizedIndex` constants are frozen at their pre-Gloas values.

| Name                                    | Value                                                                                |
| --------------------------------------- | ------------------------------------------------------------------------------------ |
| `FINALIZED_ROOT_GINDEX_ELECTRA`         | `get_generalized_index(electra.BeaconState, 'finalized_checkpoint', 'root')` (= 169) |
| `CURRENT_SYNC_COMMITTEE_GINDEX_ELECTRA` | `get_generalized_index(electra.BeaconState, 'current_sync_committee')` (= 86)        |
| `NEXT_SYNC_COMMITTEE_GINDEX_ELECTRA`    | `get_generalized_index(electra.BeaconState, 'next_sync_committee')` (= 87)           |
| `EXECUTION_PAYLOAD_GINDEX`              | `get_generalized_index(capella.BeaconBlockBody, 'execution_payload')` (= 25)         |

### New constants

| Name                                  | Value                                                                                                               |
| ------------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| `FINALIZED_ROOT_GINDEX_GLOAS`         | `get_generalized_index(BeaconState, 'finalized_checkpoint', 'root')` (= 735)                                        |
| `CURRENT_SYNC_COMMITTEE_GINDEX_GLOAS` | `get_generalized_index(BeaconState, 'current_sync_committee')` (= 2,945)                                            |
| `NEXT_SYNC_COMMITTEE_GINDEX_GLOAS`    | `get_generalized_index(BeaconState, 'next_sync_committee')` (= 2,946)                                               |
| `EXECUTION_BLOCK_HASH_GINDEX`         | `get_generalized_index(capella.BeaconBlockBody, 'execution_payload', 'block_hash')` (= 412)                         |
| `EXECUTION_BLOCK_HASH_GINDEX_DENEB`   | `get_generalized_index(deneb.BeaconBlockBody, 'execution_payload', 'block_hash')` (= 812)                           |
| `EXECUTION_BLOCK_HASH_GINDEX_GLOAS`   | `get_generalized_index(BeaconBlockBody, 'signed_execution_payload_bid', 'message', 'parent_block_hash')` (= 11,424) |

## Containers

### Modified `LightClientHeader`

```python
class LightClientHeader(Container):
    beacon: BeaconBlockHeader
    # [Modified in Gloas:EIP7732]
    # Removed `execution`
    # [New in Gloas:EIP7732]
    execution_block_hash: Hash32
    # [Modified in Gloas:EIP7732]
    execution_branch: ExecutionBranch
```

## Helpers

### Modified `finalized_root_gindex_at_slot`

```python
def finalized_root_gindex_at_slot(slot: Slot) -> GeneralizedIndex:
    epoch = compute_epoch_at_slot(slot)

    # [Modified in Gloas:EIP7688]
    if epoch >= GLOAS_FORK_EPOCH:
        return FINALIZED_ROOT_GINDEX_GLOAS
    if epoch >= ELECTRA_FORK_EPOCH:
        return FINALIZED_ROOT_GINDEX_ELECTRA
    return FINALIZED_ROOT_GINDEX
```

### Modified `current_sync_committee_gindex_at_slot`

```python
def current_sync_committee_gindex_at_slot(slot: Slot) -> GeneralizedIndex:
    epoch = compute_epoch_at_slot(slot)

    # [Modified in Gloas:EIP7688]
    if epoch >= GLOAS_FORK_EPOCH:
        return CURRENT_SYNC_COMMITTEE_GINDEX_GLOAS
    if epoch >= ELECTRA_FORK_EPOCH:
        return CURRENT_SYNC_COMMITTEE_GINDEX_ELECTRA
    return CURRENT_SYNC_COMMITTEE_GINDEX
```

### Modified `next_sync_committee_gindex_at_slot`

```python
def next_sync_committee_gindex_at_slot(slot: Slot) -> GeneralizedIndex:
    epoch = compute_epoch_at_slot(slot)

    # [Modified in Gloas:EIP7688]
    if epoch >= GLOAS_FORK_EPOCH:
        return NEXT_SYNC_COMMITTEE_GINDEX_GLOAS
    if epoch >= ELECTRA_FORK_EPOCH:
        return NEXT_SYNC_COMMITTEE_GINDEX_ELECTRA
    return NEXT_SYNC_COMMITTEE_GINDEX
```

### Modified `get_lc_execution_root`

```python
def get_lc_execution_root(header: LightClientHeader) -> Root:
    epoch = compute_epoch_at_slot(header.beacon.slot)

    # [New in Gloas:EIP7732]
    if epoch >= GLOAS_FORK_EPOCH:
        return Root(header.execution_block_hash)

    # [Modified in Gloas:EIP7732]
    if epoch >= DENEB_FORK_EPOCH:
        if header.beacon.slot == GENESIS_SLOT:
            return hash_tree_root(deneb.ExecutionPayloadHeader())
        BLOCK_HASH_GINDEX = get_generalized_index(deneb.ExecutionPayloadHeader, "block_hash")
    elif epoch >= CAPELLA_FORK_EPOCH:
        if header.beacon.slot == GENESIS_SLOT:
            return hash_tree_root(capella.ExecutionPayloadHeader())
        BLOCK_HASH_GINDEX = get_generalized_index(capella.ExecutionPayloadHeader, "block_hash")
    else:
        return Root()

    # [Modified in Gloas:EIP7732]
    inner = header.execution_branch[
        : len(header.execution_branch) - floorlog2(EXECUTION_PAYLOAD_GINDEX)
    ]
    return compute_merkle_branch_root(
        leaf=Bytes32(header.execution_block_hash),
        branch=inner[len(inner) - floorlog2(BLOCK_HASH_GINDEX) :],
        depth=floorlog2(BLOCK_HASH_GINDEX),
        index=get_subtree_index(BLOCK_HASH_GINDEX),
    )
```

### Modified `is_valid_light_client_header`

```python
def is_valid_light_client_header(header: LightClientHeader) -> bool:
    epoch = compute_epoch_at_slot(header.beacon.slot)

    # [New in Gloas:EIP7732]
    if epoch >= GLOAS_FORK_EPOCH:
        return is_valid_normalized_merkle_branch(
            leaf=Bytes32(header.execution_block_hash),
            branch=header.execution_branch,
            gindex=EXECUTION_BLOCK_HASH_GINDEX_GLOAS,
            root=header.beacon.body_root,
        )

    # [Modified in Gloas:EIP7732]
    if epoch >= DENEB_FORK_EPOCH:
        return is_valid_normalized_merkle_branch(
            leaf=Bytes32(header.execution_block_hash),
            branch=header.execution_branch,
            gindex=EXECUTION_BLOCK_HASH_GINDEX_DENEB,
            root=header.beacon.body_root,
        )

    # [Modified in Gloas:EIP7732]
    if epoch >= CAPELLA_FORK_EPOCH:
        return is_valid_normalized_merkle_branch(
            leaf=Bytes32(header.execution_block_hash),
            branch=header.execution_branch,
            gindex=EXECUTION_BLOCK_HASH_GINDEX,
            root=header.beacon.body_root,
        )

    # [Modified in Gloas:EIP7732]
    return header.execution_block_hash == Hash32() and header.execution_branch == ExecutionBranch()
```
