# EIP-7732 -- Fork Choice

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Custom types](#custom-types)
- [Constants](#constants)
- [Containers](#containers)
  - [New `ForkChoiceNode`](#new-forkchoicenode)
  - [Modified `LatestMessage`](#modified-latestmessage)
  - [Modified `update_latest_messages`](#modified-update_latest_messages)
  - [Modified `Store`](#modified-store)
  - [Modified `get_forkchoice_store`](#modified-get_forkchoice_store)
  - [New `notify_ptc_messages`](#new-notify_ptc_messages)
  - [New `is_payload_timely`](#new-is_payload_timely)
  - [New `get_parent_payload_status`](#new-get_parent_payload_status)
  - [New `is_parent_node_full`](#new-is_parent_node_full)
  - [Modified `get_ancestor`](#modified-get_ancestor)
  - [Modified `get_checkpoint_block`](#modified-get_checkpoint_block)
  - [New `is_supporting_vote`](#new-is_supporting_vote)
  - [New `should_extend_payload`](#new-should_extend_payload)
  - [New `get_payload_status_tiebreaker`](#new-get_payload_status_tiebreaker)
  - [Modified `get_weight`](#modified-get_weight)
  - [New `get_node_children`](#new-get_node_children)
  - [Modified `get_head`](#modified-get_head)
- [Updated fork-choice handlers](#updated-fork-choice-handlers)
  - [Modified `on_block`](#modified-on_block)
- [New fork-choice handlers](#new-fork-choice-handlers)
  - [New `on_execution_payload`](#new-on_execution_payload)
  - [New `on_payload_attestation_message`](#new-on_payload_attestation_message)
  - [Modified `validate_on_attestation`](#modified-validate_on_attestation)
  - [Modified `validate_merge_block`](#modified-validate_merge_block)

<!-- mdformat-toc end -->

## Introduction

This is the modification of the fork-choice accompanying the EIP-7732 upgrade.

## Custom types

| Name            | SSZ equivalent | Description                                     |
| --------------- | -------------- | ----------------------------------------------- |
| `PayloadStatus` | `uint8`        | Possible status of a payload in the fork-choice |

## Constants

| Name                       | Value                   |
| -------------------------- | ----------------------- |
| `PAYLOAD_TIMELY_THRESHOLD` | `PTC_SIZE // 2` (= 256) |
| `INTERVALS_PER_SLOT`       | `4`                     |
| `PAYLOAD_STATUS_PENDING`   | `PayloadStatus(0)`      |
| `PAYLOAD_STATUS_EMPTY`     | `PayloadStatus(1)`      |
| `PAYLOAD_STATUS_FULL`      | `PayloadStatus(2)`      |

## Containers

### New `ForkChoiceNode`

```python
class ForkChoiceNode(Container):
    root: Root
    payload_status: PayloadStatus  # One of PAYLOAD_STATUS_* values
```

### Modified `LatestMessage`

*Note*: The class is modified to keep track of the slot instead of the epoch.

```python
@dataclass(eq=True, frozen=True)
class LatestMessage(object):
    slot: Slot
    root: Root
    payload_present: boolean
```

### Modified `update_latest_messages`

*Note*: the function `update_latest_messages` is updated to use the attestation
slot instead of target. Notice that this function is only called on validated
attestations and validators cannot attest twice in the same epoch without
equivocating. Notice also that target epoch number and slot number are validated
on `validate_on_attestation`.

```python
def update_latest_messages(
    store: Store, attesting_indices: Sequence[ValidatorIndex], attestation: Attestation
) -> None:
    slot = attestation.data.slot
    beacon_block_root = attestation.data.beacon_block_root
    payload_present = attestation.data.index == 1
    non_equivocating_attesting_indices = [
        i for i in attesting_indices if i not in store.equivocating_indices
    ]
    for i in non_equivocating_attesting_indices:
        if i not in store.latest_messages or slot > store.latest_messages[i].slot:
            store.latest_messages[i] = LatestMessage(
                slot=slot, root=beacon_block_root, payload_present=payload_present
            )
```

### Modified `Store`

*Note*: `Store` is modified to track the intermediate states of "empty"
consensus blocks, that is, those consensus blocks for which the corresponding
execution payload has not been revealed or has not been included on chain.

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
    # [New in EIP7732]
    execution_payload_states: Dict[Root, BeaconState] = field(default_factory=dict)
    # [New in EIP7732]
    ptc_vote: Dict[Root, Vector[boolean, PTC_SIZE]] = field(default_factory=dict)
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
        # [New in EIP7732]
        execution_payload_states={anchor_root: copy(anchor_state)},
        ptc_vote={anchor_root: Vector[boolean, PTC_SIZE]()},
    )
```

### New `notify_ptc_messages`

```python
def notify_ptc_messages(
    store: Store, state: BeaconState, payload_attestations: Sequence[PayloadAttestation]
) -> None:
    """
    Extracts a list of ``PayloadAttestationMessage`` from ``payload_attestations`` and updates the store with them
    These Payload attestations are assumed to be in the beacon block hence signature verification is not needed
    """
    if state.slot == 0:
        return
    for payload_attestation in payload_attestations:
        indexed_payload_attestation = get_indexed_payload_attestation(
            state, Slot(state.slot - 1), payload_attestation
        )
        for idx in indexed_payload_attestation.attesting_indices:
            on_payload_attestation_message(
                store,
                PayloadAttestationMessage(
                    validator_index=idx,
                    data=payload_attestation.data,
                    signature=BLSSignature(),
                ),
                is_from_block=True,
            )
```

### New `is_payload_timely`

```python
def is_payload_timely(store: Store, root: Root) -> bool:
    """
    Return whether the execution payload for the beacon block with root ``root``
    was voted as present by the PTC, and was locally determined to be available.
    """
    # The beacon block root must be known
    assert root in store.ptc_vote

    # If the payload is not locally available, the payload
    # is not considered available regardless of the PTC vote
    if root not in store.execution_payload_states:
        return False

    return sum(store.ptc_vote[root]) > PAYLOAD_TIMELY_THRESHOLD
```

### New `get_parent_payload_status`

```python
def get_parent_payload_status(store: Store, block: BeaconBlock) -> PayloadStatus:
    parent = store.blocks[block.parent_root]
    parent_block_hash = block.body.signed_execution_payload_header.message.parent_block_hash
    message_block_hash = parent.body.signed_execution_payload_header.message.block_hash
    return PAYLOAD_STATUS_FULL if parent_block_hash == message_block_hash else PAYLOAD_STATUS_EMPTY
```

### New `is_parent_node_full`

```python
def is_parent_node_full(store: Store, block: BeaconBlock) -> bool:
    return get_parent_payload_status(store, block) == PAYLOAD_STATUS_FULL
```

### Modified `get_ancestor`

*Note*: `get_ancestor` is modified to return whether the chain is based on an
*empty* or *full* block.

```python
def get_ancestor(store: Store, root: Root, slot: Slot) -> ForkChoiceNode:
    """
    Returns the beacon block root and the payload status of the ancestor of the beacon block
    with ``root`` at ``slot``. If the beacon block with ``root`` is already at ``slot`` or we are
    requesting an ancestor "in the future", it returns ``PAYLOAD_STATUS_PENDING``.
    """
    block = store.blocks[root]
    if block.slot <= slot:
        return ForkChoiceNode(root=root, payload_status=PAYLOAD_STATUS_PENDING)

    parent = store.blocks[block.parent_root]
    if parent.slot > slot:
        return get_ancestor(store, block.parent_root, slot)
    else:
        return ForkChoiceNode(
            root=block.parent_root,
            payload_status=get_parent_payload_status(store, block),
        )
```

### Modified `get_checkpoint_block`

*Note*: `get_checkpoint_block` is modified to use the new `get_ancestor`

```python
def get_checkpoint_block(store: Store, root: Root, epoch: Epoch) -> Root:
    """
    Compute the checkpoint block for epoch ``epoch`` in the chain of block ``root``
    """
    epoch_first_slot = compute_start_slot_at_epoch(epoch)
    return get_ancestor(store, root, epoch_first_slot).root
```

### New `is_supporting_vote`

```python
def is_supporting_vote(store: Store, node: ForkChoiceNode, message: LatestMessage) -> bool:
    """
    Returns whether a vote for ``message.root`` supports the chain containing the beacon block ``node.root`` with the
    payload contents indicated by ``node.payload_status`` as head during slot ``node.slot``.
    """
    block = store.blocks[node.root]
    if node.root == message.root:
        if node.payload_status == PAYLOAD_STATUS_PENDING:
            return True
        if message.slot <= block.slot:
            return False
        if message.payload_present:
            return node.payload_status == PAYLOAD_STATUS_FULL
        else:
            return node.payload_status == PAYLOAD_STATUS_EMPTY

    else:
        ancestor = get_ancestor(store, message.root, block.slot)
        return node.root == ancestor.root and (
            node.payload_status == PAYLOAD_STATUS_PENDING
            or node.payload_status == ancestor.payload_status
        )
```

### New `should_extend_payload`

*Note*: `should_extend_payload` decides whether to extend an available payload
from the previous slot, corresponding to the beacon block `root`. We extend it
if a majority of the PTC has voted for it. If not, we also extend it if the
proposer boost root is not set, set to something conflicting with the given
root, or to something extending the payload.

```python
def should_extend_payload(store: Store, root: Root) -> bool:
    proposer_root = store.proposer_boost_root
    return (
        is_payload_timely(store, root)
        or proposer_root == Root()
        or store.blocks[proposer_root].parent_root != root
        or is_parent_node_full(store, store.blocks[proposer_root])
    )
```

### New `get_payload_status_tiebreaker`

```python
def get_payload_status_tiebreaker(store: Store, node: ForkChoiceNode) -> uint8:
    if node.payload_status == PAYLOAD_STATUS_PENDING or store.blocks[
        node.root
    ].slot + 1 != get_current_slot(store):
        return node.payload_status
    else:
        # To decide on a payload from the previous slot, choose
        # between FULL and EMPTY based on `should_extend_payload`
        if node.payload_status == PAYLOAD_STATUS_EMPTY:
            return 1
        else:
            return 2 if should_extend_payload(store, node.root) else 0
```

### Modified `get_weight`

```python
def get_weight(store: Store, node: ForkChoiceNode) -> Gwei:
    if node.payload_status == PAYLOAD_STATUS_PENDING or store.blocks[
        node.root
    ].slot + 1 != get_current_slot(store):
        state = store.checkpoint_states[store.justified_checkpoint]
        unslashed_and_active_indices = [
            i
            for i in get_active_validator_indices(state, get_current_epoch(state))
            if not state.validators[i].slashed
        ]
        attestation_score = Gwei(
            sum(
                state.validators[i].effective_balance
                for i in unslashed_and_active_indices
                if (
                    i in store.latest_messages
                    and i not in store.equivocating_indices
                    and is_supporting_vote(store, node, store.latest_messages[i])
                )
            )
        )

        if store.proposer_boost_root == Root():
            # Return only attestation score if `proposer_boost_root` is not set
            return attestation_score

        # Calculate proposer score if `proposer_boost_root` is set
        proposer_score = Gwei(0)

        # `proposer_boost_root` is treated as a vote for the
        # proposer's block in the current slot. Proposer boost
        # is applied accordingly to all ancestors
        message = LatestMessage(
            slot=get_current_slot(store),
            root=store.proposer_boost_root,
            payload_present=False,
        )
        if is_supporting_vote(store, node, message):
            proposer_score = get_proposer_score(store)

        return attestation_score + proposer_score
    else:
        return Gwei(0)
```

### New `get_node_children`

```python
def get_node_children(
    store: Store, blocks: Dict[Root, BeaconBlock], node: ForkChoiceNode
) -> Sequence[ForkChoiceNode]:
    if node.payload_status == PAYLOAD_STATUS_PENDING:
        children = [ForkChoiceNode(root=node.root, payload_status=PAYLOAD_STATUS_EMPTY)]
        if node.root in store.execution_payload_states:
            children.append(ForkChoiceNode(root=node.root, payload_status=PAYLOAD_STATUS_FULL))
        return children
    else:
        return [
            ForkChoiceNode(root=root, payload_status=PAYLOAD_STATUS_PENDING)
            for root in blocks.keys()
            if (
                blocks[root].parent_root == node.root
                and node.payload_status == get_parent_payload_status(store, blocks[root])
            )
        ]
```

### Modified `get_head`

*Note*: `get_head` is a modified to use the new `get_weight` function. It
returns the `ForkChoiceNode` object corresponding to the head block.

```python
def get_head(store: Store) -> ForkChoiceNode:
    # Get filtered block tree that only includes viable branches
    blocks = get_filtered_block_tree(store)
    # Execute the LMD-GHOST fork-choice
    head = ForkChoiceNode(
        root=store.justified_checkpoint.root,
        payload_status=PAYLOAD_STATUS_PENDING,
    )

    while True:
        children = get_node_children(store, blocks, head)
        if len(children) == 0:
            return head
        # Sort by latest attesting balance with ties broken lexicographically
        head = max(
            children,
            key=lambda child: (
                get_weight(store, child),
                child.root,
                get_payload_status_tiebreaker(store, child),
            ),
        )
```

## Updated fork-choice handlers

### Modified `on_block`

*Note*: The handler `on_block` is modified to consider the pre `state` of the
given consensus beacon block depending not only on the parent block root, but
also on the parent blockhash. In addition we delay the checking of blob data
availability until the processing of the execution payload.

```python
def on_block(store: Store, signed_block: SignedBeaconBlock) -> None:
    """
    Run ``on_block`` upon receiving a new block.
    """
    block = signed_block.message
    # Parent block must be known
    assert block.parent_root in store.block_states

    # Check if this blocks builds on empty or full parent block
    parent_block = store.blocks[block.parent_root]
    header = block.body.signed_execution_payload_header.message
    parent_header = parent_block.body.signed_execution_payload_header.message
    # Make a copy of the state to avoid mutability issues
    if is_parent_node_full(store, block):
        assert block.parent_root in store.execution_payload_states
        state = copy(store.execution_payload_states[block.parent_root])
    else:
        assert header.parent_block_hash == parent_header.parent_block_hash
        state = copy(store.block_states[block.parent_root])

    # Blocks cannot be in the future. If they are, their consideration must be delayed until they are in the past.
    current_slot = get_current_slot(store)
    assert current_slot >= block.slot

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

    # Check the block is valid and compute the post-state
    block_root = hash_tree_root(block)
    state_transition(state, signed_block, True)

    # Add new block to the store
    store.blocks[block_root] = block
    # Add new state for this block to the store
    store.block_states[block_root] = state
    # Add a new PTC voting for this block to the store
    store.ptc_vote[block_root] = [False] * PTC_SIZE

    # Notify the store about the payload_attestations in the block
    notify_ptc_messages(store, state, block.body.payload_attestations)
    # Add proposer score boost if the block is timely
    time_into_slot = (store.time - store.genesis_time) % SECONDS_PER_SLOT
    is_before_attesting_interval = time_into_slot < SECONDS_PER_SLOT // INTERVALS_PER_SLOT
    is_timely = get_current_slot(store) == block.slot and is_before_attesting_interval
    store.block_timeliness[hash_tree_root(block)] = is_timely

    # Add proposer score boost if the block is timely and not conflicting with an existing block
    is_first_block = store.proposer_boost_root == Root()
    if is_timely and is_first_block:
        store.proposer_boost_root = hash_tree_root(block)

    # Update checkpoints in store if necessary
    update_checkpoints(store, state.current_justified_checkpoint, state.finalized_checkpoint)

    # Eagerly compute unrealized justification and finality.
    compute_pulled_up_tip(store, block_root)
```

## New fork-choice handlers

### New `on_execution_payload`

The handler `on_execution_payload` is called when the node receives a
`SignedExecutionPayloadEnvelope` to sync.

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
    assert is_data_available(envelope.beacon_block_root, envelope.blob_kzg_commitments)

    # Make a copy of the state to avoid mutability issues
    state = copy(store.block_states[envelope.beacon_block_root])

    # Process the execution payload
    process_execution_payload(state, signed_envelope, EXECUTION_ENGINE)

    # Add new state for this payload to the store
    store.execution_payload_states[envelope.beacon_block_root] = state
```

### New `on_payload_attestation_message`

```python
def on_payload_attestation_message(
    store: Store, ptc_message: PayloadAttestationMessage, is_from_block: bool = False
) -> None:
    """
    Run ``on_payload_attestation_message`` upon receiving a new ``ptc_message`` directly on the wire.
    """
    # The beacon block root must be known
    data = ptc_message.data
    # PTC attestation must be for a known block. If block is unknown, delay consideration until the block is found
    state = store.block_states[data.beacon_block_root]
    ptc = get_ptc(state, data.slot)
    # PTC votes can only change the vote for their assigned beacon block, return early otherwise
    if data.slot != state.slot:
        return
    # Check that the attester is from the PTC
    assert ptc_message.validator_index in ptc

    # Verify the signature and check that its for the current slot if it is coming from the wire
    if not is_from_block:
        # Check that the attestation is for the current slot
        assert data.slot == get_current_slot(store)
        # Verify the signature
        assert is_valid_indexed_payload_attestation(
            state,
            IndexedPayloadAttestation(
                attesting_indices=[ptc_message.validator_index],
                data=data,
                signature=ptc_message.signature,
            ),
        )
    # Update the ptc vote for the block
    ptc_index = ptc.index(ptc_message.validator_index)
    ptc_vote = store.ptc_vote[data.beacon_block_root]
    ptc_vote[ptc_index] = data.payload_present
```

### Modified `validate_on_attestation`

```python
def validate_on_attestation(store: Store, attestation: Attestation, is_from_block: bool) -> None:
    target = attestation.data.target

    # If the given attestation is not from a beacon block message,
    # we have to check the target epoch scope.
    if not is_from_block:
        validate_target_epoch_against_current_time(store, attestation)

    # Check that the epoch number and slot number are matching.
    assert target.epoch == compute_epoch_at_slot(attestation.data.slot)

    # Attestation target must be for a known block. If target block
    # is unknown, delay consideration until block is found.
    assert target.root in store.blocks

    # Attestations must be for a known block. If block
    # is unknown, delay consideration until the block is found.
    assert attestation.data.beacon_block_root in store.blocks
    # Attestations must not be for blocks in the future.
    # If not, the attestation should not be considered.
    block_slot = store.blocks[attestation.data.beacon_block_root].slot
    assert block_slot <= attestation.data.slot

    # [New in EIP7732]
    assert attestation.data.index in [0, 1]
    if block_slot == attestation.data.slot:
        assert attestation.data.index == 0

    # LMD vote must be consistent with FFG vote target
    assert target.root == get_checkpoint_block(
        store, attestation.data.beacon_block_root, target.epoch
    )

    # Attestations can only affect the fork-choice of subsequent slots.
    # Delay consideration in the fork-choice until their slot is in the past.
    assert get_current_slot(store) >= attestation.data.slot + 1
```

### Modified `validate_merge_block`

The function `validate_merge_block` is modified for test purposes

```python
def validate_merge_block(block: BeaconBlock) -> None:
    """
    Check the parent PoW block of execution payload is a valid terminal PoW block.

    Note: Unavailable PoW block(s) may later become available,
    and a client software MAY delay a call to ``validate_merge_block``
    until the PoW block(s) become available.
    """
    if TERMINAL_BLOCK_HASH != Hash32():
        # If `TERMINAL_BLOCK_HASH` is used as an override, the activation epoch must be reached.
        assert compute_epoch_at_slot(block.slot) >= TERMINAL_BLOCK_HASH_ACTIVATION_EPOCH
        assert (
            block.body.signed_execution_payload_header.message.parent_block_hash
            == TERMINAL_BLOCK_HASH
        )
        return

    pow_block = get_pow_block(block.body.signed_execution_payload_header.message.parent_block_hash)
    # Check if `pow_block` is available
    assert pow_block is not None
    pow_parent = get_pow_block(pow_block.parent_hash)
    # Check if `pow_parent` is available
    assert pow_parent is not None
    # Check if `pow_block` is a valid terminal PoW block
    assert is_valid_terminal_pow_block(pow_block, pow_parent)
```
