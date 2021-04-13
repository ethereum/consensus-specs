# Ethereum 2.0 The Merge

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents
<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
  - [Helpers](#helpers)
    - [`PowBlock`](#powblock)
    - [`get_pow_block`](#get_pow_block)
    - [`is_valid_transition_block`](#is_valid_transition_block)
  - [Updated fork-choice handlers](#updated-fork-choice-handlers)
    - [`on_block`](#on_block)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This is the modification of the fork choice according to the executable beacon chain proposal.

*Note*: It introduces the process of transition from the last PoW block to the first PoS block.

### Helpers

#### `PowBlock`

```python
class PowBlock(Container):
    block_hash: Hash32
    is_processed: boolean
    is_valid: boolean
    total_difficulty: uint256
```

#### `get_pow_block`

Let `get_pow_block(block_hash: Hash32) -> PowBlock` be the function that given the hash of the PoW block returns its data.

*Note*: The `eth_getBlockByHash` JSON-RPC method does not distinguish invalid blocks from blocks that haven't been processed yet. Either extending this existing method or implementing a new one is required.

#### `is_valid_transition_block`

Used by fork-choice handler, `on_block`.

```python
def is_valid_transition_block(block: PowBlock) -> boolean:
    is_total_difficulty_reached = block.total_difficulty >= TRANSITION_TOTAL_DIFFICULTY
    return block.is_valid and is_total_difficulty_reached
```

### Updated fork-choice handlers

#### `on_block`

*Note*: The only modification is the addition of the verification of transition block conditions.

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
    
    # [New in Merge]
    if is_transition_block(pre_state, block.body):
        # Delay consideration of block until PoW block is processed by the PoW node
        pow_block = get_pow_block(block.body.execution_payload.parent_hash)
        assert pow_block.is_processed
        assert is_valid_transition_block(pow_block)

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
