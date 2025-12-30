# Gloas Light Client -- Sync Protocol

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Constants](#constants)
  - [Frozen constants](#frozen-constants)
- [Note](#note)

<!-- mdformat-toc end -->

## Introduction

This upgrade updates light client data to include the Gloas changes to the
generalized indices of [`BeaconState`](../beacon-chain.md).

## Constants

### Frozen constants

Existing `GeneralizedIndex` constants are frozen at their
[Electra](../../electra/light-client/sync-protocol.md#constants) values.

| Name                                    | Value                                                                                |
| --------------------------------------- | ------------------------------------------------------------------------------------ |
| `FINALIZED_ROOT_GINDEX_ELECTRA`         | `get_generalized_index(electra.BeaconState, 'finalized_checkpoint', 'root')` (= 169) |
| `CURRENT_SYNC_COMMITTEE_GINDEX_ELECTRA` | `get_generalized_index(electra.BeaconState, 'current_sync_committee')` (= 86)        |
| `NEXT_SYNC_COMMITTEE_GINDEX_ELECTRA`    | `get_generalized_index(electra.BeaconState, 'next_sync_committee')` (= 87)           |

## Note

The light client specs for Gloas are currently incomplete.
