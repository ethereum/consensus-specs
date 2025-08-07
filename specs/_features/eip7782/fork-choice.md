# Phase 0 -- Beacon Chain Fork Choice

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Helpers](#helpers)
  - [Modified `get_forkchoice_store`](#modified-get_forkchoice_store)
  - [Modified `get_slots_since_genesis`](#modified-get_slots_since_genesis)
  - [Modified `get_slot_component_duration_ms`](#modified-get_slot_component_duration_ms)
- [Handlers](#handlers)
  - [`on_tick`](#on_tick)

<!-- mdformat-toc end -->

### Helpers

#### Modified `get_forkchoice_store`

```python
def get_forkchoice_store(anchor_state: BeaconState, anchor_block: BeaconBlock) -> Store:
    assert anchor_block.state_root == hash_tree_root(anchor_state)
    anchor_root = hash_tree_root(anchor_block)
    anchor_epoch = get_current_epoch(anchor_state)
    
    # Calculate time in milliseconds based on the slot duration that applies to the anchor epoch
    if anchor_epoch >= EIP7782_FORK_EPOCH:
        # Use EIP-7782 slot duration (6000 milliseconds)
        time_ms = anchor_state.genesis_time * 1000 + SLOT_DURATION_MS_EIP7782 * anchor_state.slot
    else:
        # Use standard slot duration (12000 milliseconds)
        time_ms = anchor_state.genesis_time * 1000 + SLOT_DURATION_MS * anchor_state.slot
    
    # Convert back to seconds for the store (maintaining backward compatibility)
    time = uint64(time_ms // 1000)
    
    justified_checkpoint = Checkpoint(epoch=anchor_epoch, root=anchor_root)
    finalized_checkpoint = Checkpoint(epoch=anchor_epoch, root=anchor_root)
    proposer_boost_root = Root()
    return Store(
        time=time,
        genesis_time=anchor_state.genesis_time,
        justified_checkpoint=justified_checkpoint,
        finalized_checkpoint=finalized_checkpoint,
        unrealized_justified_checkpoint=justified_checkpoint,
        unrealized_finalized_checkpoint=finalized_checkpoint,
        proposer_boost_root=proposer_boost_root,
        equivocating_indices=set(),
        blocks={anchor_root: copy(anchor_block)},
        block_states={anchor_root: copy(anchor_state)},
        checkpoint_states={justified_checkpoint: copy(anchor_state)},
        unrealized_justifications={anchor_root: justified_checkpoint},
    )
```

#### Modified `get_slots_since_genesis`

```python
def get_slots_since_genesis(store: Store) -> int:
    """
    Calculate the number of slots since genesis, accounting for EIP-7782 slot duration changes.
    Uses millisecond-based calculations for better precision and future fractional slot support.
    """
    # Convert store time to milliseconds for precise calculations
    store_time_ms = store.time * 1000
    genesis_time_ms = store.genesis_time * 1000
    
    # Calculate the time when EIP-7782 fork occurs
    if EIP7782_FORK_EPOCH == FAR_FUTURE_EPOCH:
        # If EIP-7782 is not scheduled, use standard slot duration
        return (store_time_ms - genesis_time_ms) // SLOT_DURATION_MS
    
    # Calculate the slot and time when EIP-7782 fork occurs (in milliseconds)
    eip7782_fork_slot = EIP7782_FORK_EPOCH * SLOTS_PER_EPOCH
    eip7782_fork_time_ms = genesis_time_ms + eip7782_fork_slot * SLOT_DURATION_MS
    
    if store_time_ms < eip7782_fork_time_ms:
        # Before EIP-7782 fork, use standard slot duration
        return (store_time_ms - genesis_time_ms) // SLOT_DURATION_MS
    else:
        # After EIP-7782 fork, calculate slots before and after the fork
        slots_before_eip7782 = eip7782_fork_slot
        time_after_eip7782_ms = store_time_ms - eip7782_fork_time_ms
        slots_after_eip7782 = time_after_eip7782_ms // SLOT_DURATION_MS_EIP7782
        return slots_before_eip7782 + slots_after_eip7782
```

#### Modified `get_slot_component_duration_ms`

```python
def get_slot_component_duration_ms(basis_points: uint64) -> uint64:
    """
    Calculate the duration of a slot component in milliseconds using EIP-7782 slot duration.
    """
    return basis_points * SLOT_DURATION_MS_EIP7782 // BASIS_POINTS
```

#### New `get_slot_duration_ms_for_epoch`

```python
def get_slot_duration_ms_for_epoch(epoch: Epoch) -> uint64:
    """
    Return the slot duration in milliseconds for a given epoch.
    This function enables future support for fractional slot times.
    """
    if epoch >= EIP7782_FORK_EPOCH:
        return SLOT_DURATION_MS_EIP7782  # 6000 milliseconds
    else:
        return SLOT_DURATION_MS  # 12000 milliseconds
```

#### New `get_slots_since_genesis_ms`

```python
def get_slots_since_genesis_ms(store: Store) -> int:
    """
    Calculate the number of slots since genesis using millisecond precision.
    This function provides the foundation for future fractional slot support.
    """
    store_time_ms = store.time * 1000
    genesis_time_ms = store.genesis_time * 1000
    
    if EIP7782_FORK_EPOCH == FAR_FUTURE_EPOCH:
        return (store_time_ms - genesis_time_ms) // SLOT_DURATION_MS
    
    eip7782_fork_slot = EIP7782_FORK_EPOCH * SLOTS_PER_EPOCH
    eip7782_fork_time_ms = genesis_time_ms + eip7782_fork_slot * SLOT_DURATION_MS
    
    if store_time_ms < eip7782_fork_time_ms:
        return (store_time_ms - genesis_time_ms) // SLOT_DURATION_MS
    else:
        slots_before_eip7782 = eip7782_fork_slot
        time_after_eip7782_ms = store_time_ms - eip7782_fork_time_ms
        slots_after_eip7782 = time_after_eip7782_ms // SLOT_DURATION_MS_EIP7782
        return slots_before_eip7782 + slots_after_eip7782
```

### Handlers

#### `on_tick`