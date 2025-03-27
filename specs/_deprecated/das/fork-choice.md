# Data Availability Sampling -- Fork Choice

*Note*: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Dependency calculation](#dependency-calculation)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This document is the beacon chain fork choice spec for Data Availability Sampling. The only change that we add from phase 0 is that we add a concept of "data dependencies";
a block is only eligible for consideration in the fork choice after a data availability test has been successfully completed for all dependencies.
The "root" of a shard block for data dependency purposes is considered to be a `DataCommitment` object, which is a pair of a Kate commitment and a length.

## Dependency calculation

```python
def get_new_dependencies(state: BeaconState) -> Set[DataCommitment]:
    return set(
        # Already confirmed during this epoch
        [c.commitment for c in state.current_epoch_pending_headers if c.confirmed] +
        # Already confirmed during previous epoch
        [c.commitment for c in state.previous_epoch_pending_headers if c.confirmed] +
        # Confirmed in the epoch before the previous
        [c for c in shard for shard in state.grandparent_epoch_confirmed_commitments if c != DataCommitment()]
    )
```

```python
def get_all_dependencies(store: Store, block: BeaconBlock) -> Set[DataCommitment]:
    if compute_epoch_at_slot(block.slot) < SHARDING_FORK_EPOCH:
        return set()
    else:
        latest = get_new_dependencies(store.block_states[hash_tree_root(block)])
        older = get_all_dependencies(store, store.blocks[block.parent_root])
        return latest.union(older)
```
