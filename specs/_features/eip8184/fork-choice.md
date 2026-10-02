# EIP-8184 -- Fork Choice

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Configuration](#configuration)
  - [Time parameters](#time-parameters)
- [Containers](#containers)
  - [New `SealedTransactionKeyTimelinessStore`](#new-sealedtransactionkeytimelinessstore)
  - [Modified `Store`](#modified-store)
- [Helpers](#helpers)
  - [Modified `get_forkchoice_store`](#modified-get_forkchoice_store)
  - [New `get_sealed_transaction_key_message_due_ms`](#new-get_sealed_transaction_key_message_due_ms)
  - [New `get_sealed_transaction_key_vote_due_ms`](#new-get_sealed_transaction_key_vote_due_ms)
  - [New `process_sealed_transaction_key_message`](#new-process_sealed_transaction_key_message)
  - [New `process_sealed_transaction_key_timeliness_vote`](#new-process_sealed_transaction_key_timeliness_vote)
  - [New `is_key_treated_as_observed`](#new-is_key_treated_as_observed)
  - [New `record_payload_sealed_transaction_commitment_satisfaction`](#new-record_payload_sealed_transaction_commitment_satisfaction)
  - [New `is_payload_sealed_transaction_commitment_satisfied`](#new-is_payload_sealed_transaction_commitment_satisfied)
  - [Modified `should_extend_payload`](#modified-should_extend_payload)
- [Handlers](#handlers)
  - [New `on_sealed_transaction_key_message`](#new-on_sealed_transaction_key_message)
  - [New `on_sealed_transaction_key_timeliness_vote`](#new-on_sealed_transaction_key_timeliness_vote)
  - [Modified `on_execution_payload_envelope`](#modified-on_execution_payload_envelope)

<!-- mdformat-toc end -->

## Introduction

This is the modification of the fork choice accompanying the EIP-8184
(encrypted mempool) upgrade.

## Configuration

### Time parameters

| Name                                       | Value          |     Unit     |          Duration          |
| ------------------------------------------ | -------------- | :----------: | :------------------------: |
| `SEALED_TRANSACTION_KEY_MESSAGE_DUE_BPS`   | `uint64(7500)` | basis points | ~75% of `SLOT_DURATION_MS` |
| `SEALED_TRANSACTION_KEY_VOTE_DUE_BPS`      | `uint64(8000)` | basis points | ~80% of `SLOT_DURATION_MS` |

*Note*: `SEALED_TRANSACTION_KEY_VOTE_DUE_BPS` MUST be strictly greater
than `INCLUSION_LIST_DUE_BPS` (heze: 6667) and
`SEALED_TRANSACTION_KEY_MESSAGE_DUE_BPS`, and strictly less than the
payload timeliness deadline.

## Containers

### New `SealedTransactionKeyTimelinessStore`

```python
@dataclass
class SealedTransactionKeyTimelinessStore:
    key_messages: DefaultDict[Root, Dict[uint8, SealedTransactionKeyMessage]] = field(
        default_factory=lambda: defaultdict(dict)
    )
    key_message_timeliness: DefaultDict[Root, Dict[uint8, boolean]] = field(
        default_factory=lambda: defaultdict(dict)
    )
    timeliness_votes: DefaultDict[Root, Dict[ValidatorIndex, SignedSealedTransactionKeyTimelinessVote]] = field(
        default_factory=lambda: defaultdict(dict)
    )
    timely_votes: DefaultDict[Root, Dict[ValidatorIndex, SignedSealedTransactionKeyTimelinessVote]] = field(
        default_factory=lambda: defaultdict(dict)
    )
    equivocators: DefaultDict[Root, Set[ValidatorIndex]] = field(
        default_factory=lambda: defaultdict(set)
    )
```

### Modified `Store`

*Note*: `Store` is modified to track whether the execution payloads
satisfy the sealed-transaction commitment constraints introduced by
this upgrade, in addition to the existing inclusion list satisfaction
tracking.

```python
@dataclass
class Store:
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
    block_timeliness: Dict[Root, list[boolean]] = field(default_factory=dict)
    checkpoint_states: Dict[Checkpoint, BeaconState] = field(default_factory=dict)
    latest_messages: Dict[ValidatorIndex, LatestMessage] = field(default_factory=dict)
    unrealized_justifications: Dict[Root, Checkpoint] = field(default_factory=dict)
    payloads: Dict[Root, ExecutionPayloadEnvelope] = field(default_factory=dict)
    payload_timeliness_vote: Dict[Root, list[Optional[boolean]]] = field(default_factory=dict)
    payload_data_availability_vote: Dict[Root, list[Optional[boolean]]] = field(
        default_factory=dict
    )
    payload_inclusion_list_satisfaction: Dict[Root, boolean] = field(default_factory=dict)
    # [New in EIP8184]
    payload_sealed_transaction_commitment_satisfaction: Dict[Root, boolean] = field(default_factory=dict)
```

## Helpers

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
        time=uint64(anchor_state.genesis_time + SLOT_DURATION_MS * anchor_state.slot // 1000),
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
        payload_timeliness_vote={},
        payload_data_availability_vote={},
        payload_inclusion_list_satisfaction={},
        # [New in EIP8184]
        payload_sealed_transaction_commitment_satisfaction={},
    )
```

### New `get_sealed_transaction_key_message_due_ms`

```python
def get_sealed_transaction_key_message_due_ms() -> uint64:
    return get_slot_component_duration_ms(SEALED_TRANSACTION_KEY_MESSAGE_DUE_BPS)
```

### New `get_sealed_transaction_key_vote_due_ms`

```python
def get_sealed_transaction_key_vote_due_ms() -> uint64:
    return get_slot_component_duration_ms(SEALED_TRANSACTION_KEY_VOTE_DUE_BPS)
```

### New `process_sealed_transaction_key_message`

```python
def process_sealed_transaction_key_message(
    store: SealedTransactionKeyTimelinessStore,
    key_message: SealedTransactionKeyMessage,
    is_timely: bool,
) -> None:
    """
    Record ``key_message`` in the timeliness store, deduplicating on
    ``(scheduling_beacon_block_root, commit_index)``.
    """
    key = key_message.scheduling_beacon_block_root
    index = key_message.commit_index

    if index in store.key_messages[key]:
        return

    store.key_messages[key][index] = key_message
    store.key_message_timeliness[key][index] = is_timely
```

### New `process_sealed_transaction_key_timeliness_vote`

*Note*: A second distinct vote from the same validator for the same
`(scheduling_beacon_block_root, scheduling_slot)` is recorded as an
equivocation. Equivocated voters are excluded from the timeliness tally
and may be treated as voting either `0` or `1` by downstream consumers.

```python
def process_sealed_transaction_key_timeliness_vote(
    store: SealedTransactionKeyTimelinessStore,
    signed_vote: SignedSealedTransactionKeyTimelinessVote,
    is_timely: bool,
) -> None:
    message = signed_vote.message
    key = message.scheduling_beacon_block_root
    validator = message.validator_index

    if validator in store.equivocators[key]:
        return

    if validator in store.timeliness_votes[key]:
        stored = store.timeliness_votes[key][validator]
        if stored.message != message:
            store.equivocators[key].add(validator)
        return

    store.timeliness_votes[key][validator] = signed_vote
    if is_timely:
        store.timely_votes[key][validator] = signed_vote
```

### New `is_key_treated_as_observed`

*Note*: Mirrors the EIP's tally logic for whether the builder of the
next slot can treat a scheduled sealed-transaction commitment's key as
observed. Returns `True` if the observed-side majority exceeds half of
the total tallied PTC voters, counting equivocators on the observed
side.

```python
def is_key_treated_as_observed(
    store: SealedTransactionKeyTimelinessStore,
    scheduling_beacon_block_root: Root,
    commit_index: uint8,
) -> bool:
    key = scheduling_beacon_block_root

    def voted_observed(vote: SignedSealedTransactionKeyTimelinessVote) -> bool:
        bits = vote.message.keys_observed
        return commit_index < len(bits) and bits[commit_index]

    timely_1 = sum(1 for v in store.timely_votes[key].values() if voted_observed(v))
    total_1 = sum(1 for v in store.timeliness_votes[key].values() if voted_observed(v))
    total = len(store.timeliness_votes[key])
    late_1 = total_1 - timely_1
    equivocated = len(store.equivocators[key])

    numerator = 2 * (timely_1 + late_1 + equivocated)
    denominator = timely_1 + (total - total_1) + late_1 + equivocated
    return numerator > denominator
```

### New `record_payload_sealed_transaction_commitment_satisfaction`

*Note*: Whether a payload satisfies its sealed-transaction commitment
constraints MUST NOT affect payload validation. A valid payload that
fails to satisfy those constraints remains valid, but fork choice does
not extend it.

```python
def record_payload_sealed_transaction_commitment_satisfaction(
    store: Store,
    state: BeaconState,
    root: Root,
    payload: ExecutionPayload,
    execution_engine: ExecutionEngine,
) -> None:
    is_satisfied = execution_engine.is_sealed_transaction_commitment_satisfied(
        payload, state.latest_execution_payload_bid.sealed_transaction_commitments
    )
    store.payload_sealed_transaction_commitment_satisfaction[root] = is_satisfied
```

### New `is_payload_sealed_transaction_commitment_satisfied`

```python
def is_payload_sealed_transaction_commitment_satisfied(store: Store, root: Root) -> bool:
    """
    Return whether the execution payload for the beacon block with root
    ``root`` satisfied its sealed-transaction commitment constraints.
    """
    assert root in store.payload_sealed_transaction_commitment_satisfaction

    if not is_payload_verified(store, root):
        return False

    return store.payload_sealed_transaction_commitment_satisfaction[root]
```

### Modified `should_extend_payload`

*Note*: `should_extend_payload` is modified to not extend a payload if
it does not satisfy the sealed-transaction commitment constraints
introduced by this upgrade.

```python
def should_extend_payload(store: Store, root: Root) -> bool:
    assert store.blocks[root].slot + 1 == get_current_slot(store)
    if not is_payload_verified(store, root):
        return False
    if not is_payload_inclusion_list_satisfied(store, root):
        return False
    # [New in EIP8184]
    if not is_payload_sealed_transaction_commitment_satisfied(store, root):
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

## Handlers

### New `on_sealed_transaction_key_message`

```python
def on_sealed_transaction_key_message(
    store: Store, key_message: SealedTransactionKeyMessage
) -> None:
    """
    Run ``on_sealed_transaction_key_message`` upon receiving a new
    sealed-transaction key message.
    """
    seconds_since_genesis = store.time - store.genesis_time
    time_into_slot_ms = seconds_to_milliseconds(seconds_since_genesis) % SLOT_DURATION_MS
    due_ms = get_sealed_transaction_key_message_due_ms()
    is_timely = time_into_slot_ms < due_ms

    process_sealed_transaction_key_message(
        get_sealed_transaction_key_timeliness_store(), key_message, is_timely
    )
```

### New `on_sealed_transaction_key_timeliness_vote`

```python
def on_sealed_transaction_key_timeliness_vote(
    store: Store, signed_vote: SignedSealedTransactionKeyTimelinessVote
) -> None:
    """
    Run ``on_sealed_transaction_key_timeliness_vote`` upon receiving a
    new vote.
    """
    seconds_since_genesis = store.time - store.genesis_time
    time_into_slot_ms = seconds_to_milliseconds(seconds_since_genesis) % SLOT_DURATION_MS
    due_ms = get_sealed_transaction_key_vote_due_ms()
    is_timely = time_into_slot_ms < due_ms

    process_sealed_transaction_key_timeliness_vote(
        get_sealed_transaction_key_timeliness_store(), signed_vote, is_timely
    )
```

### Modified `on_execution_payload_envelope`

```python
def on_execution_payload_envelope(
    store: Store, signed_envelope: SignedExecutionPayloadEnvelope
) -> None:
    """
    Run ``on_execution_payload_envelope`` upon receiving a new execution
    payload envelope.
    """
    envelope = signed_envelope.message
    assert envelope.beacon_block_root in store.block_states
    assert is_data_available(envelope.beacon_block_root)

    state = store.block_states[envelope.beacon_block_root]

    verify_execution_payload_envelope(state, signed_envelope, EXECUTION_ENGINE)

    record_payload_inclusion_list_satisfaction(
        store, state, envelope.beacon_block_root, envelope.payload, EXECUTION_ENGINE
    )

    # [New in EIP8184]
    record_payload_sealed_transaction_commitment_satisfaction(
        store, state, envelope.beacon_block_root, envelope.payload, EXECUTION_ENGINE
    )

    store.payloads[envelope.beacon_block_root] = envelope
```
