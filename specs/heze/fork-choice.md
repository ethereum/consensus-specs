# Heze -- Fork Choice

*Note*: This document is a work-in-progress for researchers and implementers.

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
  - [New `get_inclusion_list_due_ms`](#new-get_inclusion_list_due_ms)
- [Handlers](#handlers)
  - [New `on_inclusion_list`](#new-on_inclusion_list)
  - [Modified `on_execution_payload_envelope`](#modified-on_execution_payload_envelope)

<!-- mdformat-toc end -->

## Introduction

This is the modification of the fork choice accompanying the Heze upgrade.

## Configuration

### Time parameters

| Name                     | Value          | Duration                   |
| ------------------------ | -------------- | -------------------------- |
| `INCLUSION_LIST_DUE_BPS` | `Uint64(6667)` | ~67% of `SLOT_DURATION_MS` |

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
class PayloadAttributes:
    timestamp: Uint64
    prev_randao: Bytes32
    suggested_fee_recipient: ExecutionAddress
    withdrawals: Sequence[Withdrawal]
    parent_beacon_block_root: Root
    slot_number: Uint64
    target_gas_limit: Uint64
    # [New in Heze:EIP7805]
    inclusion_list_transactions: Sequence[Transaction]
```

### Modified `Store`

*Note*: `Store` is modified to track whether the execution payloads satisfy the
inclusion list constraints.

```python
@dataclass
class Store:
    time: Uint64
    genesis_time: Uint64
    justified_checkpoint: Checkpoint
    finalized_checkpoint: Checkpoint
    unrealized_justified_checkpoint: Checkpoint
    unrealized_finalized_checkpoint: Checkpoint
    proposer_boost_root: Root
    equivocating_indices: Set[ValidatorIndex]
    blocks: Dict[Root, BeaconBlock]
    block_states: Dict[Root, BeaconState]
    block_timeliness: Dict[Root, list[Boolean]]
    checkpoint_states: Dict[Checkpoint, BeaconState]
    latest_messages: Dict[ValidatorIndex, LatestMessage]
    unrealized_justifications: Dict[Root, Checkpoint]
    payloads: Dict[Root, ExecutionPayloadEnvelope]
    payload_timeliness_vote: Dict[Root, list[Optional[Boolean]]]
    payload_data_availability_vote: Dict[Root, list[Optional[Boolean]]]
    # [New in Heze:EIP7805]
    payload_inclusion_list_satisfaction: Dict[Root, Boolean]
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
        time=Uint64(anchor_state.genesis_time + SLOT_DURATION_MS * anchor_state.slot // 1000),
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
        latest_messages={},
        unrealized_justifications={anchor_root: justified_checkpoint},
        payloads={},
        payload_timeliness_vote={},
        payload_data_availability_vote={},
        # [New in Heze:EIP7805]
        payload_inclusion_list_satisfaction={},
    )
```

### New `record_payload_inclusion_list_satisfaction`

*Note*: Payloads declared `VALID` by an execution engine and recorded as
satisfying the inclusion list constraints SHOULD NOT be marked as unsatisfied
even if their associated `InclusionList`s have subsequently been pruned.

*Note*: A `NOT_VALIDATED` payload is optimistically recorded as satisfying the
inclusion list constraints. When the `NOT_VALIDATED` payload transitions to
`VALID`, whether the payload satisfies the inclusion list constraints MUST be
recorded according to the
[Optimistic sync](./optimistic/optimistic.md#new-how-to-track-inclusion-list-satisfaction)
specification.

*Note*: Whether a payload satisfies the inclusion list constraints MUST NOT
affect payload validation. A valid payload that fails to satisfy those
constraints remains valid, but fork choice does not extend it.

```python
def record_payload_inclusion_list_satisfaction(
    store: Store,
    state: BeaconState,
    root: Root,
    payload: ExecutionPayload,
    execution_engine: ExecutionEngine,
) -> None:
    inclusion_list_transactions = get_inclusion_list_transactions(
        get_inclusion_list_store(), state, Slot(state.slot - 1), only_timely=True
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
    if not is_payload_verified(store, root):
        return False

    return store.payload_inclusion_list_satisfaction[root]
```

### Modified `should_extend_payload`

*Note*: `should_extend_payload` is modified to not extend a payload if it does
not satisfy the inclusion list constraints.

```python
def should_extend_payload(store: Store, root: Root) -> bool:
    assert store.blocks[root].slot + 1 == get_current_slot(store)
    if not is_payload_verified(store, root):
        return False
    # [New in Heze:EIP7805]
    if not is_payload_inclusion_list_satisfied(store, root):
        return False
    proposer_root = store.proposer_boost_root
    payload_is_timely = payload_timeliness(store, root, timely=True)
    payload_data_is_available = payload_data_availability(store, root, available=True)
    return (
        (payload_is_timely and payload_data_is_available)
        or proposer_root == Root()
        or store.blocks[proposer_root].parent_root != root
        or is_parent_node_full(store, store.blocks[proposer_root])
    )
```

### New `get_inclusion_list_due_ms`

```python
def get_inclusion_list_due_ms() -> Uint64:
    return get_slot_component_duration_ms(INCLUSION_LIST_DUE_BPS)
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
    current_slot = get_current_slot(store)

    # The transactions must not exceed the maximum size
    transactions_size = sum(len(transaction) for transaction in inclusion_list.transactions)
    assert transactions_size <= MAX_TRANSACTIONS_BYTES_PER_INCLUSION_LIST

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
    seconds_since_genesis = store.time - store.genesis_time
    time_into_slot_ms = seconds_to_milliseconds(seconds_since_genesis) % SLOT_DURATION_MS
    is_current_slot = inclusion_list.slot == current_slot
    is_timely = is_current_slot and time_into_slot_ms < get_inclusion_list_due_ms()

    # Process the inclusion list
    process_inclusion_list(
        get_inclusion_list_store(),
        signed_inclusion_list,
        hash_tree_root(committee),
        is_timely,
    )
```

### Modified `on_execution_payload_envelope`

```python
def on_execution_payload_envelope(
    store: Store, signed_envelope: SignedExecutionPayloadEnvelope
) -> None:
    """
    Run ``on_execution_payload_envelope`` upon receiving a new execution payload envelope.
    """
    envelope = signed_envelope.message
    # The corresponding beacon block root needs to be known
    assert envelope.beacon_block_root in store.block_states

    # Check if blob data is available
    # If not, this payload MAY be queued and subsequently considered when blob data becomes available
    assert is_data_available(envelope.beacon_block_root)

    state = store.block_states[envelope.beacon_block_root]

    # Verify the execution payload envelope
    verify_execution_payload_envelope(state, signed_envelope, EXECUTION_ENGINE)

    # [New in Heze:EIP7805]
    # Check if this payload satisfies the inclusion list constraints
    # If not, add this payload to the store as inclusion list constraints unsatisfied
    record_payload_inclusion_list_satisfaction(
        store, state, envelope.beacon_block_root, envelope.payload, EXECUTION_ENGINE
    )

    # Add execution payload envelope to the store
    store.payloads[envelope.beacon_block_root] = envelope
```
