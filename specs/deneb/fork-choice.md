# Deneb -- Fork Choice

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Containers](#containers)
- [Helpers](#helpers)
  - [Modified `PayloadAttributes`](#modified-payloadattributes)
  - [`is_data_available`](#is_data_available)
- [Updated fork-choice handlers](#updated-fork-choice-handlers)
  - [`on_block`](#on_block)

<!-- mdformat-toc end -->

## Introduction

This is the modification of the fork choice accompanying the Deneb upgrade.

## Containers

## Helpers

### Modified `PayloadAttributes`

`PayloadAttributes` is extended with the parent beacon block root for EIP-4788.

```python
@dataclass
class PayloadAttributes(object):
    timestamp: uint64
    prev_randao: Bytes32
    suggested_fee_recipient: ExecutionAddress
    withdrawals: Sequence[Withdrawal]
    parent_beacon_block_root: Root  # [New in Deneb:EIP4788]
```

### `is_data_available`

*[New in Deneb:EIP4844]*

The implementation of `is_data_available` will become more sophisticated during
later scaling upgrades. Initially, verification requires every verifying actor
to retrieve all matching `Blob`s and `KZGProof`s, and validate them with
`verify_blob_kzg_proof_batch`.

The block MUST NOT be considered valid until all valid `Blob`s have been
downloaded. Blocks that have been previously validated as available SHOULD be
considered available even if the associated `Blob`s have subsequently been
pruned.

*Note*: Extraneous or invalid Blobs (in addition to KZG expected/referenced
valid blobs) received on the p2p network MUST NOT invalidate a block that is
otherwise valid and available.

```python
def is_data_available(beacon_block_root: Root, blob_kzg_commitments: Sequence[KZGCommitment]) -> bool:
    # `retrieve_blobs_and_proofs` is implementation and context dependent
    # It returns all the blobs for the given block root, and raises an exception if not available
    # Note: the p2p network does not guarantee sidecar retrieval outside of
    # `MIN_EPOCHS_FOR_BLOB_SIDECARS_REQUESTS`
    blobs, proofs = retrieve_blobs_and_proofs(beacon_block_root)

    return verify_blob_kzg_proof_batch(blobs, blob_kzg_commitments, proofs)
```

## Updated fork-choice handlers

### `on_block`

*Note*: The only modification is the addition of the blob data availability
check.

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

    # [New in Deneb:EIP4844]
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
