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
  - [New `validate_inclusion_lists`](#new-validate_inclusion_lists)
  - [New `get_attester_head`](#new-get_attester_head)
  - [Modified `get_proposer_head`](#modified-get_proposer_head)
- [Updated fork-choice handlers](#updated-fork-choice-handlers)
  - [New `on_inclusion_list`](#new-on_inclusion_list)
  - [Modified `on_block`](#modified-on_block)

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

The only change made is to the `PayloadAttributes` container through the
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

*Note*: `Store` is modified to track the seen inclusion lists and inclusion list
equivocators.

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
    block_timeliness: Dict[Root, boolean] = field(default_factory=dict)
    checkpoint_states: Dict[Checkpoint, BeaconState] = field(default_factory=dict)
    latest_messages: Dict[ValidatorIndex, LatestMessage] = field(default_factory=dict)
    unrealized_justifications: Dict[Root, Checkpoint] = field(default_factory=dict)
    # [New in EIP7805]
    unsatisfied_inclusion_list_blocks: Set[Root] = field(default_factory=Set)
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
        checkpoint_states={justified_checkpoint: copy(anchor_state)},
        unrealized_justifications={anchor_root: justified_checkpoint},
        # [New in EIP7805]
        unsatisfied_inclusion_list_blocks=set(),
    )
```

### New `validate_inclusion_lists`

Blocks previously validated as satisfying the inclusion list constraints SHOULD
NOT be invalidated even if their associated `InclusionList`s have subsequently
been pruned.

*Note*: Invalid or equivocating `InclusionList`s received on the p2p network
MUST NOT invalidate a block that is otherwise valid and satisfies the inclusion
list constraints.

```python
def validate_inclusion_lists(
    store: Store, beacon_block_root: Root, execution_engine: ExecutionEngine
) -> bool:
    inclusion_list_store = get_inclusion_list_store()

    block = store.blocks[beacon_block_root]
    state = store.block_states[beacon_block_root]

    inclusion_list_transactions = get_inclusion_list_transactions(
        inclusion_list_store, state, Slot(block.slot - 1)
    )

    return execution_engine.is_inclusion_list_satisfied(
        block.body.execution_payload, inclusion_list_transactions
    )
```

### New `get_attester_head`

```python
def get_attester_head(store: Store, head_root: Root) -> Root:
    if head_root in store.unsatisfied_inclusion_list_blocks:
        head_block = store.blocks[head_root]
        return head_block.parent_root

    return head_root
```

### Modified `get_proposer_head`

The implementation of `get_proposer_head` is modified to also account for
`store.unsatisfied_inclusion_list_blocks`.

```python
def get_proposer_head(store: Store, head_root: Root, slot: Slot) -> Root:
    head_block = store.blocks[head_root]
    parent_root = head_block.parent_root
    parent_block = store.blocks[parent_root]

    # Only re-org the head block if it arrived later than the attestation deadline.
    head_late = is_head_late(store, head_root)

    # Do not re-org on an epoch boundary where the proposer shuffling could change.
    shuffling_stable = is_shuffling_stable(slot)

    # Ensure that the FFG information of the new head will be competitive with the current head.
    ffg_competitive = is_ffg_competitive(store, head_root, parent_root)

    # Do not re-org if the chain is not finalizing with acceptable frequency.
    finalization_ok = is_finalization_ok(store, slot)

    # Only re-org if we are proposing on-time.
    proposing_on_time = is_proposing_on_time(store)

    # Only re-org a single slot at most.
    parent_slot_ok = parent_block.slot + 1 == head_block.slot
    current_time_ok = head_block.slot + 1 == slot
    single_slot_reorg = parent_slot_ok and current_time_ok

    # Check that the head has few enough votes to be overpowered by our proposer boost.
    assert store.proposer_boost_root != head_root  # ensure boost has worn off
    head_weak = is_head_weak(store, head_root)

    # Check that the missing votes are assigned to the parent and not being hoarded.
    parent_strong = is_parent_strong(store, parent_root)

    reorg_prerequisites = all(
        [
            shuffling_stable,
            ffg_competitive,
            finalization_ok,
            proposing_on_time,
            single_slot_reorg,
            head_weak,
            parent_strong,
        ]
    )

    # [New in EIP7805]
    # Check that the head block is in the unsatisfied inclusion list blocks
    inclusion_list_not_satisfied = head_root in store.unsatisfied_inclusion_list_blocks

    if reorg_prerequisites and (head_late or inclusion_list_not_satisfied):
        return parent_root
    else:
        return head_root
```

## Updated fork-choice handlers

### New `on_inclusion_list`

*Note*: A new handler `on_inclusion_list` is called whenever an inclusion list
is received. Any call to this handler that triggers an unhandled exception
(e.g., a failed assert or an out-of-range list access) is considered invalid and
MUST NOT modify the store.

```python
def on_inclusion_list(store: Store, signed_inclusion_list: SignedInclusionList) -> None:
    """
    Run ``on_inclusion_list`` upon receiving a new inclusion list.
    """
    inclusion_list = signed_inclusion_list.message

    inclusion_list_store = get_inclusion_list_store()

    seconds_since_genesis = store.time - store.genesis_time
    time_into_slot_ms = seconds_to_milliseconds(seconds_since_genesis) % SLOT_DURATION_MS
    view_freeze_deadline_ms = get_slot_component_duration_ms(VIEW_FREEZE_CUTOFF_BPS)
    is_before_view_freeze_deadline = time_into_slot_ms < view_freeze_deadline_ms

    process_inclusion_list(inclusion_list_store, inclusion_list, is_before_view_freeze_deadline)
```

### Modified `on_block`

*Note*: `on_block` is modified to add the given block that does not satisfy the
inclusion list constraints to `store.unsatisfied_inclusion_list_blocks` and to
avoid applying a proposer score boost to the block.

```python
def on_block(store: Store, signed_block: SignedBeaconBlock) -> None:
    """
    Run ``on_block`` upon receiving a new block.
    """
    block = signed_block.message
    # Parent block must be known
    assert block.parent_root in store.block_states
    # Blocks cannot be in the future. If they are, their consideration must be delayed until they are in the past.
    assert get_current_slot(store) >= block.slot

    # Check that block is later than the finalized epoch slot (optimization to reduce calls to get_ancestor)
    finalized_slot = compute_start_slot_at_epoch(store.finalized_checkpoint.epoch)
    assert block.slot > finalized_slot
    # Check block is a descendant of the finalized block at the checkpoint finalized slot
    finalized_checkpoint_block = get_checkpoint_block(
        store,
        block.parent_root,
        store.finalized_checkpoint.epoch,
    )
    assert store.finalized_checkpoint.root == finalized_checkpoint_block

    # Check if blob data is available
    # If not, this block MAY be queued and subsequently considered when blob data becomes available
    # *Note*: Extraneous or invalid Blobs (in addition to the expected/referenced valid blobs)
    # received on the p2p network MUST NOT invalidate a block that is otherwise valid and available
    assert is_data_available(hash_tree_root(block), block.body.blob_kzg_commitments)

    # Check the block is valid and compute the post-state
    # Make a copy of the state to avoid mutability issues
    state = copy(store.block_states[block.parent_root])
    block_root = hash_tree_root(block)
    state_transition(state, signed_block, True)

    # Add new block to the store
    store.blocks[block_root] = block
    # Add new state for this block to the store
    store.block_states[block_root] = state

    # Add block timeliness to the store
    seconds_since_genesis = store.time - store.genesis_time
    time_into_slot_ms = seconds_to_milliseconds(seconds_since_genesis) % SLOT_DURATION_MS
    attestation_threshold_ms = get_slot_component_duration_ms(ATTESTATION_DUE_BPS)
    is_before_attesting_interval = time_into_slot_ms < attestation_threshold_ms
    is_timely = get_current_slot(store) == block.slot and is_before_attesting_interval
    store.block_timeliness[hash_tree_root(block)] = is_timely

    # [New in EIP7805]
    # Check if block satisfies the inclusion list constraints
    # If not, add this block to the store as inclusion list constraints unsatisfied
    is_inclusion_list_satisfied = validate_inclusion_lists(store, block_root, EXECUTION_ENGINE)
    if not is_inclusion_list_satisfied:
        store.unsatisfied_inclusion_list_blocks.add(block_root)

    # Add proposer score boost if the block is timely, not conflicting with an existing block
    # and satisfies the inclusion list constraints.
    is_first_block = store.proposer_boost_root == Root()
    # [Modified in EIP7805]
    if is_timely and is_first_block and is_inclusion_list_satisfied:
        store.proposer_boost_root = hash_tree_root(block)

    # Update checkpoints in store if necessary
    update_checkpoints(store, state.current_justified_checkpoint, state.finalized_checkpoint)

    # Eagerly compute unrealized justification and finality.
    compute_pulled_up_tip(store, block_root)
```
