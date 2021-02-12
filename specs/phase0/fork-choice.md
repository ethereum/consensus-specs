# Ethereum 2.0 Phase 0 -- Beacon Chain Fork Choice

## Table of contents
<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Fork choice](#fork-choice)
  - [Configuration](#configuration)
  - [Helpers](#helpers)
    - [`LatestMessage`](#latestmessage)
    - [`BlockSlotNode`](#blockslotnode)
    - [`BlockSlotKey`](#blockslotkey)
    - [`get_block_slot_key`](#get_block_slot_key)
    - [`Store`](#store)
    - [`get_forkchoice_store`](#get_forkchoice_store)
    - [`get_slots_since_genesis`](#get_slots_since_genesis)
    - [`get_current_slot`](#get_current_slot)
    - [`compute_slots_since_epoch_start`](#compute_slots_since_epoch_start)
    - [`get_ancestor`](#get_ancestor)
    - [`get_ancestor_node`](#get_ancestor_node)
    - [`get_latest_attesting_balance`](#get_latest_attesting_balance)
    - [`filter_block_slot_tree`](#filter_block_slot_tree)
    - [`get_filtered_block_tree`](#get_filtered_block_tree)
    - [`get_head`](#get_head)
    - [`should_update_justified_checkpoint`](#should_update_justified_checkpoint)
    - [`on_attestation` helpers](#on_attestation-helpers)
      - [`validate_on_attestation`](#validate_on_attestation)
      - [`store_target_checkpoint_state`](#store_target_checkpoint_state)
      - [`update_latest_messages`](#update_latest_messages)
    - [`add_block_slot_node`](#add_block_slot_node)
  - [Handlers](#handlers)
    - [`on_tick`](#on_tick)
    - [`on_block`](#on_block)
    - [`on_attestation`](#on_attestation)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This document is the beacon chain fork choice spec, part of Ethereum 2.0 Phase 0. It assumes the [beacon chain state transition function spec](./beacon-chain.md).

## Fork choice

The head block root associated with a `store` is defined as `get_head(store)`. At genesis, let `store = get_forkchoice_store(genesis_state, genesis_block, genesis_block.slot)` and update `store` by running:

- `on_tick(store, time)` whenever `time > store.time` where `time` is the current Unix time
- `on_block(store, block)` whenever a block `block: SignedBeaconBlock` is received
- `on_attestation(store, attestation)` whenever an attestation `attestation` is received

Any of the above handlers that trigger an unhandled exception (e.g. a failed assert or an out-of-range list access) are considered invalid. Invalid calls to handlers must not modify `store`.

*Notes*:

1) **Leap seconds**: Slots will last `SECONDS_PER_SLOT + 1` or `SECONDS_PER_SLOT - 1` seconds around leap seconds. This is automatically handled by [UNIX time](https://en.wikipedia.org/wiki/Unix_time).
2) **Honest clocks**: Honest nodes are assumed to have clocks synchronized within `SECONDS_PER_SLOT` seconds of each other.
3) **Eth1 data**: The large `ETH1_FOLLOW_DISTANCE` specified in the [honest validator document](./validator.md) should ensure that `state.latest_eth1_data` of the canonical Ethereum 2.0 chain remains consistent with the canonical Ethereum 1.0 chain. If not, emergency manual intervention will be required.
4) **Manual forks**: Manual forks may arbitrarily change the fork choice rule but are expected to be enacted at epoch transitions, with the fork details reflected in `state.fork`.
5) **Implementation**: The implementation found in this specification is constructed for ease of understanding rather than for optimization in computation, space, or any other resource. A number of optimized alternatives can be found [here](https://github.com/protolambda/lmd-ghost).

### Configuration

| Name | Value | Unit | Duration |
| - | - | :-: | :-: |
| `SAFE_SLOTS_TO_UPDATE_JUSTIFIED` | `2**3` (= 8) | slots | 96 seconds |

### Helpers

#### `LatestMessage`

```python
@dataclass(eq=True, frozen=True)
class LatestMessage(object):
    slot: Slot
    root: Root
```

#### `BlockSlotNode`

```python
class BlockSlotNode(Container):
    block_root: Root
    slot: Slot
    parent_node: Root
```

#### `BlockSlotKey`

```python
class BlockSlotKey(Container):
    block_root: Root
    slot: Slot
```

#### `get_block_slot_key`

```python
def get_block_slot_key(block_root: Root, slot: Slot) -> Root:
    return hash_tree_root(BlockSlotKey(block_root=block_root, slot=slot))
```

#### `Store`

```python
@dataclass
class Store(object):
    time: uint64
    genesis_time: uint64
    justified_checkpoint: Checkpoint
    finalized_checkpoint: Checkpoint
    best_justified_checkpoint: Checkpoint
    blocks: Dict[Root, BeaconBlock] = field(default_factory=dict)
    block_slot_tree: Dict[Root, BlockSlotNode] = field(default_factory=dict)
    block_states: Dict[Root, BeaconState] = field(default_factory=dict)
    checkpoint_states: Dict[Checkpoint, BeaconState] = field(default_factory=dict)
    latest_messages: Dict[ValidatorIndex, LatestMessage] = field(default_factory=dict)
```

#### `get_forkchoice_store`

The provided anchor-state will be regarded as a trusted state, to not roll back beyond.
This should be the genesis state for a full client.

*Note* With regards to fork choice, block headers are interchangeable with blocks. The spec is likely to move to headers for reduced overhead in test vectors and better encapsulation. Full implementations store blocks as part of their database and will often use full blocks when dealing with production fork choice.

```python
def get_forkchoice_store(anchor_state: BeaconState, anchor_block: BeaconBlock, anchor_slot: Slot) -> Store:
    assert anchor_block.state_root == hash_tree_root(anchor_state)
    anchor_root = hash_tree_root(anchor_block)
    anchor_node = BlockSlotNode(block_root=anchor_root, slot=anchor_slot, parent_node=Root())
    anchor_node_key = get_block_slot_key(anchor_root, anchor_slot)
    anchor_epoch = get_current_epoch(anchor_state)
    justified_checkpoint = Checkpoint(epoch=anchor_epoch, root=anchor_root)
    finalized_checkpoint = Checkpoint(epoch=anchor_epoch, root=anchor_root)
    return Store(
        time=uint64(anchor_state.genesis_time + SECONDS_PER_SLOT * anchor_state.slot),
        genesis_time=anchor_state.genesis_time,
        justified_checkpoint=justified_checkpoint,
        finalized_checkpoint=finalized_checkpoint,
        best_justified_checkpoint=justified_checkpoint,
        blocks={anchor_root: copy(anchor_block)},
        block_slot_tree={anchor_node_key: copy(anchor_node)},
        block_states={anchor_root: copy(anchor_state)},
        checkpoint_states={justified_checkpoint: copy(anchor_state)},
    )
```

#### `get_slots_since_genesis`

```python
def get_slots_since_genesis(store: Store) -> int:
    return (store.time - store.genesis_time) // SECONDS_PER_SLOT
```

#### `get_current_slot`

```python
def get_current_slot(store: Store) -> Slot:
    return Slot(GENESIS_SLOT + get_slots_since_genesis(store))
```

#### `compute_slots_since_epoch_start`

```python
def compute_slots_since_epoch_start(slot: Slot) -> int:
    return slot - compute_start_slot_at_epoch(compute_epoch_at_slot(slot))
```

#### `get_ancestor`

```python
def get_ancestor(store: Store, root: Root, slot: Slot) -> Root:
    # Return highest block's root with slot less than or equal to the queried slot
    block = store.blocks[root]
    if block.slot > slot:
        return get_ancestor(store, block.parent_root, slot)
    else:
        return root
```

#### `get_ancestor_node`

```python
def get_ancestor_node(store: Store, node_key: Root, slot: Slot) -> Root:
    # Return highest node's key with slot less than or equal to the queried slot
    node = store.block_slot_tree[node_key]
    if node.slot > slot:
        return get_ancestor_node(store, node.parent_node, slot)
    else:
        return get_block_slot_key(node.block_root, node.slot)
```

#### `get_latest_attesting_balance`

```python
def get_latest_attesting_balance(store: Store, node_key: Root) -> Gwei:
    state = store.checkpoint_states[store.justified_checkpoint]
    active_indices = get_active_validator_indices(state, get_current_epoch(state))
    node = store.block_slot_tree[node_key]
    return Gwei(sum(
        state.validators[i].effective_balance for i in active_indices
        if (i in store.latest_messages
            and get_ancestor_node(store, store.latest_messages[i].root, node.slot) == node_key)
    ))
```

#### `filter_block_slot_tree`

```python
def filter_block_slot_tree(store: Store, node_key: Root, nodes: Dict[Root, BlockSlotNode]) -> bool:
    node = store.block_slot_tree[node_key]
    children = [
        root for root in store.block_slot_tree.keys()
        if store.block_slot_tree[root].parent_node == node_key
    ]

    # If any children branches contain expected finalized/justified checkpoints,
    # add to filtered block-tree and signal viability to parent.
    if any(children):
        filter_block_slot_tree_result = [filter_block_slot_tree(store, child_key, nodes) for child_key in children]
        if any(filter_block_slot_tree_result):
            nodes[node_key] = node
            return True
        return False

    # If leaf node, check finalized/justified checkpoints as matching latest.
    head_state = store.block_states[node.block_root]

    correct_justified = (
        store.justified_checkpoint.epoch == GENESIS_EPOCH
        or head_state.current_justified_checkpoint == store.justified_checkpoint
    )
    correct_finalized = (
        store.finalized_checkpoint.epoch == GENESIS_EPOCH
        or head_state.finalized_checkpoint == store.finalized_checkpoint
    )
    # If expected finalized/justified, add to viable block-tree and signal viability to parent.
    if correct_justified and correct_finalized:
        nodes[node_key] = node
        return True

    # Otherwise, branch not viable
    return False
```

#### `get_filtered_block_tree`

```python
def get_filtered_block_slot_tree(store: Store) -> Dict[Root, BlockSlotNode]:
    """
    Retrieve a filtered (block, slot)-tree from ``store``, only returning branches
    whose leaf state's justified/finalized info agrees with that in ``store``.
    """
    base_block_root = store.justified_checkpoint.root
    base_slot = compute_start_slot_at_epoch(store.justified_checkpoint.epoch)
    base_node_key = get_block_slot_key(base_block_root, base_slot)
    nodes: Dict[Root, BlockSlotNode] = {}
    filter_block_slot_tree(store, base_node_key, nodes)
    return nodes
```

#### `get_head`

```python
def get_head(store: Store) -> Root:
    # Get filtered (block, slot)-tree that only includes viable branches
    nodes = get_filtered_block_slot_tree(store)
    # Execute the LMD-GHOST fork choice
    base_block_root = store.justified_checkpoint.root
    base_slot = compute_start_slot_at_epoch(store.justified_checkpoint.epoch)
    head_node_key = get_block_slot_key(base_block_root, base_slot)
    while True:
        children = [
            key for key in nodes.keys()
            if nodes[key].parent_node == head_node_key
        ]
        if len(children) == 0:
            return store.block_slot_tree[head_node_key].block_root
        # Sort by latest attesting balance with ties broken lexicographically
        head_node_key = max(children, key=lambda key: (get_latest_attesting_balance(store, key), nodes[key].block_root))
```

#### `should_update_justified_checkpoint`

```python
def should_update_justified_checkpoint(store: Store, new_justified_checkpoint: Checkpoint) -> bool:
    """
    To address the bouncing attack, only update conflicting justified
    checkpoints in the fork choice if in the early slots of the epoch.
    Otherwise, delay incorporation of new justified checkpoint until next epoch boundary.

    See https://ethresear.ch/t/prevention-of-bouncing-attack-on-ffg/6114 for more detailed analysis and discussion.
    """
    if compute_slots_since_epoch_start(get_current_slot(store)) < SAFE_SLOTS_TO_UPDATE_JUSTIFIED:
        return True

    justified_slot = compute_start_slot_at_epoch(store.justified_checkpoint.epoch)
    new_justified_checkpoint_node_key = get_block_slot_key(
        block_root=new_justified_checkpoint.root,
        slot=compute_start_slot_at_epoch(new_justified_checkpoint.epoch)
    )
    new_justified_checkpoint_ancestor_node_key = get_ancestor_node(
        store=store,
        node_key=new_justified_checkpoint_node_key,
        slot=justified_slot
    )
    new_justified_checkpoint_ancestor_node = store.block_slot_tree[new_justified_checkpoint_ancestor_node_key]
    if not new_justified_checkpoint_ancestor_node.block_root == store.justified_checkpoint.root:
        return False

    return True
```

#### `on_attestation` helpers

##### `validate_on_attestation`

```python
def validate_on_attestation(store: Store, attestation: Attestation) -> None:
    target = attestation.data.target

    # Attestations must be from the current or previous epoch
    current_epoch = compute_epoch_at_slot(get_current_slot(store))
    # Use GENESIS_EPOCH for previous when genesis to avoid underflow
    previous_epoch = current_epoch - 1 if current_epoch > GENESIS_EPOCH else GENESIS_EPOCH
    # If attestation target is from a future epoch, delay consideration until the epoch arrives
    assert target.epoch in [current_epoch, previous_epoch]
    assert target.epoch == compute_epoch_at_slot(attestation.data.slot)

    # Attestations target be for a known block. If target block is unknown, delay consideration until the block is found
    assert target.root in store.blocks

    # Attestations must be for a known block. If block is unknown, delay consideration until the block is found
    assert attestation.data.beacon_block_root in store.blocks
    # Attestations must not be for blocks in the future. If not, the attestation should not be considered
    assert store.blocks[attestation.data.beacon_block_root].slot <= attestation.data.slot

    # LMD vote must be consistent with FFG vote target in block hierarchy
    target_slot = compute_start_slot_at_epoch(target.epoch)
    assert target.root == get_ancestor(store, attestation.data.beacon_block_root, target_slot)

    # Attestations can only affect the fork choice of subsequent slots.
    # Delay consideration in the fork choice until their slot is in the past.
    assert get_current_slot(store) >= attestation.data.slot + 1
```

##### `store_target_checkpoint_state`

```python
def store_target_checkpoint_state(store: Store, target: Checkpoint) -> None:
    # Store target checkpoint state if not yet seen
    if target not in store.checkpoint_states:
        base_state = copy(store.block_states[target.root])
        if base_state.slot < compute_start_slot_at_epoch(target.epoch):
            process_slots(base_state, compute_start_slot_at_epoch(target.epoch))
        store.checkpoint_states[target] = base_state
```

##### `update_latest_messages`

```python
def update_latest_messages(store: Store, attesting_indices: Sequence[ValidatorIndex], attestation: Attestation) -> None:
    attestation_slot = attestation.data.slot
    beacon_block_root = attestation.data.beacon_block_root
    for i in attesting_indices:
        if i not in store.latest_messages or attestation_slot > store.latest_messages[i].slot:
            node_key = get_block_slot_key(beacon_block_root, attestation_slot)
            store.latest_messages[i] = LatestMessage(slot=attestation_slot, root=node_key)
```

#### `add_block_slot_node`

```python
def add_block_slot_node(store: Store, block: BeaconBlock, node_slot: Slot) -> BlockSlotNode:
    """
    Adds a ``BlockSlotNode`` corresponding to ``block`` at slot ``node_slot`` in ``store.block_slot_tree`` 
    and returns the same.

    Algorithm:
        1. Check if the parent block's node exists at slot ``block.slot - 1``. 
           If not found, recursively call ``add_block_slot_node()`` for parent block's node.
        2. Add this block's node from ``block.slot`` till ``node_slot``. 
    """
    assert block.slot <= node_slot

    # Check if parent block's node exists at ``block.slot-1``
    # Check for parent block's node only if current block is not genesis/anchor block
    # NOTE: This only checks if ``block`` is the genesis block. Arbitrary anchor block capability
    # is not implemented yet.
    if block.slot > GENESIS_SLOT:
        parent_block_node_slot = Slot(block.slot - 1)
        parent_node_key = get_block_slot_key(block.parent_root, parent_block_node_slot)
        # Add the parent block's node if it doesn't exist
        if parent_node_key not in store.block_slot_tree.keys():
            parent_block = store.blocks[block.parent_root]
            store.block_slot_tree[parent_node_key] = add_block_slot_node(
                store, parent_block, parent_block_node_slot)
    else:
        parent_node_key = Root()
    
    # Add this block's nodes from ``block.slot`` till ``slot``
    block_root = hash_tree_root(block)
    for block_node_slot in range(block.slot, node_slot + 1):
        block_node = BlockSlotNode(
            block_root=block_root, 
            slot=Slot(block_node_slot), 
            parent_node=parent_node_key, 
        )
        block_node_key = get_block_slot_key(block_root, Slot(block_node_slot))
        store.block_slot_tree[block_node_key] = block_node
        parent_node_key = block_node_key
    return block_node
```

### Handlers

#### `on_tick`

```python
def on_tick(store: Store, time: uint64) -> None:
    previous_slot = get_current_slot(store)

    # update store time
    store.time = time

    current_slot = get_current_slot(store)
    # Not a new epoch, return
    if not (current_slot > previous_slot and compute_slots_since_epoch_start(current_slot) == 0):
        return
    # Update store.justified_checkpoint if a better checkpoint is known
    if store.best_justified_checkpoint.epoch > store.justified_checkpoint.epoch:
        store.justified_checkpoint = store.best_justified_checkpoint
```

#### `on_block`

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

    # Check the block is valid and compute the post-state
    state = pre_state.copy()
    state_transition(state, signed_block, True)
    # Add new block to the store
    store.blocks[hash_tree_root(block)] = block
    # Add new (block, slot)-node to the store
    add_block_slot_node(store, block, block.slot)
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

#### `on_attestation`

```python
def on_attestation(store: Store, attestation: Attestation) -> None:
    """
    Run ``on_attestation`` upon receiving a new ``attestation`` from either within a block or directly on the wire.

    An ``attestation`` that is asserted as invalid may be valid at a later time,
    consider scheduling it for later processing in such case.
    """
    validate_on_attestation(store, attestation)
    store_target_checkpoint_state(store, attestation.data.target)

    # Get state at the `target` to fully validate attestation
    target_state = store.checkpoint_states[attestation.data.target]
    indexed_attestation = get_indexed_attestation(target_state, attestation)
    assert is_valid_indexed_attestation(target_state, indexed_attestation)

    lmd_block = store.blocks[attestation.data.beacon_block_root]
    add_block_slot_node(store, lmd_block, attestation.data.slot)

    # LMD vote must be consistent with FFG vote target in the (block, slot)-tree
    target = attestation.data.target
    target_slot = compute_start_slot_at_epoch(target.epoch)
    ffg_node_key = get_block_slot_key(target.root, target_slot)
    lmd_block_root = attestation.data.beacon_block_root
    lmd_slot = attestation.data.slot
    lmd_node_key = get_block_slot_key(lmd_block_root, lmd_slot)
    assert ffg_node_key == get_ancestor_node(store, lmd_node_key, target_slot)

    # Update latest messages for attesting indices
    update_latest_messages(store, indexed_attestation.attesting_indices, attestation)
```
