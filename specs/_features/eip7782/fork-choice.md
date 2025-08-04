# Phase 0 -- Beacon Chain Fork Choice

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Helpers](#helpers)
  - [Modified `get_slots_since_genesis`](#modified-get_slots_since_genesis)
  - [Modified `get_slot_component_duration_ms`](#modified-get_slot_component_duration_ms)

<!-- mdformat-toc end -->

### Helpers

#### Modified `get_slots_since_genesis`

```python
def get_slots_since_genesis(store: Store) -> int:
    # Calculate number of slots before eip7782 fork
    eip7782_fork_slot = EIP7782_FORK_EPOCH * SLOTS_PER_EPOCH
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
