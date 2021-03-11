# Ethereum 2.0 The Merge

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents
<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
  - [Helpers](#helpers)
    - [`get_eth1_data`](#get_eth1_data)
    - [`is_valid_eth1_data`](#is_valid_eth1_data)
  - [Updated fork-choice handlers](#updated-fork-choice-handlers)
    - [`on_block`](#on_block)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This is the modification of the fork choice according to the executable beacon chain proposal.

*Note*: It introduces the following change. `Eth1Data` included in a block must correspond to the application state produced by the parent block. This acts as an additional filter on the block subtree under consideration for the beacon block fork choice.

### Helpers

#### `get_eth1_data`

Let `get_eth1_data(state: BeaconState) -> Eth1Data` be the function that returns the `Eth1Data` obtained from the beacon state.

*Note*: This is mostly a function of the state of the beacon chain deposit contract. It can be read from the application state and/or logs. The `block_hash` value of `Eth1Data` must be set to `state.application_block_hash`.

#### `is_valid_eth1_data`

Used by fork-choice handler, `on_block`

```python
def is_valid_eth1_data(store: Store, block: BeaconBlock) -> boolean:
    parent_state = store.block_states[block.parent_root]
    expected_eth1_data = get_eth1_data(parent_state)
    actual_eth1_data = block.body.eth1_data
    
    is_correct_root = expected_eth1_data.deposit_root == actual_eth1_data.deposit_root
    is_correct_count = expected_eth1_data.deposit_count == actual_eth1_data.deposit_count
    is_correct_block_hash = expected_eth1_data.block_hash == actual_eth1_data.block_hash
    return is_correct_root and is_correct_count and is_correct_block_hash
```

### Updated fork-choice handlers

#### `on_block`

*Note*: The only modification is the addition of the `Eth1Data` validity assumption.

```python
def on_block(store: Store, signed_block: SignedBeaconBlock) -> None:
    block = signed_block.message
    # Parent block must be known
    assert block.parent_root in store.block_states
    # Make a copy of the state to avoid mutability issues
    pre_state = copy(store.block_states[block.parent_root])
    # Blocks cannot be in the future. If they are, their consideration must be delayed until the are in the past.
    assert get_current_slot(store) >= block.slot

    # Check that block is later than the finalized epoch slot (optimization to reduce calls to get_ancestor)
    finalized_slot = compute_start_slot_at_epoch(store.finalized_checkpoint.epoch)
    assert block.slot > finalized_slot
    # Check block is a descendant of the finalized block at the checkpoint finalized slot
    assert get_ancestor(store, block.parent_root, finalized_slot) == store.finalized_checkpoint.root
    
    # [Added] Check that Eth1 data is correct
    assert is_valid_eth1_data(store, block)

    # Check the block is valid and compute the post-state
    state = pre_state.copy()
    state_transition(state, signed_block, True)
    # Add new block to the store
    store.blocks[hash_tree_root(block)] = block
    # Add new state for this block to the store
    store.block_states[hash_tree_root(block)] = state

    # Update justified checkpoint
    if state.current_justified_checkpoint.epoch > store.justified_checkpoint.epoch:
        if state.current_justified_checkpoint.epoch > store.best_justified_checkpoint.epoch:
            store.best_justified_checkpoint = state.current_justified_checkpoint
        if should_update_justified_checkpoint(store, state.current_justified_checkpoint):
            store.justified_checkpoint = state.current_justified_checkpoint

    # Update finalized checkpoint
    if state.finalized_checkpoint.epoch > store.finalized_checkpoint.epoch:
        store.finalized_checkpoint = state.finalized_checkpoint
        
        # Potentially update justified if different from store
        if store.justified_checkpoint != state.current_justified_checkpoint:
            # Update justified if new justified is later than store justified
            if state.current_justified_checkpoint.epoch > store.justified_checkpoint.epoch:
                store.justified_checkpoint = state.current_justified_checkpoint
                return

            # Update justified if store justified is not in chain with finalized checkpoint
            finalized_slot = compute_start_slot_at_epoch(store.finalized_checkpoint.epoch)
            ancestor_at_finalized_slot = get_ancestor(store, store.justified_checkpoint.root, finalized_slot)
            if ancestor_at_finalized_slot != store.finalized_checkpoint.root:
                store.justified_checkpoint = state.current_justified_checkpoint
```

