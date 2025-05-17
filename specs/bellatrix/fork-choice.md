# Bellatrix -- Fork Choice

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Custom types](#custom-types)
- [Protocols](#protocols)
  - [`ExecutionEngine`](#executionengine)
    - [`notify_forkchoice_updated`](#notify_forkchoice_updated)
      - [`safe_block_hash`](#safe_block_hash)
      - [`should_override_forkchoice_update`](#should_override_forkchoice_update)
- [Helpers](#helpers)
  - [`PayloadAttributes`](#payloadattributes)
  - [`PowBlock`](#powblock)
  - [`get_pow_block`](#get_pow_block)
  - [`is_valid_terminal_pow_block`](#is_valid_terminal_pow_block)
  - [`validate_merge_block`](#validate_merge_block)
- [Updated fork-choice handlers](#updated-fork-choice-handlers)
  - [`on_block`](#on_block)

<!-- mdformat-toc end -->

## Introduction

This is the modification of the fork choice according to the executable beacon
chain proposal.

*Note*: It introduces the process of transition from the last PoW block to the
first PoS block.

## Custom types

| Name        | SSZ equivalent | Description                              |
| ----------- | -------------- | ---------------------------------------- |
| `PayloadId` | `Bytes8`       | Identifier of a payload building process |

## Protocols

### `ExecutionEngine`

*Note*: The `notify_forkchoice_updated` function is added to the
`ExecutionEngine` protocol to signal the fork choice updates.

The body of this function is implementation dependent. The Engine API may be
used to implement it with an external execution engine.

#### `notify_forkchoice_updated`

This function performs three actions *atomically*:

- Re-organizes the execution payload chain and corresponding state to make
  `head_block_hash` the head.
- Updates safe block hash with the value provided by `safe_block_hash`
  parameter.
- Applies finality to the execution state: it irreversibly persists the chain of
  all execution payloads and corresponding state, up to and including
  `finalized_block_hash`.

Additionally, if `payload_attributes` is provided, this function sets in motion
a payload build process on top of `head_block_hash` and returns an identifier of
initiated process.

```python
def notify_forkchoice_updated(self: ExecutionEngine,
                              head_block_hash: Hash32,
                              safe_block_hash: Hash32,
                              finalized_block_hash: Hash32,
                              payload_attributes: Optional[PayloadAttributes]) -> Optional[PayloadId]:
    ...
```

*Note*: The `(head_block_hash, finalized_block_hash)` values of the
`notify_forkchoice_updated` function call maps on the `POS_FORKCHOICE_UPDATED`
event defined in the
[EIP-3675](https://eips.ethereum.org/EIPS/eip-3675#definitions). As per
EIP-3675, before a post-transition block is finalized,
`notify_forkchoice_updated` MUST be called with
`finalized_block_hash = Hash32()`.

*Note*: Client software MUST NOT call this function until the transition
conditions are met on the PoW network, i.e. there exists a block for which
`is_valid_terminal_pow_block` function returns `True`.

*Note*: Client software MUST call this function to initiate the payload build
process to produce the merge transition block; the `head_block_hash` parameter
MUST be set to the hash of a terminal PoW block in this case.

##### `safe_block_hash`

The `safe_block_hash` parameter MUST be set to return value of
[`get_safe_execution_block_hash(store: Store)`](../../fork_choice/safe-block.md#get_safe_execution_block_hash)
function.

##### `should_override_forkchoice_update`

If proposer boost re-orgs are implemented and enabled (see `get_proposer_head`)
then additional care must be taken to ensure that the proposer is able to build
an execution payload.

If a beacon node knows it will propose the next block then it SHOULD NOT call
`notify_forkchoice_updated` if it detects the current head to be weak and
potentially capable of being re-orged. Complete information for evaluating
`get_proposer_head` _will not_ be available immediately after the receipt of a
new block, so an approximation of those conditions should be used when deciding
whether to send or suppress a fork choice notification. The exact conditions
used may be implementation-specific, a suggested implementation is below.

Let `validator_is_connected(validator_index: ValidatorIndex) -> bool` be a
function that indicates whether the validator with `validator_index` is
connected to the node (e.g. has sent an unexpired proposer preparation message).

```python
def should_override_forkchoice_update(store: Store, head_root: Root) -> bool:
    head_block = store.blocks[head_root]
    parent_root = head_block.parent_root
    parent_block = store.blocks[parent_root]
    current_slot = get_current_slot(store)
    proposal_slot = head_block.slot + Slot(1)

    # Only re-org the head_block block if it arrived later than the attestation deadline.
    head_late = is_head_late(store, head_root)

    # Shuffling stable.
    shuffling_stable = is_shuffling_stable(proposal_slot)

    # FFG information of the new head_block will be competitive with the current head.
    ffg_competitive = is_ffg_competitive(store, head_root, parent_root)

    # Do not re-org if the chain is not finalizing with acceptable frequency.
    finalization_ok = is_finalization_ok(store, proposal_slot)

    # Only suppress the fork choice update if we are confident that we will propose the next block.
    parent_state_advanced = store.block_states[parent_root].copy()
    process_slots(parent_state_advanced, proposal_slot)
    proposer_index = get_beacon_proposer_index(parent_state_advanced)
    proposing_reorg_slot = validator_is_connected(proposer_index)

    # Single slot re-org.
    parent_slot_ok = parent_block.slot + 1 == head_block.slot
    proposing_on_time = is_proposing_on_time(store)

    # Note that this condition is different from `get_proposer_head`
    current_time_ok = (head_block.slot == current_slot
                       or (proposal_slot == current_slot and proposing_on_time))
    single_slot_reorg = parent_slot_ok and current_time_ok

    # Check the head weight only if the attestations from the head slot have already been applied.
    # Implementations may want to do this in different ways, e.g. by advancing
    # `store.time` early, or by counting queued attestations during the head block's slot.
    if current_slot > head_block.slot:
        head_weak = is_head_weak(store, head_root)
        parent_strong = is_parent_strong(store, parent_root)
    else:
        head_weak = True
        parent_strong = True

    return all([head_late, shuffling_stable, ffg_competitive, finalization_ok,
                proposing_reorg_slot, single_slot_reorg,
                head_weak, parent_strong])
```

*Note*: The ordering of conditions is a suggestion only. Implementations are
free to optimize by re-ordering the conditions from least to most expensive and
by returning early if any of the early conditions are `False`.

In case `should_override_forkchoice_update` returns `True`, a node SHOULD
instead call `notify_forkchoice_updated` with parameters appropriate for
building upon the parent block. Care must be taken to compute the correct
`payload_attributes`, as they may change depending on the slot of the block to
be proposed (due to withdrawals).

If `should_override_forkchoice_update` returns `True` but `get_proposer_head`
later chooses the canonical head rather than its parent, then this is a
misprediction that will cause the node to construct a payload with less notice.
The result of `get_proposer_head` MUST be preferred over the result of
`should_override_forkchoice_update` (when proposer reorgs are enabled).

## Helpers

### `PayloadAttributes`

Used to signal to initiate the payload build process via
`notify_forkchoice_updated`.

```python
@dataclass
class PayloadAttributes(object):
    timestamp: uint64
    prev_randao: Bytes32
    suggested_fee_recipient: ExecutionAddress
```

### `PowBlock`

```python
class PowBlock(Container):
    block_hash: Hash32
    parent_hash: Hash32
    total_difficulty: uint256
```

### `get_pow_block`

Let `get_pow_block(block_hash: Hash32) -> Optional[PowBlock]` be the function
that given the hash of the PoW block returns its data. It may result in `None`
if the requested block is not yet available.

*Note*: The `eth_getBlockByHash` JSON-RPC method may be used to pull this
information from an execution client.

### `is_valid_terminal_pow_block`

Used by fork-choice handler, `on_block`.

```python
def is_valid_terminal_pow_block(block: PowBlock, parent: PowBlock) -> bool:
    is_total_difficulty_reached = block.total_difficulty >= TERMINAL_TOTAL_DIFFICULTY
    is_parent_total_difficulty_valid = parent.total_difficulty < TERMINAL_TOTAL_DIFFICULTY
    return is_total_difficulty_reached and is_parent_total_difficulty_valid
```

### `validate_merge_block`

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
        assert block.body.execution_payload.parent_hash == TERMINAL_BLOCK_HASH
        return

    pow_block = get_pow_block(block.body.execution_payload.parent_hash)
    # Check if `pow_block` is available
    assert pow_block is not None
    pow_parent = get_pow_block(pow_block.parent_hash)
    # Check if `pow_parent` is available
    assert pow_parent is not None
    # Check if `pow_block` is a valid terminal PoW block
    assert is_valid_terminal_pow_block(pow_block, pow_parent)
```

## Updated fork-choice handlers

### `on_block`

*Note*: The only modification is the addition of the verification of transition
block conditions.

```python
def on_block(store: Store, signed_block: SignedBeaconBlock) -> None:
    """
    Run ``on_block`` upon receiving a new block.

    A block that is asserted as invalid due to unavailable PoW block may be valid at a later time,
    consider scheduling it for later processing in such case.
    """
    block = signed_block.message
    # Parent block must be known
    assert block.parent_root in store.block_states
    # Make a copy of the state to avoid mutability issues
    pre_state = copy(store.block_states[block.parent_root])
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

    # Check the block is valid and compute the post-state
    state = pre_state.copy()
    block_root = hash_tree_root(block)
    state_transition(state, signed_block, True)

    # [New in Bellatrix]
    if is_merge_transition_block(pre_state, block.body):
        validate_merge_block(block)

    # Add new block to the store
    store.blocks[block_root] = block
    # Add new state for this block to the store
    store.block_states[block_root] = state

    # Add block timeliness to the store
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
