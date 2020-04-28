# Ethereum 2.0 Phase 1 -- Beacon Chain + Shard Chain Fork Choice

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Introduction](#introduction)
- [Fork choice](#fork-choice)
  - [Helpers](#helpers)
    - [Extended `Store`](#extended-store)
    - [Updated `get_forkchoice_store`](#updated-get_forkchoice_store)
    - [`get_shard_latest_attesting_balance`](#get_shard_latest_attesting_balance)
    - [`get_shard_head`](#get_shard_head)
    - [`get_shard_ancestor`](#get_shard_ancestor)
    - [`filter_shard_block_tree`](#filter_shard_block_tree)
    - [`get_filtered_block_tree`](#get_filtered_block_tree)
  - [Handlers](#handlers)
    - [`on_shard_block`](#on_shard_block)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

## Introduction

This document is the shard chain fork choice spec for part of Ethereum 2.0 Phase 1.

## Fork choice

### Helpers

#### Extended `Store`

```python
@dataclass
class Store(object):
    time: uint64
    genesis_time: uint64
    justified_checkpoint: Checkpoint
    finalized_checkpoint: Checkpoint
    best_justified_checkpoint: Checkpoint
    blocks: Dict[Root, BeaconBlock] = field(default_factory=dict)
    block_states: Dict[Root, BeaconState] = field(default_factory=dict)
    checkpoint_states: Dict[Checkpoint, BeaconState] = field(default_factory=dict)
    latest_messages: Dict[ValidatorIndex, LatestMessage] = field(default_factory=dict)
    # shard chain
    shard_init_slots: Dict[Shard, Slot] = field(default_factory=dict)
    shard_blocks: Dict[Shard, Dict[Root, ShardBlock]] = field(default_factory=dict)
    shard_block_states: Dict[Shard, Dict[Root, ShardState]] = field(default_factory=dict)
```

#### Updated `get_forkchoice_store`

```python
def get_forkchoice_store(anchor_state: BeaconState,
                         shard_init_slots: Dict[Shard, Slot],
                         anchor_state_shard_blocks: Dict[Shard, Dict[Root, ShardBlock]]) -> Store:
    shard_count = len(anchor_state.shard_states)
    anchor_block_header = anchor_state.latest_block_header.copy()
    if anchor_block_header.state_root == Bytes32():
        anchor_block_header.state_root = hash_tree_root(anchor_state)
    anchor_root = hash_tree_root(anchor_block_header)
    anchor_epoch = get_current_epoch(anchor_state)
    justified_checkpoint = Checkpoint(epoch=anchor_epoch, root=anchor_root)
    finalized_checkpoint = Checkpoint(epoch=anchor_epoch, root=anchor_root)
    return Store(
        time=anchor_state.genesis_time + SECONDS_PER_SLOT * anchor_state.slot,
        genesis_time=anchor_state.genesis_time,
        justified_checkpoint=justified_checkpoint,
        finalized_checkpoint=finalized_checkpoint,
        best_justified_checkpoint=justified_checkpoint,
        blocks={anchor_root: anchor_block_header},
        block_states={anchor_root: anchor_state.copy()},
        checkpoint_states={justified_checkpoint: anchor_state.copy()},
        # shard chain
        shard_init_slots=shard_init_slots,
        shard_blocks=anchor_state_shard_blocks,
        shard_block_states={
            shard: {
                anchor_state.shard_states[shard].latest_block_root: anchor_state.copy().shard_states[shard]
            }
            for shard in map(Shard, range(shard_count))
        },
    )
```

#### `get_shard_latest_attesting_balance`

```python
def get_shard_latest_attesting_balance(store: Store, shard: Shard, root: Root) -> Gwei:
    state = store.checkpoint_states[store.justified_checkpoint]
    active_indices = get_active_validator_indices(state, get_current_epoch(state))
    return Gwei(sum(
        state.validators[i].effective_balance for i in active_indices
        if (
            i in store.latest_messages and get_shard_ancestor(
                store, shard, store.latest_messages[i].root, store.shard_blocks[shard][root].slot
            ) == root
        )
    ))
```

#### `get_shard_head`

```python
def get_shard_head(store: Store, shard: Shard) -> Root:
    # Get filtered block tree that only includes viable branches
    blocks = get_filtered_shard_block_tree(store, shard)

    # Execute the LMD-GHOST fork choice
    head_beacon_root = get_head(store)
    head_shard_root = store.block_states[head_beacon_root].shard_states[shard].latest_block_root
    while True:
        children = [
            root for root in blocks.keys()
            if blocks[root].shard_parent_root == head_shard_root
        ]
        if len(children) == 0:
            return head_shard_root
        # Sort by latest attesting balance with ties broken lexicographically
        head_shard_root = max(children, key=lambda root: (get_shard_latest_attesting_balance(store, shard, root), root))
```

#### `get_shard_ancestor`

```python
def get_shard_ancestor(store: Store, shard: Shard, root: Root, slot: Slot) -> Root:
    block = store.shard_blocks[shard][root]
    if block.slot > slot:
        return get_shard_ancestor(store, shard, block.shard_parent_root, slot)
    elif block.slot == slot:
        return root
    else:
        # root is older than queried slot, thus a skip slot. Return earliest root prior to slot
        return root
```

#### `filter_shard_block_tree`

```python
def filter_shard_block_tree(store: Store, shard: Shard, block_root: Root, blocks: Dict[Root, ShardBlock]) -> bool:
    block = store.shard_blocks[shard][block_root]
    children = [
        root for root in store.shard_blocks[shard].keys()
        if (
            store.shard_blocks[shard][root].shard_parent_root == block_root
            and store.shard_blocks[shard][root].slot != store.shard_init_slots[shard]
        )
    ]

    if any(children):
        filter_block_tree_result = [filter_shard_block_tree(store, shard, child, blocks) for child in children]
        if any(filter_block_tree_result):
            blocks[block_root] = block
            return True
        return False

    return False
```

#### `get_filtered_block_tree`

```python
def get_filtered_shard_block_tree(store: Store, shard: Shard) -> Dict[Root, ShardBlock]:
    base_beacon_block_root = get_head(store)
    base_shard_block_root = store.block_states[base_beacon_block_root].shard_states[shard].latest_block_root
    blocks: Dict[Root, ShardBlock] = {}
    filter_shard_block_tree(store, shard, base_shard_block_root, blocks)
    return blocks
```

### Handlers

#### `on_shard_block`

```python
def on_shard_block(store: Store, shard: Shard, signed_shard_block: SignedShardBlock) -> None:
    shard_block = signed_shard_block.message

    # 1. Check shard parent exists
    assert shard_block.shard_parent_root in store.shard_block_states[shard]
    pre_shard_state = store.shard_block_states[shard][shard_block.shard_parent_root]

    # 2. Check beacon parent exists
    assert shard_block.beacon_parent_root in store.block_states
    beacon_state = store.block_states[shard_block.beacon_parent_root]

    # 3. Check that block is later than the finalized epoch slot (optimization to reduce calls to get_ancestor)
    finalized_slot = compute_start_slot_at_epoch(store.finalized_checkpoint.epoch)
    assert shard_block.slot > finalized_slot

    # 4. Check block is a descendant of the finalized block at the checkpoint finalized slot
    assert (
        shard_block.beacon_parent_root == store.finalized_checkpoint.root
        or get_ancestor(store, shard_block.beacon_parent_root, finalized_slot) == store.finalized_checkpoint.root
    )

    # Add new block to the store
    store.shard_blocks[shard][hash_tree_root(shard_block)] = shard_block

    # Check the block is valid and compute the post-state
    verify_shard_block_message(beacon_state, pre_shard_state, shard_block, shard_block.slot, shard)
    verify_shard_block_signature(beacon_state, signed_shard_block)
    post_state = get_post_shard_state(beacon_state, pre_shard_state, shard_block)
    # Add new state for this block to the store
    store.shard_block_states[shard][hash_tree_root(shard_block)] = post_state
```
