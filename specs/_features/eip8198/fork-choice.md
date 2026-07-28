# EIP-8198 -- Beacon Chain Fork Choice

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Configuration](#configuration)
  - [Resulting mainnet deadlines](#resulting-mainnet-deadlines)
- [Helpers](#helpers)
  - [Modified `Store`](#modified-store)
  - [Modified `get_forkchoice_store`](#modified-get_forkchoice_store)
  - [Modified `get_slot_component_duration_ms`](#modified-get_slot_component_duration_ms)
  - [New `get_slot_from_time_ms`](#new-get_slot_from_time_ms)
  - [New `get_slot_from_time`](#new-get_slot_from_time)
  - [New `get_time_at_slot_end_ms`](#new-get_time_at_slot_end_ms)
  - [New `get_time_at_slot_end`](#new-get_time_at_slot_end)
  - [New `get_time_into_slot_ms`](#new-get_time_into_slot_ms)
  - [Modified `get_slots_since_genesis`](#modified-get_slots_since_genesis)
  - [Modified `record_block_timeliness`](#modified-record_block_timeliness)
  - [Modified `is_proposing_on_time`](#modified-is_proposing_on_time)
- [Handlers](#handlers)
  - [Modified `on_tick_per_slot`](#modified-on_tick_per_slot)
  - [New `on_tick_per_slot_ms`](#new-on_tick_per_slot_ms)
  - [New `on_tick_ms`](#new-on_tick_ms)
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
  before the fork running at the old duration and slots after it at the new one,
  using the canonical beacon-chain timeline helpers, and
- the time elapsed *within* the current slot can no longer be computed as time
  since genesis modulo `SLOT_DURATION_MS`, because post-fork slot boundaries are
  not aligned to genesis at the old duration. Every timeliness check
  (attestation deadline, proposer reorg cutoff, payload timeliness, inclusion
  list deadline) is therefore rebased on the new `get_time_into_slot_ms` helper.

Fork-choice time MUST retain millisecond precision. Implementations MUST drive
the store with `on_tick_ms`; the whole-second `on_tick` entry point is retained
only as a backwards-compatible adapter for inherited test vectors and callers
that do not need to represent sub-second instants.

## Configuration

### Resulting mainnet deadlines

EIP-8198 deliberately retains every inherited basis-point value. The resulting
deadlines below make that protocol choice explicit; changing an individual
deadline requires a separate parameter change rather than following
automatically from the clock infrastructure.

| Component                   | Basis points | Post-fork deadline |
| --------------------------- | -----------: | -----------------: |
| Proposer reorg cutoff       |         1667 |           1,667 ms |
| Attestation                 |         2500 |           2,500 ms |
| Sync committee message      |         2500 |           2,500 ms |
| Aggregate                   |         5000 |           5,000 ms |
| Sync committee contribution |         5000 |           5,000 ms |
| Execution payload           |         5000 |           5,000 ms |
| Inclusion list              |         6667 |           6,667 ms |
| Payload attestation         |         7500 |           7,500 ms |

## Helpers

### Modified `Store`

*Note*: The `time` field remains for backwards compatibility with inherited
fork-choice test formats. EIP-8198 adds `time_ms` as the authoritative clock
used for slot and deadline calculations.

```python
@dataclass
class Store:
    time: Uint64
    # [New in EIP8198]
    time_ms: Uint64
    genesis_time: Uint64
    justified_checkpoint: Checkpoint
    finalized_checkpoint: Checkpoint
    unrealized_justified_checkpoint: Checkpoint
    unrealized_finalized_checkpoint: Checkpoint
    proposer_boost_root: Root
    equivocating_indices: Set[ValidatorIndex]
    blocks: Dict[Root, BeaconBlock] = field(default_factory=dict)
    block_states: Dict[Root, BeaconState] = field(default_factory=dict)
    # [Modified in Gloas:EIP7732]
    block_timeliness: Dict[Root, list[Boolean]] = field(default_factory=dict)
    checkpoint_states: Dict[Checkpoint, BeaconState] = field(default_factory=dict)
    latest_messages: Dict[ValidatorIndex, LatestMessage] = field(default_factory=dict)
    unrealized_justifications: Dict[Root, Checkpoint] = field(default_factory=dict)
    # [New in Gloas:EIP7732]
    payloads: Dict[Root, ExecutionPayloadEnvelope] = field(default_factory=dict)
    # [New in Gloas:EIP7732]
    payload_timeliness_vote: Dict[Root, list[Optional[Boolean]]] = field(default_factory=dict)
    # [New in Gloas:EIP7732]
    payload_data_availability_vote: Dict[Root, list[Optional[Boolean]]] = field(
        default_factory=dict
    )
    # [New in Heze:EIP7805]
    payload_inclusion_list_satisfaction: Dict[Root, Boolean] = field(default_factory=dict)
```

### Modified `get_forkchoice_store`

*Note*: Identical to the Heze definition except that the initial store time is
derived with the EIP-8198-aware `compute_time_at_slot` (see the beacon chain
document) instead of assuming `SLOT_DURATION_MS` slots since genesis. This
matters when the anchor state is past the fork, e.g. on checkpoint sync.

```python
def get_forkchoice_store(anchor_state: BeaconState, anchor_block: BeaconBlock) -> Store:
    assert anchor_block.state_root == hash_tree_root(anchor_state)
    anchor_root = hash_tree_root(anchor_block)
    anchor_epoch = get_current_epoch(anchor_state)
    justified_checkpoint = Checkpoint(epoch=anchor_epoch, root=anchor_root)
    finalized_checkpoint = Checkpoint(epoch=anchor_epoch, root=anchor_root)
    proposer_boost_root = Root()
    return Store(
        # [Modified in EIP8198]
        time=compute_time_at_slot(anchor_state, anchor_state.slot),
        # [New in EIP8198]
        time_ms=compute_time_at_slot_ms(anchor_state, anchor_state.slot),
        genesis_time=anchor_state.genesis_time,
        justified_checkpoint=justified_checkpoint,
        finalized_checkpoint=finalized_checkpoint,
        unrealized_justified_checkpoint=justified_checkpoint,
        unrealized_finalized_checkpoint=finalized_checkpoint,
        proposer_boost_root=proposer_boost_root,
        equivocating_indices=set(),
        blocks={anchor_root: copy(anchor_block)},
        block_states={anchor_root: copy(anchor_state)},
        # [New in Gloas:EIP7732]
        block_timeliness={anchor_root: [True, True]},
        checkpoint_states={justified_checkpoint: copy(anchor_state)},
        unrealized_justifications={anchor_root: justified_checkpoint},
        # [New in Gloas:EIP7732]
        payloads={},
        # [New in Gloas:EIP7732]
        payload_timeliness_vote={},
        # [New in Gloas:EIP7732]
        payload_data_availability_vote={},
        # [New in Heze:EIP7805]
        payload_inclusion_list_satisfaction={},
    )
```

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
    # [Modified in EIP8198]
    return basis_points * SLOT_DURATION_MS_EIP8198 // BASIS_POINTS
```

### New `get_slot_from_time_ms`

```python
def get_slot_from_time_ms(store: Store, time_ms: Uint64) -> int:
    """
    Return the number of slots since genesis corresponding to ``time_ms``.
    """
    return compute_slot_at_time_ms(store.genesis_time, time_ms) - GENESIS_SLOT
```

### New `get_slot_from_time`

```python
def get_slot_from_time(store: Store, time: Uint64) -> int:
    """
    Whole-second compatibility wrapper around ``get_slot_from_time_ms``.
    """
    return get_slot_from_time_ms(store, seconds_to_milliseconds(time))
```

### New `get_time_at_slot_end_ms`

```python
def get_time_at_slot_end_ms(store: Store, slot: Slot) -> Uint64:
    """
    Return the absolute Unix time in milliseconds at the end of ``slot``.
    """
    return compute_slot_start_time_ms(store.genesis_time, Slot(slot + 1))
```

### New `get_time_at_slot_end`

```python
def get_time_at_slot_end(store: Store, slot: Slot) -> Uint64:
    """
    Whole-second compatibility wrapper around ``get_time_at_slot_end_ms``.
    """
    return get_time_at_slot_end_ms(store, slot) // 1000
```

### New `get_time_into_slot_ms`

*Note*: The elapsed time is computed from the authoritative millisecond clock
and the canonical start time of the current slot. This preserves exact
sub-second deadline boundaries.

```python
def get_time_into_slot_ms(store: Store) -> Uint64:
    """
    Return the time elapsed since the start of the current slot in
    milliseconds, accounting for the slot duration change at
    ``EIP8198_FORK_EPOCH``.
    """
    current_slot = Slot(GENESIS_SLOT + get_slot_from_time_ms(store, store.time_ms))
    slot_start_time_ms = compute_slot_start_time_ms(store.genesis_time, current_slot)
    return store.time_ms - slot_start_time_ms
```

### Modified `get_slots_since_genesis`

```python
def get_slots_since_genesis(store: Store) -> int:
    # [Modified in EIP8198]
    return get_slot_from_time_ms(store, store.time_ms)
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

### Modified `on_tick_per_slot`

*Note*: This whole-second entry point remains as a compatibility adapter.
`on_tick_per_slot_ms` is authoritative and keeps both clock fields synchronized.

```python
def on_tick_per_slot(store: Store, time: Uint64) -> None:
    # [Modified in EIP8198]
    on_tick_per_slot_ms(store, seconds_to_milliseconds(time))
```

### New `on_tick_per_slot_ms`

```python
def on_tick_per_slot_ms(store: Store, time_ms: Uint64) -> None:
    previous_slot = get_current_slot(store)

    # [Modified in EIP8198]
    store.time_ms = time_ms
    store.time = time_ms // 1000

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

### New `on_tick_ms`

```python
def on_tick_ms(store: Store, time_ms: Uint64) -> None:
    assert time_ms >= store.time_ms
    tick_slot = Slot(GENESIS_SLOT + get_slot_from_time_ms(store, time_ms))
    while get_current_slot(store) < tick_slot:
        previous_time_ms = get_time_at_slot_end_ms(store, Slot(get_current_slot(store)))
        on_tick_per_slot_ms(store, previous_time_ms)
    on_tick_per_slot_ms(store, time_ms)
```

### Modified `on_tick`

```python
def on_tick(store: Store, time: Uint64) -> None:
    # [Modified in EIP8198]
    on_tick_ms(store, seconds_to_milliseconds(time))
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
