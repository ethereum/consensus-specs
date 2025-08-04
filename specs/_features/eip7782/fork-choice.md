# Phase 0 -- Beacon Chain Fork Choice

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Constant](#constant)
- [Helpers](#helpers)
  - [`get_slots_since_genesis`](#get_slots_since_genesis)
  - [`get_slot_component_duration_ms`](#get_slot_component_duration_ms)

<!-- mdformat-toc end -->

### Constant

| Name | Value |
| --------------------------------- | --------------- |
| `INTERVALS_PER_SLOT` *deprecated* | `uint64(3)` |
| `BASIS_POINTS` | `uint64(10000)` |

### Helpers

#### `get_slots_since_genesis`

```python
def get_slots_since_genesis(store: Store) -> int:
    if store.time < EIP7782_FORK_TIME:
        return (store.time - store.genesis_time) // SECONDS_PER_SLOT
    else:
        slots_to_eip7782 = (EIP7782_FORK_TIME - store.genesis_time) // SECONDS_PER_SLOT
        return slots_to_eip7782 + 1000 * (store.time - EIP7782_FORK_TIME) / SLOT_DURATION_MS_EIP7782
```

#### `get_slot_component_duration_ms`

```python
def get_slot_component_duration_ms(basis_points: uint64, store: Store) -> uint64:
    """
    Calculate the duration of a slot component in milliseconds.
    """
    if compute_epoch_at_slot(get_slots_since_genesis(store)) < EIP7782_FORK_EPOCH:
        return basis_points * SLOT_DURATION_MS // BASIS_POINTS
    else:
        return basis_points * SLOT_DURATION_MS_EIP7782 // BASIS_POINTS
```