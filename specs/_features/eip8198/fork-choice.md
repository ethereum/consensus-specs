# EIP-8198 -- Beacon Chain Fork Choice

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Helpers](#helpers)
  - [Modified `get_slot_component_duration_ms`](#modified-get_slot_component_duration_ms)
  - [New `get_slot_from_time`](#new-get_slot_from_time)
  - [New `get_time_at_slot_end`](#new-get_time_at_slot_end)
  - [Modified `get_slots_since_genesis`](#modified-get_slots_since_genesis)
- [Handlers](#handlers)
  - [Modified `on_tick`](#modified-on_tick)

<!-- mdformat-toc end -->

## Introduction

EIP-8198 changes the slot duration from `SLOT_DURATION_MS` to
`SLOT_DURATION_MS_EIP8198` at `EIP8198_FORK_EPOCH`. Two things follow for the
fork choice: intra-slot deadlines must be measured against the new slot
duration, and the mapping between wall-clock time and slot number must account
for slots before the fork running at the old duration and slots after it at the
new one.

## Helpers

### Modified `get_slot_component_duration_ms`

*Note*: This is the single override that rescales every intra-slot deadline. All
Heze timing functions (`get_attestation_due_ms`, `get_aggregate_due_ms`, etc.)
are defined in terms of `get_slot_component_duration_ms`, so overriding it to
use `SLOT_DURATION_MS_EIP8198` rescales them all to the 8-second slot without
further changes.

```python
def get_slot_component_duration_ms(basis_points: Uint64) -> Uint64:
    """
    Calculate the duration of a slot component in milliseconds using EIP-8198 slot duration.
    """
    return basis_points * SLOT_DURATION_MS_EIP8198 // BASIS_POINTS
```

### New `get_slot_from_time`

```python
def get_slot_from_time(store: Store, time: Uint64) -> int:
    """
    Return the slot number corresponding to ``time``, accounting for the slot
    duration change at ``EIP8198_FORK_EPOCH``.
    """
    if EIP8198_FORK_EPOCH == FAR_FUTURE_EPOCH:
        return (time - store.genesis_time) * 1000 // SLOT_DURATION_MS
    fork_slot = EIP8198_FORK_EPOCH * SLOTS_PER_EPOCH
    fork_time = store.genesis_time + fork_slot * SLOT_DURATION_MS // 1000
    if time < fork_time:
        return (time - store.genesis_time) * 1000 // SLOT_DURATION_MS
    return fork_slot + (time - fork_time) * 1000 // SLOT_DURATION_MS_EIP8198
```

### New `get_time_at_slot_end`

```python
def get_time_at_slot_end(store: Store, slot: Slot) -> Uint64:
    """
    Return the wall-clock time (in seconds) at the end of ``slot``, i.e. the
    start of ``slot + 1``, accounting for the slot duration change.
    """
    if EIP8198_FORK_EPOCH == FAR_FUTURE_EPOCH:
        return store.genesis_time + (slot + 1) * SLOT_DURATION_MS // 1000
    fork_slot = EIP8198_FORK_EPOCH * SLOTS_PER_EPOCH
    if slot + 1 <= fork_slot:
        return store.genesis_time + (slot + 1) * SLOT_DURATION_MS // 1000
    time_before_fork = fork_slot * SLOT_DURATION_MS // 1000
    time_after_fork = (slot + 1 - fork_slot) * SLOT_DURATION_MS_EIP8198 // 1000
    return store.genesis_time + time_before_fork + time_after_fork
```

### Modified `get_slots_since_genesis`

```python
def get_slots_since_genesis(store: Store) -> int:
    return get_slot_from_time(store, store.time)
```

## Handlers

### Modified `on_tick`

```python
def on_tick(store: Store, time: Uint64) -> None:
    # If the ``store.time`` falls behind, while loop catches up slot by slot
    # to ensure that every previous slot is processed with ``on_tick_per_slot``
    tick_slot = get_slot_from_time(store, time)
    while get_current_slot(store) < tick_slot:
        previous_time = get_time_at_slot_end(store, Slot(get_current_slot(store)))
        on_tick_per_slot(store, previous_time)
    on_tick_per_slot(store, time)
```
