# Decoupled Consensus Light Client -- Sync Protocol

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Types](#types)
  - [Modified `FinalityBranch`](#modified-finalitybranch)
- [Constants](#constants)
  - [Frozen constants](#frozen-constants)
  - [New constants](#new-constants)
- [Helpers](#helpers)
  - [Modified `finalized_root_gindex_at_slot`](#modified-finalized_root_gindex_at_slot)

<!-- mdformat-toc end -->

## Introduction

This upgrade moves `finalized_checkpoint` to a new position in
[`BeaconState`](../beacon-chain.md), which changes the depth of its proof. It
extends the
[Gloas Light Client specifications](../../../gloas/light-client/sync-protocol.md).

## Types

### Modified `FinalityBranch`

```python
class FinalityBranch(Vector[Bytes32]):
    """
    A Merkle branch proving ``finalized_checkpoint.root`` within
    ``BeaconState``.
    """

    LENGTH = floorlog2(FINALIZED_ROOT_GINDEX_DC)
```

## Constants

### Frozen constants

Existing `GeneralizedIndex` constants are frozen at their pre-DC values.

| Name                          | Value                                                                             |
| ----------------------------- | --------------------------------------------------------------------------------- |
| `FINALIZED_ROOT_GINDEX_GLOAS` | `get_generalized_index(heze.BeaconState, "finalized_checkpoint", "root")` (= 735) |

### New constants

| Name                       | Value                                                                          |
| -------------------------- | ------------------------------------------------------------------------------ |
| `FINALIZED_ROOT_GINDEX_DC` | `get_generalized_index(BeaconState, "finalized_checkpoint", "root")` (= 5,943) |

## Helpers

### Modified `finalized_root_gindex_at_slot`

```python
def finalized_root_gindex_at_slot(slot: Slot) -> GeneralizedIndex:
    epoch = compute_epoch_at_slot(slot)

    # [New in DC]
    if epoch >= DC_FORK_EPOCH:
        return FINALIZED_ROOT_GINDEX_DC
    if epoch >= GLOAS_FORK_EPOCH:
        return FINALIZED_ROOT_GINDEX_GLOAS
    if epoch >= ELECTRA_FORK_EPOCH:
        return FINALIZED_ROOT_GINDEX_ELECTRA
    return FINALIZED_ROOT_GINDEX
```
