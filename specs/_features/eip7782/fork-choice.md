# EIP-7782 -- Beacon Chain Fork Choice

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Helpers](#helpers)
  - [Modified `get_forkchoice_store`](#modified-get_forkchoice_store)
  - [Modified `get_slots_since_genesis`](#modified-get_slots_since_genesis)
  - [Modified `get_slot_component_duration_ms`](#modified-get_slot_component_duration_ms)
  - [New `get_slot_duration_ms_for_epoch`](#new-get_slot_duration_ms_for_epoch)
  - [New `get_slots_since_genesis_ms`](#new-get_slots_since_genesis_ms)
- [Handlers](#handlers)
  - [`on_tick`](#on_tick)
  - [`on_tick_per_slot`](#on_tick_per_slot)

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
        return SLOT_DURATION_MS_EIP7782
    else:
        return SLOT_DURATION_MS
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

```python
def on_tick(store: Store, time: uint64) -> None:
    """
    Run ``on_tick`` upon receiving a new time tick.
    Uses millisecond-based calculations for better precision and future fractional slot support.
    """
    # Convert time to milliseconds for precise calculations
    time_ms = time * 1000
    genesis_time_ms = store.genesis_time * 1000
    
    # Calculate the current slot using the appropriate slot duration
    if EIP7782_FORK_EPOCH == FAR_FUTURE_EPOCH:
        # If EIP-7782 is not scheduled, use standard slot duration
        tick_slot = (time_ms - genesis_time_ms) // SLOT_DURATION_MS
    else:
        # Use the new helper function that handles the fork transition
        tick_slot = get_slots_since_genesis_ms(Store(
            time=time,
            genesis_time=store.genesis_time,
            justified_checkpoint=store.justified_checkpoint,
            finalized_checkpoint=store.finalized_checkpoint,
            unrealized_justified_checkpoint=store.unrealized_justified_checkpoint,
            unrealized_finalized_checkpoint=store.unrealized_finalized_checkpoint,
            proposer_boost_root=store.proposer_boost_root,
            equivocating_indices=store.equivocating_indices,
            blocks=store.blocks,
            block_states=store.block_states,
            checkpoint_states=store.checkpoint_states,
            unrealized_justifications=store.unrealized_justifications,
        ))
    
    # Process each slot up to the current tick slot
    while get_current_slot(store) < tick_slot:
        current_slot = get_current_slot(store)
        
        # Calculate the time for the next slot using the correct slot duration for that specific slot
        if EIP7782_FORK_EPOCH == FAR_FUTURE_EPOCH:
            # If EIP-7782 is not scheduled, use standard slot duration
            previous_time = store.genesis_time + (current_slot + 1) * SLOT_DURATION_MS // 1000
        else:
            # Calculate the time using the correct slot duration for each slot
            eip7782_fork_slot = EIP7782_FORK_EPOCH * SLOTS_PER_EPOCH
            
            if current_slot < eip7782_fork_slot:
                # Before EIP-7782 fork, use standard slot duration
                previous_time = store.genesis_time + (current_slot + 1) * SLOT_DURATION_MS // 1000
            else:
                # After EIP-7782 fork, calculate time using both slot durations
                # Time for slots before the fork
                time_before_fork = eip7782_fork_slot * SLOT_DURATION_MS // 1000
                # Time for slots after the fork (including the current slot)
                slots_after_fork = current_slot - eip7782_fork_slot + 1
                time_after_fork = slots_after_fork * SLOT_DURATION_MS_EIP7782 // 1000
                # Total time
                previous_time = store.genesis_time + time_before_fork + time_after_fork
        
        on_tick_per_slot(store, previous_time)
    
    on_tick_per_slot(store, time)
```

#### `on_tick_per_slot`

```python
def on_tick_per_slot(store: Store, time: uint64) -> None:
    """
    Run ``on_tick_per_slot`` for a specific time.
    Uses millisecond-based calculations for better precision and future fractional slot support.
    """
    previous_slot = get_current_slot(store)

    # Update store time
    store.time = time

    current_slot = get_current_slot(store)

    # If this is a new slot, reset store.proposer_boost_root
    if current_slot > previous_slot:
        store.proposer_boost_root = Root()

    # If a new epoch, pull-up justification and finalization from previous epoch
    if current_slot > previous_slot and compute_slots_since_epoch_start(current_slot) == 0:
        update_checkpoints(
            store, store.unrealized_justified_checkpoint, store.unrealized_finalized_checkpoint
        )
```
