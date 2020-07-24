# Ethereum 2.0 Phase 1 -- Beacon Chain Fork Choice

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents
<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->


- [Introduction](#introduction)
  - [Helpers](#helpers)
    - [Extended `LatestMessage`](#extended-latestmessage)
    - [Updated `update_latest_messages`](#updated-update_latest_messages)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This document is the beacon chain fork choice spec for part of Ethereum 2.0 Phase 1.

### Helpers

#### Extended `LatestMessage`

```python
@dataclass(eq=True, frozen=True)
class LatestMessage(object):
    epoch: Epoch
    root: Root
    shard: Shard
    shard_root: Root
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
            store.latest_messages[i] = LatestMessage(
                epoch=target.epoch, root=beacon_block_root, shard=shard, shard_root=attestation.data.shard_head_root
            )
```
