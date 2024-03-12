# EIP-7547 -- Fork Choice

## Table of contents
<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Helpers](#helpers)
  - [`verify_inclusion_list`](#verify_inclusion_list)
- [Updated fork-choice handlers](#updated-fork-choice-handlers)
  - [`on_block`](#on_block)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This is the modification of the fork choice accompanying EIP-7547.

## Helpers

### `verify_inclusion_list`
*[New in EIP-7547]*

```python
def verify_inclusion_list(state: BeaconState, block: BeaconBlock, inclusion_list: SignedInclusionList, execution_engine: ExecutionEngine) -> bool:
    """
    returns true if the inclusion list is valid. 
    """
    # Check that the inclusion list corresponds to the block proposer
    signed_summary = inclusion_list.signed_summary
    proposer_index = signed_summary.message.proposer_index
    assert block.proposer_index == proposer_index

    # Check that the signature is correct
    assert verify_inclusion_list_summary_signature(state, signed_summary)

    # Check that the inclusion list is valid
    return execution_engine.notify_new_inclusion_list(NewInclusionListRequest(
            inclusion_list=inclusion_list.transactions, 
            summary=inclusion_list.signed_summary.message.summary,
            parent_block_hash = state.latest_execution_payload_header.block_hash))
```

## Updated fork-choice handlers

### `on_block`

*Note*: We change the type of the handler to the `SignedBeaconBlockAndInclusionList` which is gossiped in the `beacon_block` topic. 

```python
def on_block(store: Store, signed_block_and_inclusion_list: SignedBeaconBlockAndInclusionList) -> None:
    """
    Run ``on_block`` upon receiving a new block.
    """
    # [New in EIP-7547] Get block and inclusion list from the gossip message.
    signed_block = signed_block_and_inclusion_list.signed_block
    signed_inclusion_list = signed_block_and_inclusion_list.signed_inclusion_list
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

    # [New in EIP-7547] Check if the inclusion list is valid.
    assert verify_inclusion_list(state, block, signed_inclusion_list.signed_summary, block.parent_root)

    # Check the block is valid and compute the post-state
    state = pre_state.copy()
    block_root = hash_tree_root(block)
    state_transition(state, signed_block, True)

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