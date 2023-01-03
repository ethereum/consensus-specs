# EIP-4844 -- Fork Choice

## Table of contents
<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Helpers](#helpers)
    - [`is_data_available`](#is_data_available)
- [Updated fork-choice handlers](#updated-fork-choice-handlers)
  - [`on_block`](#on_block)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This is the modification of the fork choice according to the executable beacon chain proposal.

## Helpers

#### `is_data_available`

The implementation of `is_data_available` will become more sophisticated during later sharding upgrades.
Initially, it requires every verifying actor to retrieve the matching `BlobsSidecar`,
and validate the sidecar with `validate_blobs_sidecar`.

The block MUST NOT be considered valid until a valid `BlobsSidecar` has been downloaded. Blocks that have been previously validated as available SHOULD be considered available even if the associated `BlobsSidecar` has subsequently been pruned.

```python
def is_data_available(slot: Slot, beacon_block_root: Root, blob_kzg_commitments: Sequence[KZGCommitment]) -> bool:
    # `retrieve_blobs_sidecar` is implementation and context dependent, raises an exception if not available.
    # Note: the p2p network does not guarantee sidecar retrieval outside of `MIN_EPOCHS_FOR_BLOBS_SIDECARS_REQUESTS`
    sidecar = retrieve_blobs_sidecar(slot, beacon_block_root)

    # For testing, `retrieve_blobs_sidecar` returns "TEST".
    # TODO: Remove it once we have a way to inject `BlobsSidecar` into tests.
    if isinstance(sidecar, str):
        return True

    validate_blobs_sidecar(slot, beacon_block_root, blob_kzg_commitments, sidecar)
    return True
```

## Updated fork-choice handlers

### `on_block`

*Note*: The only modification is the addition of the verification of transition block conditions.

```python
def on_block(store: Store, signed_block: SignedBeaconBlock) -> None:
    """
    Run ``on_block`` upon receiving a new block.
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
    assert get_ancestor(store, block.parent_root, finalized_slot) == store.finalized_checkpoint.root

    # [New in EIP-4844]
    # Check if the block is available
    assert is_data_available(block.slot, hash_tree_root(block), block.body.blob_kzg_commitments) 

    # Check the block is valid and compute the post-state
    state = pre_state.copy()
    state_transition(state, signed_block, True)

    # Check the merge transition
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
