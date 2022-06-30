<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [EIP-4844 -- Optimistic Sync](#eip-4844----optimistic-sync)
  - [Introduction](#introduction)
  - [Helpers](#helpers)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# EIP-4844 -- Optimistic Sync

## Introduction

This document is an extension of the [Optimistic Sync](/sync/optimistic.md) guide for EIP-4844.
All behaviors and definitions defined in Optimistic Sync guide carry over unless explicitly noted or overridden.

EIP-4844 extends the block validity requirement for [data availability](./validator.md#is_data_available). When a block transitions from `NOT_VALIDATED` -> `VALID`, its ancestors no longer unconditionally transition as well. But rather, only ancestors that do not have ancestors themselves with missing blocks can be considered `VALID`.

## Helpers

```python
def latest_valid_candidate_block(opt_store: OptimisticStore, block: BeaconBlock) -> BeaconBlock:
    # Assuming the input `block` is VALID
    chain = []
    while True:
        chain.append(block)
        if not is_optimistic(opt_store, block) or block.parent_root == Root():
            break
        block = opt_store.blocks[block.parent_root]
    b = next(b for b in reversed(chain)
            if not is_data_available(b.slot, hash_tree_root(b.body), b.body.blob_kzgs), None)
    return opt_store.blocks[b.parent_root] if b is not None else None
```

We define `latest_valid_candidate_block` as a function returning the most recent ancestor of a `VALID` block that can be transitioned from` NOT_VALIDATED` -> `VALID`. The ancestors of the block returned by the function can also be transitioned from `NOT_VALIDATED` to `VALID`.
