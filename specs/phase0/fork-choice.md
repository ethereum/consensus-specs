# Ethereum 2.0 Phase 0 -- Beacon Chain Fork Choice

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents
<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->


- [Introduction](#introduction)
- [Fork choice](#fork-choice)
  - [Configuration](#configuration)
  - [Helpers](#helpers)
    - [`LatestMessage`](#latestmessage)
    - [`Store`](#store)
    - [`get_forkchoice_store`](#get_forkchoice_store)
    - [`get_slots_since_genesis`](#get_slots_since_genesis)
    - [`get_current_slot`](#get_current_slot)
    - [`compute_slots_since_epoch_start`](#compute_slots_since_epoch_start)
    - [`get_ancestor`](#get_ancestor)
    - [`get_latest_attesting_balance`](#get_latest_attesting_balance)
    - [`filter_block_tree`](#filter_block_tree)
    - [`get_filtered_block_tree`](#get_filtered_block_tree)
    - [`get_head`](#get_head)
    - [`should_update_justified_checkpoint`](#should_update_justified_checkpoint)
  - [Handlers](#handlers)
    - [`on_tick`](#on_tick)
    - [`on_block`](#on_block)
    - [`on_attestation`](#on_attestation)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This document is the beacon chain fork choice spec, part of Ethereum 2.0 Phase 0. It assumes the [beacon chain state transition function spec](./beacon-chain.md).

## Fork choice

The head block root associated with a `store` is defined as `get_head(store)`. At genesis, let `store = get_checkpoint_store(genesis_state)` and update `store` by running:

- `on_tick(time)` whenever `time > store.time` where `time` is the current Unix time
- `on_block(block)` whenever a block `block: SignedBeaconBlock` is received
- `on_attestation(attestation)` whenever an attestation `attestation` is received

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
    epoch: Epoch
    root: Root
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
    blocks: Dict[Root, BeaconBlockHeader] = field(default_factory=dict)
    block_states: Dict[Root, BeaconState] = field(default_factory=dict)
    checkpoint_states: Dict[Checkpoint, BeaconState] = field(default_factory=dict)
    latest_messages: Dict[ValidatorIndex, LatestMessage] = field(default_factory=dict)
```

#### `get_forkchoice_store`

The provided anchor-state will be regarded as a trusted state, to not roll back beyond.
This should be the genesis state for a full client.

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
        time=anchor_state.genesis_time,
        genesis_time=anchor_state.genesis_time,
        justified_checkpoint=justified_checkpoint,
        finalized_checkpoint=finalized_checkpoint,
        best_justified_checkpoint=justified_checkpoint,
        blocks={anchor_root: anchor_block_header},
        block_states={anchor_root: anchor_state.copy()},
        checkpoint_states={justified_checkpoint: anchor_state.copy()},
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
    block = store.blocks[root]
    if block.slot > slot:
        return get_ancestor(store, block.parent_root, slot)
    elif block.slot == slot:
        return root
    else:
        return Bytes32()  # root is older than queried slot: no results. 
```

#### `get_latest_attesting_balance`

```python
def get_latest_attesting_balance(store: Store, root: Root) -> Gwei:
    state = store.checkpoint_states[store.justified_checkpoint]
    active_indices = get_active_validator_indices(state, get_current_epoch(state))
    return Gwei(sum(
        state.validators[i].effective_balance for i in active_indices
        if (i in store.latest_messages 
            and get_ancestor(store, store.latest_messages[i].root, store.blocks[root].slot) == root)
    ))
```

#### `filter_block_tree`

```python
def filter_block_tree(store: Store, block_root: Root, blocks: Dict[Root, BeaconBlock]) -> bool:
    block = store.blocks[block_root]
    children = [
        root for root in store.blocks.keys()
        if store.blocks[root].parent_root == block_root
    ]

    # If any children branches contain expected finalized/justified checkpoints,
    # add to filtered block-tree and signal viability to parent.
    if any(children):
        filter_block_tree_result = [filter_block_tree(store, child, blocks) for child in children]
        if any(filter_block_tree_result):
            blocks[block_root] = block
            return True
        return False

    # If leaf block, check finalized/justified checkpoints as matching latest.
    head_state = store.block_states[block_root]

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
        blocks[block_root] = block
        return True

    # Otherwise, branch not viable
    return False
```

#### `get_filtered_block_tree`

```python
def get_filtered_block_tree(store: Store) -> Dict[Root, BeaconBlock]:
    """
    Retrieve a filtered block tree from ``store``, only returning branches
    whose leaf state's justified/finalized info agrees with that in ``store``.
    """
    base = store.justified_checkpoint.root
    blocks: Dict[Root, BeaconBlock] = {}
    filter_block_tree(store, base, blocks)
    return blocks
```

#### `get_head`

```python
def get_head(store: Store) -> Root:
    # Get filtered block tree that only includes viable branches
    blocks = get_filtered_block_tree(store)
    # Execute the LMD-GHOST fork choice
    head = store.justified_checkpoint.root
    justified_slot = compute_start_slot_at_epoch(store.justified_checkpoint.epoch)
    while True:
        children = [
            root for root in blocks.keys()
            if blocks[root].parent_root == head and blocks[root].slot > justified_slot
        ]
        if len(children) == 0:
            return head
        # Sort by latest attesting balance with ties broken lexicographically
        head = max(children, key=lambda root: (get_latest_attesting_balance(store, root), root))
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

    new_justified_block = store.blocks[new_justified_checkpoint.root]
    if new_justified_block.slot <= compute_start_slot_at_epoch(store.justified_checkpoint.epoch):
        return False
    if not (
        get_ancestor(store, new_justified_checkpoint.root, store.blocks[store.justified_checkpoint.root].slot)
        == store.justified_checkpoint.root
    ):
        return False

    return True
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
    # Make a copy of the state to avoid mutability issues
    assert block.parent_root in store.block_states
    pre_state = store.block_states[block.parent_root].copy()
    # Blocks cannot be in the future. If they are, their consideration must be delayed until the are in the past.
    assert get_current_slot(store) >= block.slot
    # Add new block to the store
    store.blocks[hash_tree_root(block)] = block
    # Check block is a descendant of the finalized block
    assert (
        get_ancestor(store, hash_tree_root(block), store.blocks[store.finalized_checkpoint.root].slot) ==
        store.finalized_checkpoint.root
    )
    # Check that block is later than the finalized epoch slot
    assert block.slot > compute_start_slot_at_epoch(store.finalized_checkpoint.epoch)
    # Check the block is valid and compute the post-state
    state = state_transition(pre_state, signed_block, True)
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
```

#### `on_attestation`

```python
def validate_on_attestation(store: Store, attestation: Attestation) -> None:
    target = attestation.data.target

    # Attestations must be from the current or previous epoch 
    current_epoch = compute_epoch_at_slot(get_current_slot(store))
    # Use GENESIS_EPOCH for previous when genesis to avoid underflow
    previous_epoch = current_epoch - 1 if current_epoch > GENESIS_EPOCH else GENESIS_EPOCH
    assert target.epoch in [current_epoch, previous_epoch]
    assert target.epoch == compute_epoch_at_slot(attestation.data.slot)

    # Attestations target be for a known block. If target block is unknown, delay consideration until the block is found
    assert target.root in store.blocks
    # Attestations cannot be from future epochs. If they are, delay consideration until the epoch arrives
    assert get_current_slot(store) >= compute_start_slot_at_epoch(target.epoch)

    # Attestations must be for a known block. If block is unknown, delay consideration until the block is found
    assert attestation.data.beacon_block_root in store.blocks
    # Attestations must not be for blocks in the future. If not, the attestation should not be considered
    assert store.blocks[attestation.data.beacon_block_root].slot <= attestation.data.slot

    # Attestations can only affect the fork choice of subsequent slots.
    # Delay consideration in the fork choice until their slot is in the past.
    assert get_current_slot(store) >= attestation.data.slot + 1


def store_target_checkpoint_state(store: Store, target: Checkpoint) -> None:
    # Store target checkpoint state if not yet seen
    if target not in store.checkpoint_states:
        base_state = store.block_states[target.root].copy()
        process_slots(base_state, compute_start_slot_at_epoch(target.epoch))
        store.checkpoint_states[target] = base_state


def update_latest_messages(store: Store, attesting_indices: Sequence[ValidatorIndex], attestation: Attestation) -> None:
    target = attestation.data.target
    beacon_block_root = attestation.data.beacon_block_root
    for i in attesting_indices:
        if i not in store.latest_messages or target.epoch > store.latest_messages[i].epoch:
            store.latest_messages[i] = LatestMessage(epoch=target.epoch, root=beacon_block_root)


def on_attestation(store: Store, attestation: Attestation) -> None:
    """
    Run ``on_attestation`` upon receiving a new ``attestation`` from either within a block or directly on the wire.

    An ``attestation`` that is asserted as invalid may be valid at a later time,
    consider scheduling it for later processing in such case.
    """
    validate_on_attestation(store, attestation)
    store_target_checkpoint_state(store, attestation.data.target)

    target_state = store.checkpoint_states[attestation.data.target]
    # Get state at the `target` to validate attestation and calculate the committees
    indexed_attestation = get_indexed_attestation(target_state, attestation)
    assert is_valid_indexed_attestation(target_state, indexed_attestation)

    update_latest_messages(store, indexed_attestation.attesting_indices, attestation)
```
