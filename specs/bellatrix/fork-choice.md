# Bellatrix -- Fork Choice

**Notice**: This document is a work-in-progress for researchers and implementers.

## Table of contents
<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Custom types](#custom-types)
- [Protocols](#protocols)
  - [`ExecutionEngine`](#executionengine)
    - [`notify_forkchoice_updated`](#notify_forkchoice_updated)
- [Helpers](#helpers)
  - [`PayloadAttributes`](#payloadattributes)
  - [`PowBlock`](#powblock)
  - [`get_pow_block`](#get_pow_block)
  - [`is_valid_terminal_pow_block`](#is_valid_terminal_pow_block)
  - [`validate_merge_block`](#validate_merge_block)
- [Updated fork-choice handlers](#updated-fork-choice-handlers)
  - [`on_block`](#on_block)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This is the modification of the fork choice according to the executable beacon chain proposal.

*Note*: It introduces the process of transition from the last PoW block to the first PoS block.

## Custom types

| Name | SSZ equivalent | Description |
| - | - | - |
| `PayloadId` | `Bytes8` | Identifier of a payload building process |

## Protocols

### `ExecutionEngine`

*Note*: The `notify_forkchoice_updated` function is added to the `ExecutionEngine` protocol to signal the fork choice updates.

The body of this function is implementation dependent.
The Engine API may be used to implement it with an external execution engine.

#### `notify_forkchoice_updated`

This function performs two actions *atomically*:
* Re-organizes the execution payload chain and corresponding state to make `head_block_hash` the head.
* Applies finality to the execution state: it irreversibly persists the chain of all execution payloads
and corresponding state, up to and including `finalized_block_hash`.

Additionally, if `payload_attributes` is provided, this function sets in motion a payload build process on top of
`head_block_hash` and returns an identifier of initiated process.

```python
def notify_forkchoice_updated(self: ExecutionEngine,
                              head_block_hash: Hash32,
                              finalized_block_hash: Hash32,
                              payload_attributes: Optional[PayloadAttributes]) -> Optional[PayloadId]:
    ...
```

*Note*: The call of the `notify_forkchoice_updated` function maps on the `POS_FORKCHOICE_UPDATED` event defined in the [EIP-3675](https://eips.ethereum.org/EIPS/eip-3675#definitions).
As per EIP-3675, before a post-transition block is finalized, `notify_forkchoice_updated` MUST be called with `finalized_block_hash = Hash32()`.

*Note*: Client software MUST NOT call this function until the transition conditions are met on the PoW network, i.e. there exists a block for which `is_valid_terminal_pow_block` function returns `True`.

*Note*: Client software MUST call this function to initiate the payload build process to produce the merge transition block; the `head_block_hash` parameter MUST be set to the hash of a terminal PoW block in this case.

## Helpers

### `PayloadAttributes`

Used to signal to initiate the payload build process via `notify_forkchoice_updated`.

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

Let `get_pow_block(block_hash: Hash32) -> Optional[PowBlock]` be the function that given the hash of the PoW block returns its data.
It may result in `None` if the requested block is not yet available.

*Note*: The `eth_getBlockByHash` JSON-RPC method may be used to pull this information from an execution client.

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

*Note*: The only modification is the addition of the verification of transition block conditions.

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
    # Blocks cannot be in the future. If they are, their consideration must be delayed until the are in the past.
    assert get_current_slot(store) >= block.slot

    # Check that block is later than the finalized epoch slot (optimization to reduce calls to get_ancestor)
    finalized_slot = compute_start_slot_at_epoch(store.finalized_checkpoint.epoch)
    assert block.slot > finalized_slot
    # Check block is a descendant of the finalized block at the checkpoint finalized slot
    assert get_ancestor(store, block.parent_root, finalized_slot) == store.finalized_checkpoint.root

    # Check the block is valid and compute the post-state
    state = pre_state.copy()
    state_transition(state, signed_block, True)

    # [New in Bellatrix]
    if is_merge_transition_block(pre_state, block.body):
        validate_merge_block(block)

    # Add new block to the store
    store.blocks[hash_tree_root(block)] = block
    # Add new state for this block to the store
    store.block_states[hash_tree_root(block)] = state

    # Add proposer score boost if the block is timely
    time_into_slot = (store.time - store.genesis_time) % SECONDS_PER_SLOT
    is_before_attesting_interval = time_into_slot < SECONDS_PER_SLOT // INTERVALS_PER_SLOT
    if get_current_slot(store) == block.slot and is_before_attesting_interval:
        store.proposer_boost_root = hash_tree_root(block)

    # Update justified checkpoint
    if state.current_justified_checkpoint.epoch > store.justified_checkpoint.epoch:
        if state.current_justified_checkpoint.epoch > store.best_justified_checkpoint.epoch:
            store.best_justified_checkpoint = state.current_justified_checkpoint
        if should_update_justified_checkpoint(store, state.current_justified_checkpoint):
            store.justified_checkpoint = state.current_justified_checkpoint

    # Update finalized checkpoint
    if state.finalized_checkpoint.epoch > store.finalized_checkpoint.epoch:
        store.finalized_checkpoint = state.finalized_checkpoint
        store.justified_checkpoint = state.current_justified_checkpoint
```
