# EIP-8198 -- Beacon Chain Fork Choice

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Helpers](#helpers)
  - [Modified `get_slot_component_duration_ms`](#modified-get_slot_component_duration_ms)
  - [New `get_slot_from_time`](#new-get_slot_from_time)
  - [New `get_time_at_slot_end`](#new-get_time_at_slot_end)
  - [New `get_time_into_slot_ms`](#new-get_time_into_slot_ms)
  - [Modified `get_slots_since_genesis`](#modified-get_slots_since_genesis)
  - [Modified `record_block_timeliness`](#modified-record_block_timeliness)
  - [Modified `is_proposing_on_time`](#modified-is_proposing_on_time)
- [Handlers](#handlers)
  - [Modified `on_tick`](#modified-on_tick)
  - [Modified `on_inclusion_list`](#modified-on_inclusion_list)

<!-- mdformat-toc end -->

## Introduction

EIP-8198 changes the slot duration from `SLOT_DURATION_MS` to
`SLOT_DURATION_MS_EIP8198` at `EIP8198_FORK_EPOCH`. Three things follow for the
fork choice:

- intra-slot deadlines must be measured against the new slot duration
  (`get_slot_component_duration_ms`),
- the mapping between wall-clock time and slot number must account for slots
  before the fork running at the old duration and slots after it at the new one
  (`get_slot_from_time`, `get_time_at_slot_end`), and
- the time elapsed *within* the current slot can no longer be computed as time
  since genesis modulo `SLOT_DURATION_MS`, because post-fork slot boundaries
  are not aligned to genesis at the old duration. Every timeliness check
  (attestation deadline, proposer reorg cutoff, payload timeliness, inclusion
  list deadline) is therefore rebased on the new `get_time_into_slot_ms`
  helper.

## Helpers

### Modified `get_slot_component_duration_ms`

*Note*: This override rescales every intra-slot *deadline*. All Heze timing
functions (`get_attestation_due_ms`, `get_aggregate_due_ms`, etc.) are defined
in terms of `get_slot_component_duration_ms`, so overriding it to use
`SLOT_DURATION_MS_EIP8198` rescales them all to the EIP-8198 slot duration
without further changes. The *measurement* of time elapsed within the current
slot, against which these deadlines are compared, is handled separately by
`get_time_into_slot_ms` below.

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

### New `get_time_into_slot_ms`

*Note*: Before the fork, slot starts are aligned to
`genesis_time + n * SLOT_DURATION_MS`, so the time into the current slot is
simply the time since genesis modulo `SLOT_DURATION_MS`. After the fork, slot
starts are aligned to `fork_time + n * SLOT_DURATION_MS_EIP8198` instead, so
the modulo must be taken relative to the fork time and the new duration.

```python
def get_time_into_slot_ms(store: Store) -> Uint64:
    """
    Return the time elapsed since the start of the current slot in
    milliseconds, accounting for the slot duration change at
    ``EIP8198_FORK_EPOCH``.
    """
    time_ms = seconds_to_milliseconds(store.time - store.genesis_time)
    if EIP8198_FORK_EPOCH == FAR_FUTURE_EPOCH:
        return time_ms % SLOT_DURATION_MS
    fork_time_ms = EIP8198_FORK_EPOCH * SLOTS_PER_EPOCH * SLOT_DURATION_MS
    if time_ms < fork_time_ms:
        return time_ms % SLOT_DURATION_MS
    return (time_ms - fork_time_ms) % SLOT_DURATION_MS_EIP8198
```

### Modified `get_slots_since_genesis`

```python
def get_slots_since_genesis(store: Store) -> int:
    return get_slot_from_time(store, store.time)
```

### Modified `record_block_timeliness`

*Note*: Identical to the Gloas definition except that the time into the slot is
computed with `get_time_into_slot_ms`.

```python
def record_block_timeliness(store: Store, root: Root) -> None:
    block = store.blocks[root]
    # [Modified in EIP8198]
    time_into_slot_ms = get_time_into_slot_ms(store)
    attestation_threshold_ms = get_attestation_due_ms()
    is_current_slot = get_current_slot(store) == block.slot
    ptc_threshold_ms = get_payload_attestation_due_ms()
    store.block_timeliness[root] = [
        is_current_slot and time_into_slot_ms < threshold
        for threshold in [attestation_threshold_ms, ptc_threshold_ms]
    ]
```

### Modified `is_proposing_on_time`

*Note*: Identical to the Phase 0 definition except that the time into the slot
is computed with `get_time_into_slot_ms`.

```python
def is_proposing_on_time(store: Store) -> bool:
    # [Modified in EIP8198]
    time_into_slot_ms = get_time_into_slot_ms(store)
    proposer_reorg_cutoff_ms = get_proposer_reorg_cutoff_ms()
    return time_into_slot_ms <= proposer_reorg_cutoff_ms
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

### Modified `on_inclusion_list`

*Note*: Identical to the Heze definition except that the time into the slot is
computed with `get_time_into_slot_ms`.

```python
def on_inclusion_list(store: Store, signed_inclusion_list: SignedInclusionList) -> None:
    """
    Run ``on_inclusion_list`` upon receiving a new inclusion list.
    """
    inclusion_list = signed_inclusion_list.message

    # [Modified in EIP8198]
    time_into_slot_ms = get_time_into_slot_ms(store)
    inclusion_list_due_ms = get_inclusion_list_due_ms()
    is_timely = time_into_slot_ms < inclusion_list_due_ms

    process_inclusion_list(get_inclusion_list_store(), inclusion_list, is_timely)
```
