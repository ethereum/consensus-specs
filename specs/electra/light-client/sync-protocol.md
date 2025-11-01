# Electra Light Client -- Sync Protocol

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Custom types](#custom-types)
- [Constants](#constants)
  - [Frozen constants](#frozen-constants)
  - [New constants](#new-constants)
- [Helper functions](#helper-functions)
  - [Modified `finalized_root_gindex_at_slot`](#modified-finalized_root_gindex_at_slot)
  - [Modified `current_sync_committee_gindex_at_slot`](#modified-current_sync_committee_gindex_at_slot)
  - [Modified `next_sync_committee_gindex_at_slot`](#modified-next_sync_committee_gindex_at_slot)

<!-- mdformat-toc end -->

## Introduction

This upgrade updates light client data to include the Electra changes to the
generalized indices of [`BeaconState`](../beacon-chain.md). It extends the
[Deneb Light Client specifications](../../deneb/light-client/sync-protocol.md).
The [fork document](./fork.md) explains how to upgrade existing Deneb based
deployments to Electra.

Additional documents describes the impact of the upgrade on certain roles:

- [Networking](./p2p-interface.md)

## Custom types

| Name                         | SSZ equivalent                                                      | Description                                                       |
| ---------------------------- | ------------------------------------------------------------------- | ----------------------------------------------------------------- |
| `FinalityBranch`             | `Vector[Bytes32, floorlog2(FINALIZED_ROOT_GINDEX_ELECTRA)]`         | Merkle branch of `finalized_checkpoint.root` within `BeaconState` |
| `CurrentSyncCommitteeBranch` | `Vector[Bytes32, floorlog2(CURRENT_SYNC_COMMITTEE_GINDEX_ELECTRA)]` | Merkle branch of `current_sync_committee` within `BeaconState`    |
| `NextSyncCommitteeBranch`    | `Vector[Bytes32, floorlog2(NEXT_SYNC_COMMITTEE_GINDEX_ELECTRA)]`    | Merkle branch of `next_sync_committee` within `BeaconState`       |

## Constants

### Frozen constants

Existing `GeneralizedIndex` constants are frozen at their
[Altair](../../altair/light-client/sync-protocol.md#constants) values.

| Name                            | Value                                                                               |
| ------------------------------- | ----------------------------------------------------------------------------------- |
| `FINALIZED_ROOT_GINDEX`         | `get_generalized_index(altair.BeaconState, 'finalized_checkpoint', 'root')` (= 105) |
| `CURRENT_SYNC_COMMITTEE_GINDEX` | `get_generalized_index(altair.BeaconState, 'current_sync_committee')` (= 54)        |
| `NEXT_SYNC_COMMITTEE_GINDEX`    | `get_generalized_index(altair.BeaconState, 'next_sync_committee')` (= 55)           |

### New constants

| Name                                    | Value                                                                        |
| --------------------------------------- | ---------------------------------------------------------------------------- |
| `FINALIZED_ROOT_GINDEX_ELECTRA`         | `get_generalized_index(BeaconState, 'finalized_checkpoint', 'root')` (= 169) |
| `CURRENT_SYNC_COMMITTEE_GINDEX_ELECTRA` | `get_generalized_index(BeaconState, 'current_sync_committee')` (= 86)        |
| `NEXT_SYNC_COMMITTEE_GINDEX_ELECTRA`    | `get_generalized_index(BeaconState, 'next_sync_committee')` (= 87)           |

## Helper functions

### Modified `finalized_root_gindex_at_slot`

```python
def finalized_root_gindex_at_slot(slot: Slot) -> GeneralizedIndex:
    epoch = compute_epoch_at_slot(slot)

    # [Modified in Electra]
    if epoch >= ELECTRA_FORK_EPOCH:
        return FINALIZED_ROOT_GINDEX_ELECTRA
    return FINALIZED_ROOT_GINDEX
```

### Modified `current_sync_committee_gindex_at_slot`

```python
def current_sync_committee_gindex_at_slot(slot: Slot) -> GeneralizedIndex:
    epoch = compute_epoch_at_slot(slot)

    # [Modified in Electra]
    if epoch >= ELECTRA_FORK_EPOCH:
        return CURRENT_SYNC_COMMITTEE_GINDEX_ELECTRA
    return CURRENT_SYNC_COMMITTEE_GINDEX
```

### Modified `next_sync_committee_gindex_at_slot`

```python
def next_sync_committee_gindex_at_slot(slot: Slot) -> GeneralizedIndex:
    epoch = compute_epoch_at_slot(slot)

    # [Modified in Electra]
    if epoch >= ELECTRA_FORK_EPOCH:
        return NEXT_SYNC_COMMITTEE_GINDEX_ELECTRA
    return NEXT_SYNC_COMMITTEE_GINDEX
```
