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

*TODO*

#### Modified `get_slots_since_genesis`

*TODO* Fix this. Most test cases start with a state associated with the fork;
the state's slot is zero despite `EIP7782_FORK_EPOCH` being `FAR_FUTURE_EPOCH`.
The logic here will not work because `EIP7782_FORK_EPOCH` (and
`EIP7782_FORK_TIME`) are placeholder values (`UINT64_MAX`). The fix will require
some type of refactor to the fork-choice store.

```python
def get_slots_since_genesis(store: Store) -> int:
    # XXX: A bandaid until we figure out how to do this properly
    if EIP7782_FORK_EPOCH == FAR_FUTURE_EPOCH:
        eip7782_fork_epoch = GENESIS_EPOCH
    else:
        eip7782_fork_epoch = EIP7782_FORK_EPOCH

    # Calculate number of slots before eip7782 fork
    eip7782_fork_slot = eip7782_fork_epoch * SLOTS_PER_EPOCH
    eip7782_fork_time_secs = store.genesis_time + eip7782_fork_slot * SECONDS_PER_SLOT

    # Calculate number of slots after eip7782 fork
    time_after_eip7782_ms = seconds_to_milliseconds(store.time - eip7782_fork_time_secs)
    slots_after_eip7782 = time_after_eip7782_ms // SLOT_DURATION_MS_EIP7782

    return eip7782_fork_slot + slots_after_eip7782
```

#### Modified `get_slot_component_duration_ms`

```python
def get_slot_component_duration_ms(basis_points: uint64) -> uint64:
    """
    Calculate the duration of a slot component in milliseconds.
    """
    return basis_points * SLOT_DURATION_MS_EIP7782 // BASIS_POINTS
```

### Handlers

#### `on_tick`

*TODO*
