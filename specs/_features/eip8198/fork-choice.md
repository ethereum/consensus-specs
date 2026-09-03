# EIP-8198 -- Beacon Chain Fork Choice

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Helpers](#helpers)
  - [Modified `Store`](#modified-store)
  - [Modified `get_forkchoice_store`](#modified-get_forkchoice_store)
  - [New `get_slot_from_time_ms`](#new-get_slot_from_time_ms)
  - [New `get_time_at_slot_end_ms`](#new-get_time_at_slot_end_ms)
  - [New `get_time_into_slot_ms`](#new-get_time_into_slot_ms)
  - [Modified `get_slots_since_genesis`](#modified-get_slots_since_genesis)
  - [Modified `get_attestation_due_ms`](#modified-get_attestation_due_ms)
  - [Modified `get_proposer_reorg_cutoff_ms`](#modified-get_proposer_reorg_cutoff_ms)
  - [Modified `get_aggregate_due_ms`](#modified-get_aggregate_due_ms)
  - [Modified `get_sync_message_due_ms`](#modified-get_sync_message_due_ms)
  - [Modified `get_contribution_due_ms`](#modified-get_contribution_due_ms)
  - [Modified `get_payload_due_ms`](#modified-get_payload_due_ms)
  - [Modified `get_payload_attestation_due_ms`](#modified-get_payload_attestation_due_ms)
  - [Modified `get_inclusion_list_due_ms`](#modified-get_inclusion_list_due_ms)
  - [Proposer head and reorg helpers](#proposer-head-and-reorg-helpers)
    - [Modified `is_proposing_on_time`](#modified-is_proposing_on_time)
  - [`on_tick` helpers](#on_tick-helpers)
    - [New `on_tick_per_slot_ms`](#new-on_tick_per_slot_ms)
  - [`on_block` helpers](#on_block-helpers)
    - [Modified `record_block_timeliness`](#modified-record_block_timeliness)
- [Handlers](#handlers)
  - [New `on_tick_ms`](#new-on_tick_ms)
  - [Modified `on_tick`](#modified-on_tick)
  - [Modified `on_inclusion_list`](#modified-on_inclusion_list)

<!-- mdformat-toc end -->

## Introduction

EIP-8198 makes the slot duration change per `SLOT_DURATION_SCHEDULE`. Intra-slot
deadlines are read from the schedule entry in effect at a duty's slot, so the
deadline helpers gain a `slot` parameter; the inherited basis-point deadlines
apply before the first schedule entry. The mapping between wall-clock time and
slot number becomes piecewise over the schedule's eras, and every timeliness
check is rebased on the new `get_time_into_slot_ms` helper. The store clock
gains millisecond precision: implementations MUST drive the store with
`on_tick_ms`; the whole-second `on_tick` remains only as a compatibility
adapter.

*Note*: This specification is built upon [Heze](../../heze/fork-choice.md).

## Helpers

### Modified `Store`

*Note*: `time_ms`, at millisecond precision, replaces `time` as the store clock.

```python
@dataclass
class Store:
    # [Modified in EIP8198]
    # Removed `time`
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
    block_timeliness: Dict[Root, list[bool]] = field(default_factory=dict)
    checkpoint_states: Dict[Checkpoint, BeaconState] = field(default_factory=dict)
    latest_messages: Dict[ValidatorIndex, LatestMessage] = field(default_factory=dict)
    unrealized_justifications: Dict[Root, Checkpoint] = field(default_factory=dict)
    payloads: Dict[Root, ExecutionPayloadEnvelope] = field(default_factory=dict)
    payload_timeliness_vote: Dict[Root, list[Optional[Boolean]]] = field(default_factory=dict)
    payload_data_availability_vote: Dict[Root, list[Optional[Boolean]]] = field(
        default_factory=dict
    )
    payload_inclusion_list_satisfaction: Dict[Root, bool] = field(default_factory=dict)
```

### Modified `get_forkchoice_store`

*Note*: The anchor state may already be past a slot duration change, e.g. on
checkpoint sync, so the initial store time is derived from the piecewise
timeline.

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
        # Removed `time`
        # [New in EIP8198]
        time_ms=compute_slot_start_time_ms(anchor_state.genesis_time, anchor_state.slot),
        genesis_time=anchor_state.genesis_time,
        justified_checkpoint=justified_checkpoint,
        finalized_checkpoint=finalized_checkpoint,
        unrealized_justified_checkpoint=justified_checkpoint,
        unrealized_finalized_checkpoint=finalized_checkpoint,
        proposer_boost_root=proposer_boost_root,
        equivocating_indices=set(),
        blocks={anchor_root: copy(anchor_block)},
        block_states={anchor_root: copy(anchor_state)},
        block_timeliness={anchor_root: [True, True]},
        checkpoint_states={justified_checkpoint: copy(anchor_state)},
        unrealized_justifications={anchor_root: justified_checkpoint},
        payloads={},
        payload_timeliness_vote={anchor_root: [None] * PTC_SIZE},
        payload_data_availability_vote={anchor_root: [None] * PTC_SIZE},
        payload_inclusion_list_satisfaction={},
    )
```

### New `get_slot_from_time_ms`

```python
def get_slot_from_time_ms(store: Store, time_ms: Uint64) -> int:
    """
    Return the number of slots since genesis corresponding to ``time_ms``.
    """
    return compute_slot_at_time_ms(store.genesis_time, time_ms) - GENESIS_SLOT
```

### New `get_time_at_slot_end_ms`

```python
def get_time_at_slot_end_ms(store: Store, slot: Slot) -> Uint64:
    """
    Return the Unix time in milliseconds at the end of ``slot``.
    """
    return compute_slot_start_time_ms(store.genesis_time, Slot(slot + 1))
```

### New `get_time_into_slot_ms`

```python
def get_time_into_slot_ms(store: Store) -> Uint64:
    """
    Return the milliseconds elapsed since the start of the current slot.
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

### Modified `get_attestation_due_ms`

*Note*: This helper and the deadline helpers below gain a `slot` parameter,
since the deadline of a duty is read from the schedule entry in effect at its
slot.

```python
def get_attestation_due_ms(slot: Slot) -> Uint64:
    # [Modified in EIP8198]
    # Added `slot`
    return get_slot_timing_parameters(compute_epoch_at_slot(slot)).attestation_due_ms
```

### Modified `get_proposer_reorg_cutoff_ms`

```python
def get_proposer_reorg_cutoff_ms(slot: Slot) -> Uint64:
    # [Modified in EIP8198]
    # Added `slot`
    return get_slot_timing_parameters(compute_epoch_at_slot(slot)).proposer_reorg_cutoff_ms
```

### Modified `get_aggregate_due_ms`

```python
def get_aggregate_due_ms(slot: Slot) -> Uint64:
    # [Modified in EIP8198]
    # Added `slot`
    return get_slot_timing_parameters(compute_epoch_at_slot(slot)).aggregate_due_ms
```

### Modified `get_sync_message_due_ms`

```python
def get_sync_message_due_ms(slot: Slot) -> Uint64:
    # [Modified in EIP8198]
    # Added `slot`
    return get_slot_timing_parameters(compute_epoch_at_slot(slot)).sync_message_due_ms
```

### Modified `get_contribution_due_ms`

```python
def get_contribution_due_ms(slot: Slot) -> Uint64:
    # [Modified in EIP8198]
    # Added `slot`
    return get_slot_timing_parameters(compute_epoch_at_slot(slot)).contribution_due_ms
```

### Modified `get_payload_due_ms`

```python
def get_payload_due_ms(slot: Slot) -> Uint64:
    # [Modified in EIP8198]
    # Added `slot`
    return get_slot_timing_parameters(compute_epoch_at_slot(slot)).payload_due_ms
```

### Modified `get_payload_attestation_due_ms`

```python
def get_payload_attestation_due_ms(slot: Slot) -> Uint64:
    # [Modified in EIP8198]
    # Added `slot`
    return get_slot_timing_parameters(compute_epoch_at_slot(slot)).payload_attestation_due_ms
```

### Modified `get_inclusion_list_due_ms`

```python
def get_inclusion_list_due_ms(slot: Slot) -> Uint64:
    # [Modified in EIP8198]
    # Added `slot`
    return get_slot_timing_parameters(compute_epoch_at_slot(slot)).inclusion_list_due_ms
```

### Proposer head and reorg helpers

#### Modified `is_proposing_on_time`

```python
def is_proposing_on_time(store: Store) -> bool:
    # [Modified in EIP8198]
    time_into_slot_ms = get_time_into_slot_ms(store)
    proposer_reorg_cutoff_ms = get_proposer_reorg_cutoff_ms(get_current_slot(store))
    return time_into_slot_ms <= proposer_reorg_cutoff_ms
```

### `on_tick` helpers

#### New `on_tick_per_slot_ms`

```python
def on_tick_per_slot_ms(store: Store, time_ms: Uint64) -> None:
    previous_slot = get_current_slot(store)

    # Update store time
    store.time_ms = time_ms

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

### `on_block` helpers

#### Modified `record_block_timeliness`

```python
def record_block_timeliness(store: Store, root: Root) -> None:
    block = store.blocks[root]
    # [Modified in EIP8198]
    time_into_slot_ms = get_time_into_slot_ms(store)
    attestation_threshold_ms = get_attestation_due_ms(get_current_slot(store))
    is_current_slot = get_current_slot(store) == block.slot
    ptc_threshold_ms = get_payload_attestation_due_ms(get_current_slot(store))
    store.block_timeliness[root] = [
        is_current_slot and time_into_slot_ms < threshold
        for threshold in [attestation_threshold_ms, ptc_threshold_ms]
    ]
```

## Handlers

### New `on_tick_ms`

```python
def on_tick_ms(store: Store, time_ms: Uint64) -> None:
    # If the ``store.time_ms`` falls behind, while loop catches up slot by slot
    # to ensure that every previous slot is processed with ``on_tick_per_slot_ms``
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

```python
def on_inclusion_list(store: Store, signed_inclusion_list: SignedInclusionList) -> None:
    """
    Run ``on_inclusion_list`` upon receiving a new inclusion list.
    """
    inclusion_list = signed_inclusion_list.message
    current_slot = get_current_slot(store)

    # The transactions must be non-empty and not exceed the maximum size
    transactions_size = sum(len(transaction) for transaction in inclusion_list.transactions)
    assert transactions_size > 0
    assert transactions_size <= MAX_TRANSACTIONS_BYTES_PER_INCLUSION_LIST

    # Every transaction must be non-empty
    assert all(len(transaction) > 0 for transaction in inclusion_list.transactions)

    # The slot must be within the retention window
    assert inclusion_list.slot <= current_slot
    assert inclusion_list.slot + MIN_SLOTS_FOR_INCLUSION_LISTS_REQUESTS >= current_slot

    # The dependent block must be known
    assert inclusion_list.dependent_root in store.block_states

    # Verify the validator is in the inclusion list committee
    dependent_state = copy(store.block_states[inclusion_list.dependent_root])
    if dependent_state.slot < inclusion_list.slot:
        process_slots(dependent_state, inclusion_list.slot)
    committee = get_inclusion_list_committee(dependent_state, inclusion_list.slot)
    assert inclusion_list.validator_index in committee

    # Verify the signature
    assert is_valid_inclusion_list_signature(dependent_state, signed_inclusion_list)

    # The inclusion list is timely if it arrives in its slot before the deadline
    # [Modified in EIP8198]
    time_into_slot_ms = get_time_into_slot_ms(store)
    is_current_slot = inclusion_list.slot == current_slot
    is_timely = is_current_slot and time_into_slot_ms < get_inclusion_list_due_ms(current_slot)

    # Process the inclusion list
    process_inclusion_list(get_inclusion_list_store(), signed_inclusion_list, is_timely)
```
