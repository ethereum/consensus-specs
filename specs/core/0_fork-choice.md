# Ethereum 2.0 Phase 0 -- Beacon Chain Fork Choice

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents
<!-- TOC -->

- [Ethereum 2.0 Phase 0 -- Beacon Chain Fork Choice](#ethereum-20-phase-0----beacon-chain-fork-choice)
    - [Table of contents](#table-of-contents)
    - [Introduction](#introduction)
    - [Prerequisites](#prerequisites)
    - [Constants](#constants)
        - [Time parameters](#time-parameters)
    - [Beacon chain processing](#beacon-chain-processing)
        - [Beacon chain fork choice rule](#beacon-chain-fork-choice-rule)
    - [Implementation notes](#implementation-notes)
        - [Justification and finality at genesis](#justification-and-finality-at-genesis)

<!-- /TOC -->

## Introduction

This document represents the specification for the beacon chain fork choice rule, part of Ethereum 2.0 Phase 0.

## Prerequisites

All terminology, constants, functions, and protocol mechanics defined in the [Phase 0 -- The Beacon Chain](./0_beacon-chain.md) doc are requisite for this document and used throughout. Please see the Phase 0 doc before continuing and use as a reference throughout.

## Constants

### Time parameters

| Name | Value | Unit | Duration |
| - | - | :-: | :-: |
| `SECONDS_PER_SLOT` | `6` | seconds | 6 seconds |

## Beacon chain processing

Processing the beacon chain is similar to processing the Ethereum 1.0 chain. Clients download and process blocks and maintain a view of what is the current "canonical chain", terminating at the current "head". For a beacon block, `block`, to be processed by a node, the following conditions must be met:

* The parent block with root `block.parent_root` has been processed and accepted.
* An Ethereum 1.0 block pointed to by the `state.latest_eth1_data.block_hash` has been processed and accepted.
* The node's Unix time is greater than or equal to `state.genesis_time + block.slot * SECONDS_PER_SLOT`.

*Note*: Leap seconds mean that slots will occasionally last `SECONDS_PER_SLOT + 1` or `SECONDS_PER_SLOT - 1` seconds, possibly several times a year.

*Note*: Nodes needs to have a clock that is roughly (i.e. within `SECONDS_PER_SLOT` seconds) synchronized with the other nodes.

### Client-side data structures

#### `AttestationRecord`

```python
{
    'epoch': 'uint64',
    'target': 'bytes32'
}
```

#### `Store`

```python
{
    'blocks': Map['Bytes32', BeaconBlock],
    'post_states': Map['Bytes32', BeaconState],
    'time': 'uint64',
    'genesis_time': 'uint64',
    'latest_attestations': Map['uint64', AttestationRecord],
    'finalized_head': 'Bytes32',
    'justified_head': 'Bytes32',
}
```

### Functions


### `initialize_store`

```python
def initialize_store(genesis_state: BeaconState) -> Store:
    genesis_block = BeaconBlock(state_root=hash_tree_root(genesis_state))
    return Store(
        blocks={hash_tree_root(genesis_block): genesis_block},
        post_states={hash_tree_root(genesis_block): genesis_state},
        time=0,
        genesis_time=genesis_state.genesis_time,
        latest_attestations={},
        finalized_head=hash_tree_root(genesis_block),
        justified_head=hash_tree_root(genesis_block),
    )
```

### `tick`

```python
def tick(store: Store, now: Time):
    """
    Call whenever the time increments, passing in the new time
    """
    store.time = now
```

### `get_ancestor`

```python
def get_ancestor(store: Store, block: Bytes32, slot: Slot) -> Bytes32:
    if store.blocks[block].slot < slot:
        raise Exception("Cannot get ancestor at later slot than block")
    elif store.blocks[block].slot == slot:
        return block
    else:
        return get_ancestor(store, store.blocks[block].parent_root, slot)
```

### `is_ancestor`

```python
def is_ancestor(store: Store, ancestor: Bytes32, descendant: Bytes32) -> bool:
    return get_ancestor(store, descendant, store.blocks[ancestor].slot) == ancestor

### `add_block`

```python
def add_block(store: Store, block: BeaconBlock):
    """
    Call upon receiving a block
    """
    # Check parent has been processed
    assert block.parent_root in store.blocks
    # Check it's a descendant of the finalized block
    assert is_ancestor(store, store.finalized_head, hash_tree_root(block))
    # Check it's not too early
    assert store.time >= store.genesis_time + block.slot * SECONDS_PER_SLOT
    # Check the block is valid and compute the post-state
    post_state = process_block(pre_state=store.post_states[block.parent_root], block)
    # Add it
    store.blocks[hash_tree_root(block)] = block
    store.post_states[hash_tree_root(block)] = post_state
    # Update justified and finalized blocks
    if post_state.finalized_epoch > get_current_epoch(store.blocks[store.finalized_head]):
        store.finalized_head = post_state.finalized_root
    if post_state.current_justified_epoch > get_current_epoch(store.blocks[store.justified_head]):
        store.justified_head = post_state.current_justified_root
    if post_state.previous_justified_epoch > get_current_epoch(store.blocks[store.justified_head]):
        store.justified_head = post_state.previous_justified_root
```

### `get_children`

```python
def get_children(store: Store, parent: Bytes32):
    return [block for block in store.blocks.keys() if store.blocks[block].parent_root == parent]
```

### `receive_attestation`

```python
def receive_attestation(store: Store, attestation: Attestation):
    """
    Call upon receiving an attestation
    """
    head_state = store.post_states[get_head(store)]
    indexed_attestation = convert_to_indexed(head_state, attestation)
    assert validate_indexed_attestation(head_state, indexed_attestation)
    participants = indexed_attestation.bit_0_indices + indexed_attestation.bit_1_indices
    for p in participants:
        if p not in store.latest_attestations or attestation.epoch > store.latest_attestations[p].epoch:
            store.latest_attestations[p] = AttestationRecord(epoch=attestation.epoch, target=attestation.data.target_root)
```

### `get_head`

```python
def get_head(store: Store):
    return lmd_ghost(store=store, validators=store.post_states[store.justified_head], root=store.justified_head)
```

### `lmd_ghost`

```python
def lmd_ghost(store: Store, start_state: BeaconState, root: Bytes32) -> BeaconBlock:
    """
    Execute the LMD-GHOST algorithm to find the head ``BeaconBlock``.
    """
    validators = start_state.validator_registry
    active_validator_indices = get_active_validator_indices(validators, slot_to_epoch(start_state.slot))
    attestation_targets = [(i, store.latest_attestations[i].target) for i in active_validator_indices if i in store.latest_attestations]

    # Use the rounded-balance-with-hysteresis supplied by the protocol for fork
    # choice voting. This reduces the number of recomputations that need to be
    # made for optimized implementations that precompute and save data
    def get_vote_count(block: BeaconBlock) -> int:
        return sum(
            start_state.validator_registry[validator_index].effective_balance
            for validator_index, target in attestation_targets
            if get_ancestor(store, target, block.slot) == block
        )

    head = root
    while 1:
        children = get_children(store, head)
        if len(children) == 0:
            return head
        # Ties broken by favoring block with lexicographically higher root
        head = max(children, key=lambda x: (get_vote_count(x), hash_tree_root(x)))
```
