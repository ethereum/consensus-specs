# Ethereum 2.0 Phase 0 -- Beacon Chain Fork Choice

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents
<!-- TOC -->

- [Ethereum 2.0 Phase 0 -- Beacon Chain Fork Choice](#ethereum-20-phase-0----beacon-chain-fork-choice)
    - [Table of contents](#table-of-contents)
    - [Introduction](#introduction)
    - [Constants](#constants)
        - [Time parameters](#time-parameters)
    - [Fork choice](#fork-choice)
        - [Helpers](#helpers)
            - [`Target`](#target)
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

## Configuration

### Time parameters

| Name | Value | Unit | Duration |
| - | - | :-: | :-: |
| `SECONDS_PER_SLOT` | `6` | seconds | 6 seconds |

## Fork choice

The head block root associated with a `store` is defined as `get_head(store)`. At genesis let `store = get_genesis_store(genesis_state)` and update `store` by running:

* `on_tick(time)` whenever `time > store.time` where `time` is the current Unix time
* `on_block(block)` whenever a block `block` is received
* `on_attestation(attestation)` whenever an attestation `attestation` is received

*Notes*:

1) **Leap seconds**: Slots will last `SECONDS_PER_SLOT + 1` or `SECONDS_PER_SLOT - 1` seconds around leap seconds.
2) **Honest clocks**: Honest nodes are assumed to have clocks synchronized within `SECONDS_PER_SLOT` seconds of each other.
3) **Eth1 data**: The large `ETH1_FOLLOW_DISTANCE` specified in the [honest validator document](https://github.com/ethereum/eth2.0-specs/blob/dev/specs/validator/0_beacon-chain-validator.md) should ensure that `state.latest_eth1_data` of the canonical Ethereum 2.0 chain remains consistent with the canonical Ethereum 1.0 chain. If not, emergency manual intervention will be required.
4) **Manual forks**: Manual forks may arbitrarily change the fork choice rule but are expected to be enacted at epoch transitions, with the fork details reflected in `state.fork`.

### Helpers

#### `Target`

```python
@dataclass
class Target(object):
    epoch: Epoch
    root: Hash
```

#### `RootSlot`

```python
@dataclass
class RootSlot(object):
    slot: Slot
    root: Hash
```



#### `Store`

```python
@dataclass
class Store(object):
    blocks: Dict[Hash, BeaconBlock] = field(default_factory=dict)
    states: Dict[RootSlot, BeaconState] = field(default_factory=dict)
    time: int = 0
    latest_targets: Dict[ValidatorIndex, Target] = field(default_factory=dict)
    justified_root: Hash = ZERO_HASH
    justified_epoch: Epoch = 0
    finalized_root: Hash = ZERO_HASH
    finalized_epoch: Epoch = 0
```

#### `get_genesis_store`

```python
def get_genesis_store(genesis_state: BeaconState) -> Store:
    genesis_block = BeaconBlock(state_root=hash_tree_root(genesis_state))
    root = signing_root(genesis_block)
    return Store(blocks={root: genesis_block}, states={root: genesis_state}, justified_root=root, finalized_root=root)
```

#### `get_ancestor`

```python
def get_ancestor(store: Store, root: Hash, slot: Slot) -> Hash:
    block = store.blocks[root]
    assert block.slot >= slot
    return root if block.slot == slot else get_ancestor(store, block.parent_root, slot)
```

#### `get_latest_attesting_balance`

```python
def get_latest_attesting_balance(store: Store, root: Hash) -> Gwei:
    state = store.states[RootSlot(store.justified_root, get_epoch_start_slot(store.justified_epoch)]
    active_indices = get_active_validator_indices(state.validator_registry, get_current_epoch(state))
    return Gwei(sum(
        state.validator_registry[i].effective_balance for i in active_indices
        if get_ancestor(store, store.latest_targets[i].root, store.blocks[root].slot) == root
    ))
```

#### `get_head`

```python
def get_head(store: Store) -> Hash:
    # Execute the LMD-GHOST fork choice
    head = store.justified_root
    justified_slot = get_epoch_start_slot(store.justified_epoch)
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

### Handlers

#### `on_tick`

```python
def on_tick(store: Store, time: int) -> None:
    store.time = time
```

#### `on_block`

```python
def on_block(store: Store, block: BeaconBlock) -> None:
    # Add new block to the store
    store.blocks[signing_root(block)] = block
    # Check block is a descendant of the finalized block
    assert get_ancestor(store, signing_root(block), store.blocks[store.finalized_root].slot) == store.finalized_root
    # Check that block is later than the finalized epoch slot
    assert blocks.slot > get_epoch_start_slot(store.finalized_epoch)
    # Check block slot against Unix time
    pre_state = deepcopy(store.states[block.parent_root])
    assert store.time >= pre_state.genesis_time + block.slot * SECONDS_PER_SLOT
    # Check the block is valid and compute the post-state
    state = state_transition(pre_state, block)
    # Add new state for this block to the store
    store.states[RootSlot(signing_root(block), block.slot)] = state
    # Update justified block root and epoch
    previous_justified_epoch = store.justified_epoch
    justified_root_slot = None
    if state.current_justified_epoch > store.justified_epoch:
        store.justified_root = state.current_justified_root
        state.justified_epoch = state.current_justified_epoch
    elif state.previous_justified_epoch > store.justified_epoch:
        store.justified_root = state.previous_justified_root
        state.justified_epoch = state.previous_justified_epoch

    # Store justified state
    if previous_justified_epoch != store.justified_epoch:
        justified_slot = get_epoch_start_slot(store.justified_epoch)
        justified_root_slot = RootSlot(store.justified_root, justified_slot)
        if justified_root_slot not in store.states:
            base_state = store.states[RootSlot(store.justified_root, store.blocks[store.justified_root].slot)]
            store.states[justified_root_slot] = process_slots(deepcopy(base_state), justified_slot)

    # Update finalized block root and epoch, and store finalized state
    if state.finalized_epoch > state.finalized_epoch:
        store.finalized_root = state.finalized_root
        store.finalized_epoch = state.finalized_epoch
        finalized_slot = get_epoch_start_slot(store.finalized_epoch)
        finalized_root_slot = RootSlot(store.finalized_root, finalized_slot)
        if finalized_root_slot not in store.states:
            base_state = store.states[RootSlot(store.finalized_root, store.blocks[store.finalized_root].slot)]
            store.states[finalized_root_slot] = process_slots(deepcopy(base_state), finalized_slot)
```

#### `on_attestation`

```python
def on_attestation(store: Store, attestation: Attestation) -> None:
    # cannot calculate the current shuffling if have not seen the target
    assert attestation.data.target_root in store.blocks

    # get state at the `target_root`/`target_epoch` to validate attestation and calculate the committees
    state = store.states[(attestation.data.target_root, get_epoch_start_slot(attestation.data.target_epoch))]

    indexed_attestation = convert_to_indexed(state, attestation)
    validate_indexed_attestation(state, indexed_attestation)

    # update latest targets
    for i in indexed_attestation.custody_bit_0_indices + indexed_attestation.custody_bit_1_indices:
        if i not in store.latest_targets or attestation.data.target_epoch > store.latest_targets[i].epoch:
            store.latest_targets[i] = Target(attestation.data.target_epoch, attestation.data.target_root)
```
