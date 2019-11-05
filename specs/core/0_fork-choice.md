# Ethereum 2.0 Phase 0 -- Beacon Chain Fork Choice

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents
<!-- TOC -->

- [Ethereum 2.0 Phase 0 -- Beacon Chain Fork Choice](#ethereum-20-phase-0----beacon-chain-fork-choice)
    - [Table of contents](#table-of-contents)
    - [Introduction](#introduction)
    - [Fork choice](#fork-choice)
        - [Helpers](#helpers)
            - [`LatestMessage`](#latestmessage)
            - [`Store`](#store)
            - [`get_genesis_store`](#get_genesis_store)
            - [`get_ancestor`](#get_ancestor)
            - [`get_latest_attesting_balance`](#get_latest_attesting_balance)
            - [`get_head`](#get_head)
        - [Handlers](#handlers)
            - [`on_tick`](#on_tick)
            - [`on_block`](#on_block)
            - [`on_attestation`](#on_attestation)

<!-- /TOC -->

## Introduction

This document is the beacon chain fork choice spec, part of Ethereum 2.0 Phase 0. It assumes the [beacon chain state transition function spec](./0_beacon-chain.md).

## Fork choice

The head block root associated with a `store` is defined as `get_head(store)`. At genesis, let `store = get_genesis_store(genesis_state)` and update `store` by running:

- `on_tick(time)` whenever `time > store.time` where `time` is the current Unix time
- `on_block(block)` whenever a block `block` is received
- `on_attestation(attestation)` whenever an attestation `attestation` is received

*Notes*:

1) **Leap seconds**: Slots will last `SECONDS_PER_SLOT + 1` or `SECONDS_PER_SLOT - 1` seconds around leap seconds. This is automatically handled by [UNIX time](https://en.wikipedia.org/wiki/Unix_time).
2) **Honest clocks**: Honest nodes are assumed to have clocks synchronized within `SECONDS_PER_SLOT` seconds of each other.
3) **Eth1 data**: The large `ETH1_FOLLOW_DISTANCE` specified in the [honest validator document](../validator/0_beacon-chain-validator.md) should ensure that `state.latest_eth1_data` of the canonical Ethereum 2.0 chain remains consistent with the canonical Ethereum 1.0 chain. If not, emergency manual intervention will be required.
4) **Manual forks**: Manual forks may arbitrarily change the fork choice rule but are expected to be enacted at epoch transitions, with the fork details reflected in `state.fork`.
5) **Implementation**: The implementation found in this specification is constructed for ease of understanding rather than for optimization in computation, space, or any other resource. A number of optimized alternatives can be found [here](https://github.com/protolambda/lmd-ghost).

### Configuration

| Name | Value | Unit | Duration |
| - | - | :-: | :-: |
| `SAFE_SLOTS_TO_UPDATE_JUSTIFIED` | `9` | slots | 108 seconds |

### Helpers

#### `LatestMessage`

```python
@dataclass(eq=True, frozen=True)
class LatestMessage(object):
    epoch: Epoch
    root: Hash
```

#### `Store`

```python
@dataclass
class Store(object):
    time: uint64
    genesis_time: uint64
    justified_checkpoint: Checkpoint
    finalized_checkpoint: Checkpoint
    queued_justified_checkpoints: List[Checkpoint, 2**40] = field(default_factory=list)
    blocks: Dict[Hash, BeaconBlock] = field(default_factory=dict)
    block_states: Dict[Hash, BeaconState] = field(default_factory=dict)
    checkpoint_states: Dict[Checkpoint, BeaconState] = field(default_factory=dict)
    latest_messages: Dict[ValidatorIndex, LatestMessage] = field(default_factory=dict)
```

#### `get_genesis_store`

```python
def get_genesis_store(genesis_state: BeaconState) -> Store:
    genesis_block = BeaconBlock(state_root=hash_tree_root(genesis_state))
    root = signing_root(genesis_block)
    justified_checkpoint = Checkpoint(epoch=GENESIS_EPOCH, root=root)
    finalized_checkpoint = Checkpoint(epoch=GENESIS_EPOCH, root=root)
    return Store(
        time=genesis_state.genesis_time,
        genesis_time=genesis_state.genesis_time,
        justified_checkpoint=justified_checkpoint,
        finalized_checkpoint=finalized_checkpoint,
        blocks={root: genesis_block},
        block_states={root: genesis_state.copy()},
        checkpoint_states={justified_checkpoint: genesis_state.copy()},
    )
```

```python
def get_current_slot(store: Store) -> Slot:
    return Slot((store.time - store.genesis_time) // SECONDS_PER_SLOT)
```

#### `get_ancestor`

```python
def get_ancestor(store: Store, root: Hash, slot: Slot) -> Hash:
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
def get_latest_attesting_balance(store: Store, root: Hash) -> Gwei:
    state = store.checkpoint_states[store.justified_checkpoint]
    active_indices = get_active_validator_indices(state, get_current_epoch(state))
    return Gwei(sum(
        state.validators[i].effective_balance for i in active_indices
        if (i in store.latest_messages 
            and get_ancestor(store, store.latest_messages[i].root, store.blocks[root].slot) == root)
    ))
```

#### `get_head`

```python
def get_head(store: Store) -> Hash:
    # Execute the LMD-GHOST fork choice
    head = store.justified_checkpoint.root
    justified_slot = compute_start_slot_at_epoch(store.justified_checkpoint.epoch)
    while True:
        children = [
            root for root in store.blocks.keys()
            if store.blocks[root].parent_root == head and store.blocks[root].slot > justified_slot
        ]
        if len(children) == 0:
            return head
        # Sort by latest attesting balance with ties broken lexicographically
        head = max(children, key=lambda root: (get_latest_attesting_balance(store, root), root))
```

#### `should_update_justified_checkpoint`

```python
def should_update_justified_checkpoint(store: Store, justified_checkpoint: Checkpoint) -> bool:
    current_epoch = compute_epoch_at_slot(get_current_slot(store))

    if get_current_slot(store) % SLOTS_PER_EPOCH < SAFE_SLOTS_TO_UPDATE_JUSTIFIED:
        return True

    justified_block = store.blocks[justified_checkpoint.root]
    if justified_block.slot <= compute_start_slot_at_epoch(store.justified_checkpoint.epoch):
        return False
    if not get_ancestor(store, justified_checkpoint.root, store.blocks[justified_checkpoint.root].slot):
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
    # not a new epoch, return
    if not (current_slot > previous_slot and current_slot % SLOTS_PER_EPOCH == 0):
        return
    # if new epoch and there are queued_justified_checkpoints, update if any is better than the best in store
    if any(store.queued_justified_checkpoints):
        best_justified_checkpoint = max(store.queued_justified_checkpoints, key=lambda checkpoint: checkpoint.epoch)
        if best_justified_checkpoint.epoch > store.justified_checkpoint.epoch:
            store.justified_checkpoint = best_justified_checkpoint
```

#### `on_block`

```python
def on_block(store: Store, block: BeaconBlock) -> None:
    # Make a copy of the state to avoid mutability issues
    assert block.parent_root in store.block_states
    pre_state = store.block_states[block.parent_root].copy()
    # Blocks cannot be in the future. If they are, their consideration must be delayed until the are in the past.
    assert store.time >= pre_state.genesis_time + block.slot * SECONDS_PER_SLOT
    # Add new block to the store
    store.blocks[signing_root(block)] = block
    # Check block is a descendant of the finalized block
    assert (
        get_ancestor(store, signing_root(block), store.blocks[store.finalized_checkpoint.root].slot) ==
        store.finalized_checkpoint.root
    )
    # Check that block is later than the finalized epoch slot
    assert block.slot > compute_start_slot_at_epoch(store.finalized_checkpoint.epoch)
    # Check the block is valid and compute the post-state
    state = state_transition(pre_state, block, True)
    # Add new state for this block to the store
    store.block_states[signing_root(block)] = state

    # Update justified checkpoint
    if state.current_justified_checkpoint.epoch > store.justified_checkpoint.epoch:
        if should_update_justified_checkpoint(store, state.current_justified_checkpoint):
            store.justified_checkpoint = state.current_justified_checkpoint
        else:
            store.queued_justified_checkpoints.append(state.current_justified_checkpoint)

    # Update finalized checkpoint
    if state.finalized_checkpoint.epoch > store.finalized_checkpoint.epoch:
        store.finalized_checkpoint = state.finalized_checkpoint
```

#### `on_attestation`

```python
def on_attestation(store: Store, attestation: Attestation) -> None:
    target = attestation.data.target

    # Cannot calculate the current shuffling if have not seen the target
    assert target.root in store.blocks

    # Attestations cannot be from future epochs. If they are, delay consideration until the epoch arrives
    base_state = store.block_states[target.root].copy()
    assert store.time >= base_state.genesis_time + compute_start_slot_at_epoch(target.epoch) * SECONDS_PER_SLOT

    # Store target checkpoint state if not yet seen
    if target not in store.checkpoint_states:
        process_slots(base_state, compute_start_slot_at_epoch(target.epoch))
        store.checkpoint_states[target] = base_state
    target_state = store.checkpoint_states[target]

    # Attestations can only affect the fork choice of subsequent slots.
    # Delay consideration in the fork choice until their slot is in the past.
    assert store.time >= (attestation.data.slot + 1) * SECONDS_PER_SLOT

    # Get state at the `target` to validate attestation and calculate the committees
    indexed_attestation = get_indexed_attestation(target_state, attestation)
    assert is_valid_indexed_attestation(target_state, indexed_attestation)

    # Update latest messages
    for i in indexed_attestation.custody_bit_0_indices + indexed_attestation.custody_bit_1_indices:
        if i not in store.latest_messages or target.epoch > store.latest_messages[i].epoch:
            store.latest_messages[i] = LatestMessage(epoch=target.epoch, root=attestation.data.beacon_block_root)
```
