# Ethereum 2.0 Phase 1 -- Beacon Chain + Shard Chain Fork Choice

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->


- [Introduction](#introduction)
- [Fork choice](#fork-choice)
  - [Helpers](#helpers)
    - [`get_forkchoice_shard_store`](#get_forkchoice_shard_store)
    - [`get_shard_latest_attesting_balance`](#get_shard_latest_attesting_balance)
    - [`get_shard_head`](#get_shard_head)
    - [`get_shard_ancestor`](#get_shard_ancestor)
    - [`get_pending_shard_blocks`](#get_pending_shard_blocks)
  - [Handlers](#handlers)
    - [`on_shard_block`](#on_shard_block)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

## Introduction

This document is the shard chain fork choice spec for part of Ethereum 2.0 Phase 1. It assumes the [beacon chain fork choice spec](./fork-choice.md).

## Fork choice

### Helpers

#### `get_forkchoice_shard_store`

```python
def get_forkchoice_shard_store(anchor_state: BeaconState, shard: Shard) -> ShardStore:
    return ShardStore(
        shard=shard,
        signed_blocks={
            anchor_state.shard_states[shard].latest_block_root: SignedShardBlock(
                message=ShardBlock(slot=anchor_state.slot, shard=shard)
            )
        },
        block_states={anchor_state.shard_states[shard].latest_block_root: anchor_state.copy().shard_states[shard]},
    )
```

#### `get_shard_latest_attesting_balance`

```python
def get_shard_latest_attesting_balance(store: Store, shard_store: ShardStore, root: Root) -> Gwei:
    state = store.checkpoint_states[store.justified_checkpoint]
    active_indices = get_active_validator_indices(state, get_current_epoch(state))
    return Gwei(sum(
        state.validators[i].effective_balance for i in active_indices
        if (
            i in shard_store.latest_messages
            # TODO: check the latest message logic: currently, validator's previous vote of another shard
            # would be ignored once their newer vote is accepted. Check if it makes sense.
            and get_shard_ancestor(
                store,
                shard_store,
                shard_store.latest_messages[i].root,
                shard_store.signed_blocks[root].message.slot,
            ) == root
        )
    ))
```

#### `get_shard_head`

```python
def get_shard_head(store: Store, shard_store: ShardStore) -> Root:
    # Execute the LMD-GHOST fork choice
    beacon_head_root = get_head(store)
    shard_head_state = store.block_states[beacon_head_root].shard_states[shard_store.shard]
    shard_head_root = shard_head_state.latest_block_root
    shard_blocks = {
        root: signed_shard_block.message for root, signed_shard_block in shard_store.signed_blocks.items()
        if signed_shard_block.message.slot > shard_head_state.slot
    }
    while True:
        # Find the valid child block roots
        children = [
            root for root, shard_block in shard_blocks.items()
            if shard_block.shard_parent_root == shard_head_root
        ]
        if len(children) == 0:
            return shard_head_root
        # Sort by latest attesting balance with ties broken lexicographically
        shard_head_root = max(
            children, key=lambda root: (get_shard_latest_attesting_balance(store, shard_store, root), root)
        )
```

#### `get_shard_ancestor`

```python
def get_shard_ancestor(store: Store, shard_store: ShardStore, root: Root, slot: Slot) -> Root:
    block = shard_store.signed_blocks[root].message
    if block.slot > slot:
        return get_shard_ancestor(store, shard_store, block.shard_parent_root, slot)
    elif block.slot == slot:
        return root
    else:
        # root is older than queried slot, thus a skip slot. Return most recent root prior to slot
        return root
```

#### `get_pending_shard_blocks`

```python
def get_pending_shard_blocks(store: Store, shard_store: ShardStore) -> Sequence[SignedShardBlock]:
    """
    Return the canonical shard block branch that has not yet been crosslinked.
    """
    shard = shard_store.shard

    beacon_head_root = get_head(store)
    beacon_head_state = store.block_states[beacon_head_root]
    latest_shard_block_root = beacon_head_state.shard_states[shard].latest_block_root

    shard_head_root = get_shard_head(store, shard_store)
    root = shard_head_root
    signed_shard_blocks = []
    while root != latest_shard_block_root:
        signed_shard_block = shard_store.signed_blocks[root]
        signed_shard_blocks.append(signed_shard_block)
        root = signed_shard_block.message.shard_parent_root

    signed_shard_blocks.reverse()
    return signed_shard_blocks
```

### Handlers

#### `on_shard_block`

```python
def on_shard_block(store: Store, shard_store: ShardStore, signed_shard_block: SignedShardBlock) -> None:
    shard_block = signed_shard_block.message
    shard = shard_store.shard

    # Check shard
    # TODO: check it in networking spec
    assert shard_block.shard == shard

    # Check shard parent exists
    assert shard_block.shard_parent_root in shard_store.block_states
    shard_parent_state = shard_store.block_states[shard_block.shard_parent_root]

    # Check beacon parent exists
    assert shard_block.beacon_parent_root in store.block_states
    beacon_parent_state = store.block_states[shard_block.beacon_parent_root]

    # Check that block is later than the finalized shard state slot (optimization to reduce calls to get_ancestor)
    finalized_beacon_state = store.block_states[store.finalized_checkpoint.root]
    finalized_shard_state = finalized_beacon_state.shard_states[shard]
    assert shard_block.slot > finalized_shard_state.slot

    # Check block is a descendant of the finalized block at the checkpoint finalized slot
    finalized_slot = compute_start_slot_at_epoch(store.finalized_checkpoint.epoch)
    assert (
        get_ancestor(store, shard_block.beacon_parent_root, finalized_slot) == store.finalized_checkpoint.root
    )

    # Check the block is valid and compute the post-state
    shard_state = shard_parent_state.copy()
    shard_state_transition(shard_state, signed_shard_block, beacon_parent_state, validate_result=True)

    # Add new block to the store
    # Note: storing `SignedShardBlock` format for computing `ShardTransition.proposer_signature_aggregate` 
    shard_store.signed_blocks[hash_tree_root(shard_block)] = signed_shard_block

    # Add new state for this block to the store
    shard_store.block_states[hash_tree_root(shard_block)] = shard_state
```
