# Capella -- Fork Choice

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Custom types](#custom-types)
- [Protocols](#protocols)
  - [`ExecutionEngine`](#executionengine)
    - [`notify_forkchoice_updated`](#notify_forkchoice_updated)
- [Helpers](#helpers)
  - [Modified `PayloadAttributes`](#modified-payloadattributes)
- [Updated fork-choice handlers](#updated-fork-choice-handlers)
  - [`on_block`](#on_block)

<!-- mdformat-toc end -->

## Introduction

This is the modification of the fork choice according to the Capella upgrade.

Unless stated explicitly, all prior functionality from
[Bellatrix](../bellatrix/fork-choice.md) is inherited.

## Custom types

## Protocols

### `ExecutionEngine`

*Note*: The `notify_forkchoice_updated` function is modified in the
`ExecutionEngine` protocol at the Capella upgrade.

#### `notify_forkchoice_updated`

The only change made is to the `PayloadAttributes` container through the
addition of `withdrawals`. Otherwise, `notify_forkchoice_updated` inherits all
prior functionality.

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

`PayloadAttributes` is extended with the `withdrawals` field.

```python
@dataclass
class PayloadAttributes(object):
    timestamp: uint64
    prev_randao: Bytes32
    suggested_fee_recipient: ExecutionAddress
    withdrawals: Sequence[Withdrawal]  # [New in Capella]
```

## Updated fork-choice handlers

### `on_block`

*Note*: The only modification is the deletion of the verification of merge
transition block conditions.

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
    time_into_slot = (store.time - store.genesis_time) % SECONDS_PER_SLOT
    is_before_late_block_cutoff = time_into_slot * 1000 < LATE_BLOCK_CUTOFF_MS
    is_timely = get_current_slot(store) == block.slot and is_before_late_block_cutoff
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
