# Fulu -- Fork Choice

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Helpers](#helpers)
  - [Modified `is_data_available`](#modified-is_data_available)
- [Updated fork-choice handlers](#updated-fork-choice-handlers)
  - [Modified `on_block`](#modified-on_block)

<!-- mdformat-toc end -->

## Introduction

This is the modification of the fork choice accompanying Fulu.

## Helpers

### Modified `is_data_available`

```python
def is_data_available(beacon_block_root: Root) -> bool:
    # `retrieve_column_sidecars` is implementation and context dependent, replacing
    # `retrieve_blobs_and_proofs`. For the given block root, it returns all column
    # sidecars to sample, or raises an exception if they are not available.
    # The p2p network does not guarantee sidecar retrieval outside of
    # `MIN_EPOCHS_FOR_DATA_COLUMN_SIDECARS_REQUESTS` epochs.
    column_sidecars = retrieve_column_sidecars(beacon_block_root)
    return all(
        verify_data_column_sidecar(column_sidecar)
        and verify_data_column_sidecar_kzg_proofs(column_sidecar)
        for column_sidecar in column_sidecars
    )
```

## Updated fork-choice handlers

### Modified `on_block`

*Note*: The only modification is that `is_data_available` does not take
`blob_kzg_commitments` as input.

```python
def on_block(store: Store, signed_block: SignedBeaconBlock) -> None:
    """
    Run ``on_block`` upon receiving a new block.
    """
    block = signed_block.message
    # Parent block must be known
    assert block.parent_root in store.block_states
    # Make a copy of the state to avoid mutability issues
    state = copy(store.block_states[block.parent_root])
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

    # [Modified in Fulu:EIP7594]
    assert is_data_available(hash_tree_root(block))

    # Check the block is valid and compute the post-state
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

    # Add proposer score boost if the block is timely and not conflicting with an existing block
    is_first_block = store.proposer_boost_root == Root()
    if is_timely and is_first_block:
        store.proposer_boost_root = hash_tree_root(block)

    # Update checkpoints in store if necessary
    update_checkpoints(store, state.current_justified_checkpoint, state.finalized_checkpoint)

    # Eagerly compute unrealized justification and finality.
    compute_pulled_up_tip(store, block_root)
```
