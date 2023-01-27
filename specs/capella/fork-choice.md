# Capella -- Fork Choice

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents
<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Custom types](#custom-types)
- [Protocols](#protocols)
  - [`ExecutionEngine`](#executionengine)
    - [`notify_forkchoice_updated`](#notify_forkchoice_updated)
- [Helpers](#helpers)
  - [Extended `PayloadAttributes`](#extended-payloadattributes)
- [Updated fork-choice handlers](#updated-fork-choice-handlers)
  - [`on_block`](#on_block)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This is the modification of the fork choice according to the Capella upgrade.

Unless stated explicitly, all prior functionality from [Bellatrix](../bellatrix/fork-choice.md) is inherited.

## Custom types

## Protocols

### `ExecutionEngine`

*Note*: The `notify_forkchoice_updated` function is modified in the `ExecutionEngine` protocol at the Capella upgrade.

#### `notify_forkchoice_updated`

The only change made is to the `PayloadAttributes` container through the addition of `withdrawals`.
Otherwise, `notify_forkchoice_updated` inherits all prior functionality.

```python
def notify_forkchoice_updated(self: ExecutionEngine,
                              head_block_hash: Hash32,
                              safe_block_hash: Hash32,
                              finalized_block_hash: Hash32,
                              payload_attributes: Optional[PayloadAttributes]) -> Optional[PayloadId]:
    ...
```

## Helpers

### Extended `PayloadAttributes`

`PayloadAttributes` is extended with the `withdrawals` field.

```python
@dataclass
class PayloadAttributes(object):
    timestamp: uint64
    prev_randao: Bytes32
    suggested_fee_recipient: ExecutionAddress
    withdrawals: Sequence[Withdrawal]  # [New in Capella]
```

## Updated fork-choice handlers

### `on_block`

*Note*: The only modification is the deletion of the verification of merge transition block conditions.

```python
def on_block(store: Store, signed_block: SignedBeaconBlock) -> None:
    """
    Run ``on_block`` upon receiving a new block.
    """
    block = signed_block.message
    # Parent block must be known
    assert block.parent_root in store.block_states
    # Make a copy of the state to avoid mutability issues
    pre_state = copy(store.block_states[block.parent_root])
    # Blocks cannot be in the future. If they are, their consideration must be delayed until they are in the past.
    assert get_current_slot(store) >= block.slot

    # Check that block is later than the finalized epoch slot (optimization to reduce calls to get_ancestor)
    finalized_slot = compute_start_slot_at_epoch(store.finalized_checkpoint.epoch)
    assert block.slot > finalized_slot
    # Check block is a descendant of the finalized block at the checkpoint finalized slot
    assert get_ancestor(store, block.parent_root, finalized_slot) == store.finalized_checkpoint.root

    # Check the block is valid and compute the post-state
    state = pre_state.copy()
    state_transition(state, signed_block, True)

    # Add new block to the store
    store.blocks[hash_tree_root(block)] = block
    # Add new state for this block to the store
    store.block_states[hash_tree_root(block)] = state

    # Add proposer score boost if the block is timely
    time_into_slot = (store.time - store.genesis_time) % SECONDS_PER_SLOT
    is_before_attesting_interval = time_into_slot < SECONDS_PER_SLOT // INTERVALS_PER_SLOT
    if get_current_slot(store) == block.slot and is_before_attesting_interval:
        store.proposer_boost_root = hash_tree_root(block)

    # Update justified checkpoint
    if state.current_justified_checkpoint.epoch > store.justified_checkpoint.epoch:
        if state.current_justified_checkpoint.epoch > store.best_justified_checkpoint.epoch:
            store.best_justified_checkpoint = state.current_justified_checkpoint
        if should_update_justified_checkpoint(store, state.current_justified_checkpoint):
            store.justified_checkpoint = state.current_justified_checkpoint

    # Update finalized checkpoint
    if state.finalized_checkpoint.epoch > store.finalized_checkpoint.epoch:
        store.finalized_checkpoint = state.finalized_checkpoint
        store.justified_checkpoint = state.current_justified_checkpoint
```
