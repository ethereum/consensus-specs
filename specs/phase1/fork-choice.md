# Ethereum 2.0 Phase 1 -- Beacon Chain Fork Choice

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents
<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->


- [Introduction](#introduction)
  - [Updated data structures](#updated-data-structures)
    - [Extended `Store`](#extended-store)
  - [New data structures](#new-data-structures)
    - [`ShardLatestMessage`](#shardlatestmessage)
    - [`ShardStore`](#shardstore)
  - [Updated helpers](#updated-helpers)
    - [Updated `get_forkchoice_store`](#updated-get_forkchoice_store)
    - [Updated `update_latest_messages`](#updated-update_latest_messages)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This document is the beacon chain fork choice spec for part of Ethereum 2.0 Phase 1.

### Updated data structures

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
    shard_stores: Dict[Shard, ShardStore] = field(default_factory=dict)
```

### New data structures

#### `ShardLatestMessage`

```python
@dataclass(eq=True, frozen=True)
class ShardLatestMessage(object):
    epoch: Epoch
    root: Root
```

#### `ShardStore`

```python
@dataclass
class ShardStore:
    shard: Shard
    signed_blocks: Dict[Root, SignedShardBlock] = field(default_factory=dict)
    block_states: Dict[Root, ShardState] = field(default_factory=dict)
    latest_messages: Dict[ValidatorIndex, ShardLatestMessage] = field(default_factory=dict)
```

### Updated helpers

#### Updated `get_forkchoice_store`

```python
def get_forkchoice_store(anchor_state: BeaconState) -> Store:
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
        shard_stores={
            Shard(shard): get_forkchoice_shard_store(anchor_state, Shard(shard))
            for shard in range(get_active_shard_count(anchor_state))
        }
    )
```

#### Updated `update_latest_messages`

```python
def update_latest_messages(store: Store, attesting_indices: Sequence[ValidatorIndex], attestation: Attestation) -> None:
    target = attestation.data.target
    beacon_block_root = attestation.data.beacon_block_root
    # TODO: separate shard chain vote
    shard = attestation.data.shard
    for i in attesting_indices:
        if i not in store.latest_messages or target.epoch > store.latest_messages[i].epoch:
            store.latest_messages[i] = LatestMessage(epoch=target.epoch, root=beacon_block_root)
            shard_latest_message = ShardLatestMessage(epoch=target.epoch, root=attestation.data.shard_head_root)
            store.shard_stores[shard].latest_messages[i] = shard_latest_message
```
