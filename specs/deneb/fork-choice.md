# Deneb -- Fork Choice

## Table of contents
<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Containers](#containers)
- [Helpers](#helpers)
  - [Extended `PayloadAttributes`](#extended-payloadattributes)
  - [`is_data_available`](#is_data_available)
- [Updated fork-choice handlers](#updated-fork-choice-handlers)
  - [`on_block`](#on_block)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This is the modification of the fork choice accompanying the Deneb upgrade.

## Containers

## Helpers

### Modified `Store`

*Note*: Blob sidecar store is added to keep track the blob sidecars that have been seen.

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
    blob_sidecars: Dict[BlobIdentifier, BlobSidecar] = field(default_factory=dict) # [New in Deneb]
```

### Extended `PayloadAttributes`

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

The implementation of `is_data_available` will become more sophisticated during later scaling upgrades.

The block MUST NOT be considered valid until all valid `Blob`s have been downloaded. Blocks that have been previously validated as available SHOULD be considered available even if the associated `Blob`s have subsequently been pruned.

*Note*: Extraneous or invalid Blobs (in addition to KZG expected/referenced valid blobs) received on the p2p network MUST NOT invalidate a block that is otherwise valid and available.

```python
def is_data_available(store: Store, beacon_block_root: Root, blob_kzg_commitments: Sequence[KZGCommitment]) -> bool:
    # Note: the p2p network does not guarantee sidecar retrieval outside of
    # `MIN_EPOCHS_FOR_BLOB_SIDECARS_REQUESTS`
    return all(
        BlobIdentifier(block_root=beacon_block_root, index=index) in store.blob_sidecars
        for index in range(len(blob_kzg_commitments))
    )
```
## New fork-choice handlers

### `on_blob_sidecar`

```python
def on_blob_sidecar(store: Store, sidecar: BlobSidecar) -> None:
    """
    Run ``on_blob_sidecar`` upon receiving a blob sidecar.
    """
    block_header = sidecar.signed_block_header.message
    # The sidecar's index is consistent with `MAX_BLOBS_PER_BLOCK`
    assert sidecar.index < MAX_BLOBS_PER_BLOCK
    # Blob sidecars cannot be in the future. If they are, their consideration must be delayed until they are in the past.
    assert get_current_slot(store) >= block_header.slot

    # Check that the sidecar is later than the finalized epoch slot (optimization to reduce calls to get_ancestor)
    finalized_slot = compute_start_slot_at_epoch(store.finalized_checkpoint.epoch)
    assert block_header.slot > finalized_slot

    # Parent block must be known
    assert block_header.parent_root in store.block_states
    # Make a copy of the state to avoid mutability issues
    state = copy(store.block_states[block_header.parent_root])

    # The block header signature is valid with respect to the proposer pubkey
    proposer = state.validators[block_header.proposer_index]
    domain = get_domain(state, DOMAIN_BEACON_PROPOSER, compute_epoch_at_slot(block_header.slot))
    signing_root = compute_signing_root(block_header, domain)
    assert bls.Verify(proposer.pubkey, signing_root, sidecar.signed_block_header.signature)

    # The sidecar is from a higher slot than the sidecar's block's parent
    assert block_header.slot > store.blocks[block_header.parent_root].slot

    # Check block is a descendant of the finalized block at the checkpoint finalized slot
    finalized_checkpoint_block = get_checkpoint_block(
        store,
        block_header.parent_root,
        store.finalized_checkpoint.epoch,
    )
    assert store.finalized_checkpoint.root == finalized_checkpoint_block

    # The sidecar's inclusion proof is valid
    assert verify_blob_sidecar_inclusion_proof(sidecar)

    # The sidecar's blob is valid
    asesrt verify_blob_kzg_proof(sidecar.blob, sidecar.kzg_commitment, sidecar.kzg_proof)

    # Check block is proposed by the expected proposer
    process_slots(state, block.slot)
    assert block.proposer_index == get_beacon_proposer_index(state)

    # Save the blob sidecar
    blob_identifier = BlobIdentifier(block_root=hash_tree_root(block_header), index=sidecar.index)
    store.blob_sidecars[blob_identifier] = sidecar
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
