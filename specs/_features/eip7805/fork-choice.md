# EIP-7805 -- Fork Choice

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Configuration](#configuration)
  - [Time parameters](#time-parameters)
- [Protocols](#protocols)
  - [`ExecutionEngine`](#executionengine)
    - [New `is_inclusion_list_satisfied`](#new-is_inclusion_list_satisfied)
    - [Modified `notify_forkchoice_updated`](#modified-notify_forkchoice_updated)
- [Helpers](#helpers)
  - [Modified `PayloadAttributes`](#modified-payloadattributes)
  - [Modified `Store`](#modified-store)
  - [Modified `get_forkchoice_store`](#modified-get_forkchoice_store)
  - [New `record_payload_inclusion_list_satisfaction`](#new-record_payload_inclusion_list_satisfaction)
  - [New `is_payload_inclusion_list_satisfied`](#new-is_payload_inclusion_list_satisfied)
  - [Modified `should_extend_payload`](#modified-should_extend_payload)
  - [New `get_view_freeze_cutoff_ms`](#new-get_view_freeze_cutoff_ms)
  - [New `get_inclusion_list_submission_due_ms`](#new-get_inclusion_list_submission_due_ms)
  - [New `get_proposer_inclusion_list_cutoff_ms`](#new-get_proposer_inclusion_list_cutoff_ms)
- [Handlers](#handlers)
  - [New `on_inclusion_list`](#new-on_inclusion_list)
  - [Modified `on_execution_payload`](#modified-on_execution_payload)

<!-- mdformat-toc end -->

## Introduction

This is the modification of the fork choice accompanying the EIP-7805 upgrade.

## Configuration

### Time parameters

| Name                     | Value          |     Unit     |         Duration          |
| ------------------------ | -------------- | :----------: | :-----------------------: |
| `VIEW_FREEZE_CUTOFF_BPS` | `uint64(7500)` | basis points | 75% of `SLOT_DURATION_MS` |

## Protocols

### `ExecutionEngine`

*Note*: The `is_inclusion_list_satisfied` function is added to the
`ExecutionEngine` protocol to instantiate the inclusion list constraints
validation.

The body of this function is implementation dependent. The Engine API may be
used to implement it with an external execution engine.

#### New `is_inclusion_list_satisfied`

```python
def is_inclusion_list_satisfied(
    self: ExecutionEngine,
    execution_payload: ExecutionPayload,
    inclusion_list_transactions: Sequence[Transaction],
) -> bool:
    """
    Return ``True`` if and only if ``execution_payload`` satisfies the inclusion
    list constraints with respect to ``inclusion_list_transactions``.
    """
    ...
```

#### Modified `notify_forkchoice_updated`

*Note*: The only change made is to the `PayloadAttributes` container through the
addition of `inclusion_list_transactions`. Otherwise,
`notify_forkchoice_updated` inherits all prior functionality.

*Note*: If the `inclusion_list_transactions` field of `payload_attributes` is
not empty, the payload build process MUST produce an execution payload that
satisfies the inclusion list constraints with respect to
`inclusion_list_transactions`.

```python
def notify_forkchoice_updated(
    self: ExecutionEngine,
    head_block_hash: Hash32,
    safe_block_hash: Hash32,
    finalized_block_hash: Hash32,
    payload_attributes: Optional[PayloadAttributes],
) -> Optional[PayloadId]: ...
```

## Helpers

### Modified `PayloadAttributes`

`PayloadAttributes` is extended with the `inclusion_list_transactions` field.

```python
@dataclass
class PayloadAttributes(object):
    timestamp: uint64
    prev_randao: Bytes32
    suggested_fee_recipient: ExecutionAddress
    withdrawals: Sequence[Withdrawal]
    parent_beacon_block_root: Root
    # [New in EIP7805]
    inclusion_list_transactions: Sequence[Transaction]
```

### Modified `Store`

*Note*: `Store` is modified to track whether the execution payloads satisfy the
inclusion list constraints.

```python
@dataclass
class Store(object):
    time: uint64
    genesis_time: uint64
    justified_checkpoint: Checkpoint
    finalized_checkpoint: Checkpoint
    unrealized_justified_checkpoint: Checkpoint
    unrealized_finalized_checkpoint: Checkpoint
    proposer_boost_root: Root
    equivocating_indices: Set[ValidatorIndex]
    blocks: Dict[Root, BeaconBlock] = field(default_factory=dict)
    block_states: Dict[Root, BeaconState] = field(default_factory=dict)
    block_timeliness: Dict[Root, Vector[boolean, NUM_BLOCK_TIMELINESS_DEADLINES]] = field(
        default_factory=dict
    )
    checkpoint_states: Dict[Checkpoint, BeaconState] = field(default_factory=dict)
    latest_messages: Dict[ValidatorIndex, LatestMessage] = field(default_factory=dict)
    unrealized_justifications: Dict[Root, Checkpoint] = field(default_factory=dict)
    payload_states: Dict[Root, BeaconState] = field(default_factory=dict)
    payload_timeliness_vote: Dict[Root, Vector[boolean, PTC_SIZE]] = field(default_factory=dict)
    payload_data_availability_vote: Dict[Root, Vector[boolean, PTC_SIZE]] = field(
        default_factory=dict
    )
    # [New in EIP7805]
    payload_inclusion_list_satisfaction: Dict[Root, boolean] = field(default_factory=dict)
```

### Modified `get_forkchoice_store`

```python
def get_forkchoice_store(anchor_state: BeaconState, anchor_block: BeaconBlock) -> Store:
    assert anchor_block.state_root == hash_tree_root(anchor_state)
    anchor_root = hash_tree_root(anchor_block)
    anchor_epoch = get_current_epoch(anchor_state)
    justified_checkpoint = Checkpoint(epoch=anchor_epoch, root=anchor_root)
    finalized_checkpoint = Checkpoint(epoch=anchor_epoch, root=anchor_root)
    proposer_boost_root = Root()
    return Store(
        time=uint64(anchor_state.genesis_time + SECONDS_PER_SLOT * anchor_state.slot),
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
        payload_states={anchor_root: copy(anchor_state)},
        payload_timeliness_vote={
            anchor_root: Vector[boolean, PTC_SIZE](True for _ in range(PTC_SIZE))
        },
        payload_data_availability_vote={
            anchor_root: Vector[boolean, PTC_SIZE](True for _ in range(PTC_SIZE))
        },
        # [New in EIP7805]
        payload_inclusion_list_satisfaction={anchor_root: True},
    )
```

### New `record_payload_inclusion_list_satisfaction`

*Note*: Payloads previously validated as satisfying the inclusion list
constraints SHOULD NOT be invalidated even if their associated `InclusionList`s
have subsequently been pruned.

*Note*: Invalid or equivocating `InclusionList`s received on the p2p network
MUST NOT invalidate a payload that is otherwise valid and satisfies the
inclusion list constraints.

```python
def record_payload_inclusion_list_satisfaction(
    store: Store,
    state: BeaconState,
    root: Root,
    payload: ExecutionPayload,
    execution_engine: ExecutionEngine,
) -> None:
    inclusion_list_transactions = get_inclusion_list_transactions(
        get_inclusion_list_store(), state, Slot(state.slot - 1)
    )
    is_inclusion_list_satisfied = execution_engine.is_inclusion_list_satisfied(
        payload, inclusion_list_transactions
    )
    store.payload_inclusion_list_satisfaction[root] = is_inclusion_list_satisfied
```

### New `is_payload_inclusion_list_satisfied`

```python
def is_payload_inclusion_list_satisfied(store: Store, root: Root) -> bool:
    """
    Return whether the execution payload for the beacon block with root ``root``
    satisfied the inclusion list constraints, and was locally determined to be available.
    """
    # The beacon block root must be known
    assert root in store.payload_inclusion_list_satisfaction

    # If the payload is not locally available, the payload
    # is not considered to satisfy the inclusion list constraints
    if root not in store.payload_states:
        return False

    return store.payload_inclusion_list_satisfaction[root]
```

### Modified `should_extend_payload`

*Note*: `should_extend_payload` is modified to not extend a payload if it does
not satisfy the inclusion list constraints.

```python
def should_extend_payload(store: Store, root: Root) -> bool:
    # [New in EIP7805]
    if not is_payload_inclusion_list_satisfied(store, root):
        return False

    proposer_root = store.proposer_boost_root
    return (
        (is_payload_timely(store, root) and is_payload_data_available(store, root))
        or proposer_root == Root()
        or store.blocks[proposer_root].parent_root != root
        or is_parent_node_full(store, store.blocks[proposer_root])
    )
```

### New `get_view_freeze_cutoff_ms`

```python
def get_view_freeze_cutoff_ms(epoch: Epoch) -> uint64:
    return get_slot_component_duration_ms(VIEW_FREEZE_CUTOFF_BPS)
```

### New `get_inclusion_list_submission_due_ms`

```python
def get_inclusion_list_submission_due_ms(epoch: Epoch) -> uint64:
    return get_slot_component_duration_ms(INCLUSION_LIST_SUBMISSION_DUE_BPS)
```

### New `get_proposer_inclusion_list_cutoff_ms`

```python
def get_proposer_inclusion_list_cutoff_ms(epoch: Epoch) -> uint64:
    return get_slot_component_duration_ms(PROPOSER_INCLUSION_LIST_CUTOFF_BPS)
```

## Handlers

### New `on_inclusion_list`

*Note*: A new handler `on_inclusion_list` is called whenever an inclusion list
is received. Any call to this handler that triggers an unhandled exception
(e.g., a failed assert or an out-of-range list access) is considered invalid and
MUST NOT modify `store`.

```python
def on_inclusion_list(store: Store, signed_inclusion_list: SignedInclusionList) -> None:
    """
    Run ``on_inclusion_list`` upon receiving a new inclusion list.
    """
    inclusion_list = signed_inclusion_list.message

    seconds_since_genesis = store.time - store.genesis_time
    time_into_slot_ms = seconds_to_milliseconds(seconds_since_genesis) % SLOT_DURATION_MS
    epoch = get_current_store_epoch(store)
    view_freeze_cutoff_ms = get_view_freeze_cutoff_ms(epoch)
    is_before_view_freeze_cutoff = time_into_slot_ms < view_freeze_cutoff_ms

    process_inclusion_list(get_inclusion_list_store(), inclusion_list, is_before_view_freeze_cutoff)
```

### Modified `on_execution_payload`

```python
def on_execution_payload(store: Store, signed_envelope: SignedExecutionPayloadEnvelope) -> None:
    """
    Run ``on_execution_payload`` upon receiving a new execution payload.
    """
    envelope = signed_envelope.message
    # The corresponding beacon block root needs to be known
    assert envelope.beacon_block_root in store.block_states

    # Check if blob data is available
    # If not, this payload MAY be queued and subsequently considered when blob data becomes available
    assert is_data_available(envelope.beacon_block_root)

    # Make a copy of the state to avoid mutability issues
    state = copy(store.block_states[envelope.beacon_block_root])

    # Process the execution payload
    process_execution_payload(state, signed_envelope, EXECUTION_ENGINE)

    # [New in EIP7805]
    # Check if this payload satisfies the inclusion list constraints
    # If not, add this payload to the store as inclusion list constraints unsatisfied
    record_payload_inclusion_list_satisfaction(
        store, state, envelope.beacon_block_root, envelope.payload, EXECUTION_ENGINE
    )

    # Add new state for this payload to the store
    store.payload_states[envelope.beacon_block_root] = state
```
