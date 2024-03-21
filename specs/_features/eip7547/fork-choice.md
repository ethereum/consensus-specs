# EIP-7547 -- Fork Choice

## Table of contents
<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Helpers](#helpers)
  - [New `is_inclusion_list_available`](#new-is_inclusion_list_available)
  - [Modified `filter_block_tree`](#modified-filter_block_tree)
- [New fork-choice handlers](#new-fork-choice-handlers)
  - [New `on_inclusion_list`](#new-on_inclusion_list)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This is the modification of the fork choice accompanying EIP-7547.

## Helpers

### New `is_inclusion_list_available`

```python
def is_inclusion_list_available(block_root: Root) -> bool:
    """
    Return ``True`` if and only if the payload has a corresponding inclusion list.
    """
    ...
```

### Modified `filter_block_tree`

Add filter for if the inclusion list is available.

```python
def filter_block_tree(store: Store, block_root: Root, blocks: Dict[Root, BeaconBlock]) -> bool:
    block = store.blocks[block_root]
    # [Modified in EIP-7547] Check that IL is available when considering heads.
    children = [
        root for (root, block) in blocks.items()
        if block.parent_root == block_root
        and is_inclusion_list_available(root)
    ]

    # If any children branches contain expected finalized/justified checkpoints,
    # add to filtered block-tree and signal viability to parent.
    if any(children):
        filter_block_tree_result = [filter_block_tree(store, child, blocks) for child in children]
        if any(filter_block_tree_result):
            blocks[block_root] = block
            return True
        return False

    current_epoch = get_current_store_epoch(store)
    voting_source = get_voting_source(store, block_root)

    # The voting source should be either at the same height as the store's justified checkpoint or
    # not more than two epochs ago
    correct_justified = (
        store.justified_checkpoint.epoch == GENESIS_EPOCH
        or voting_source.epoch == store.justified_checkpoint.epoch
        or voting_source.epoch + 2 >= current_epoch
    )

    finalized_checkpoint_block = get_checkpoint_block(
        store,
        block_root,
        store.finalized_checkpoint.epoch,
    )

    correct_finalized = (
        store.finalized_checkpoint.epoch == GENESIS_EPOCH
        or store.finalized_checkpoint.root == finalized_checkpoint_block
    )

    # If expected finalized/justified, add to viable block-tree and signal viability to parent.
    if correct_justified and correct_finalized:
        blocks[block_root] = block
        return True

    # Otherwise, branch not viable
    return False
```

## New fork-choice handlers

### New `on_inclusion_list`

A new handler to be called when a new inclusion list is received.

```python
def on_inclusion_list(self: ExecutionEngine, store: Store, inclusion_list: InclusionList) -> None:
    """
    Run ``on_inclusion_list`` upon receiving a new inclusion lit.
    """

    # [New in EIP-7547] Check if the inclusion list is valid.
    state = pre_state.copy()
    assert self.verify_and_notify_new_inclusion_list(inclusion_list)

    # Add IL availability to the store.
    summary = inclusion_list.signedSummary.message
    store.inclusion_list_available[(summary.slot, summary.parent_hash)] = True
```