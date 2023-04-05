# Deneb -- Fork Choice

## Table of contents
<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Containers](#containers)
- [Helpers](#helpers)
    - [`validate_blobs`](#validate_blobs)
    - [`is_data_available`](#is_data_available)
- [Updated fork-choice handlers](#updated-fork-choice-handlers)
  - [`on_block`](#on_block)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This is the modification of the fork choice accompanying the Deneb upgrade.

## Containers

## Helpers

#### `validate_blobs`

```python
def validate_blobs(expected_kzg_commitments: Sequence[KZGCommitment],
                   blobs: Sequence[Blob],
                   proofs: Sequence[KZGProof]) -> None:
    assert len(expected_kzg_commitments) == len(blobs)
    assert len(blobs) == len(proofs)

    assert verify_blob_kzg_proof_batch(blobs, expected_kzg_commitments, proofs)
```

#### `is_data_available`

The implementation of `is_data_available` will become more sophisticated during later scaling upgrades.
Initially, verification requires every verifying actor to retrieve all matching `Blob`s and `KZGProof`s, and validate them with `validate_blobs`.

The block MUST NOT be considered valid until all valid `Blob`s have been downloaded. Blocks that have been previously validated as available SHOULD be considered available even if the associated `Blob`s have subsequently been pruned.

```python
def is_data_available(beacon_block_root: Root, blob_kzg_commitments: Sequence[KZGCommitment]) -> bool:
    # `retrieve_blobs_and_proofs` is implementation and context dependent
    # It returns all the blobs for the given block root, and raises an exception if not available
    # Note: the p2p network does not guarantee sidecar retrieval outside of `MIN_EPOCHS_FOR_BLOB_SIDECARS_REQUESTS`
    blobs, proofs = retrieve_blobs_and_proofs(beacon_block_root)

    # For testing, `retrieve_blobs_and_proofs` returns ("TEST", "TEST").
    # TODO: Remove it once we have a way to inject `BlobSidecar` into tests.
    if isinstance(blobs, str) or isinstance(proofs, str):
        return True

    validate_blobs(blob_kzg_commitments, blobs, proofs)
    return True
```

## Updated fork-choice handlers

### `on_block`

*Note*: The only modification is the addition of the blob data availability check.

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
    assert store.finalized_checkpoint.root == get_ancestor_at_epoch_boundary(
        store,
        block.parent_root,
        store.finalized_checkpoint.epoch,
    )

    # [New in Deneb]
    # Check if blob data is available
    # If not, this block MAY be queued and subsequently considered when blob data becomes available
    assert is_data_available(hash_tree_root(block), block.body.blob_kzg_commitments)

    # Check the block is valid and compute the post-state
    state = pre_state.copy()
    block_root = hash_tree_root(block)
    state_transition(state, signed_block, True)

    # Check the merge transition
    if is_merge_transition_block(pre_state, block.body):
        validate_merge_block(block)

    # Add new block to the store
    store.blocks[block_root] = block
    # Add new state for this block to the store
    store.block_states[block_root] = state

    # Add proposer score boost if the block is timely
    time_into_slot = (store.time - store.genesis_time) % SECONDS_PER_SLOT
    is_before_attesting_interval = time_into_slot < SECONDS_PER_SLOT // INTERVALS_PER_SLOT
    if get_current_slot(store) == block.slot and is_before_attesting_interval:
        store.proposer_boost_root = hash_tree_root(block)

    # Update checkpoints in store if necessary
    update_checkpoints(store, state.current_justified_checkpoint, state.finalized_checkpoint)

    # Eagerly compute unrealized justification and finality.
    compute_pulled_up_tip(store, block_root)
```
