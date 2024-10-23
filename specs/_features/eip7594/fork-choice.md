# EIP-7594 -- Fork Choice

## Table of contents
<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Helpers](#helpers)
  - [New `Config`](#new-config)
  - [Modified `Store`](#modified-store)
  - [Modified `is_data_available`](#modified-is_data_available)
- [New fork-choice handlers](#new-fork-choice-handlers)
  - [New `on_data_column_sidecar`](#new-on_data_column_sidecar)
- [Updated fork-choice handlers](#updated-fork-choice-handlers)
  - [Modified `on_block`](#modified-on_block)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This is the modification of the fork choice accompanying EIP-7594.

## Helpers

### New `Config`

*Note*: `Config` is supposed to be pre-populated with configurations specific to each node.

```python
@dataclass
class Config(object):
    metadata: MetaData
    node_id: NodeID
```

### Modified `Store`

*Note*: There are two modifications to `Store`:
1. Config is added to keep node-specific configurations.
2. Data column sidecar store is added to keep track the data column sidecars that have been seen.

```python
@dataclass
class Store(object):
    config: Config # [New in EIP7594]
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
    # blob_sidecars: Dict[BlobIdentifier, BlobSidecar] = field(default_factory=dict) # [Removed in EIP7594]
    data_column_sidecars: Dict[DataColumnIdentifier, DataColumnSidecar] = field(default_factory=dict) # [New in EIP7594]
```

### Modified `is_data_available`

```python
def is_data_available(store: Store, beacon_block_root: Root) -> bool:
    # The p2p network does not guarantee sidecar retrieval outside of
    # `MIN_EPOCHS_FOR_DATA_COLUMN_SIDECARS_REQUESTS` epochs.
    custody_columns = get_custody_columns(store.config.node_id, store.config.metadata.custody_subnet_count)
    return all(
        DataColumnIdentifier(block_root=beacon_block_root, index=column_index) in store.data_column_sidecars
        for column_index in custody_columns
    )
```

## New fork-choice handlers

### New `on_data_column_sidecar`

*Note*: `on_data_column_sidecar` is triggered whenever a data column sidecar is received (either through Gossipsub topics or Req/Resp).

```python
def on_data_column_sidecar(store: Store, sidecar: DataColumnSidecar) -> None:
    """
    Run ``on_data_column_sidecar`` upon receiving a data column sidecar.
    """
    block_header = sidecar.signed_block_header.message
    # Verify data column sidecar
    assert verify_data_column_sidecar(sidecar)
    # Data column sidecars cannot be in the future. If they are, their consideration must be delayed until they are in the past.
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
    assert verify_data_column_sidecar_inclusion_proof(sidecar)

    # The sidecar's column data is valid
    assert verify_data_column_sidecar_kzg_proofs(sidecar)

    # Check block is proposed by the expected proposer
    process_slots(state, block.slot)
    assert block.proposer_index == get_beacon_proposer_index(state)

    # Save the data column sidecar
    data_column_identifier = DataColumnIdentifier(block_root=hash_tree_root(block_header), index=sidecar.index)
    store.data_column_sidecars[data_column_identifier] = sidecar
```

## Updated fork-choice handlers

### Modified `on_block`

*Note*: The only modification is that `is_data_available` does not take `blob_kzg_commitments` as input.

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

    # [Modified in EIP7594]
    assert is_data_available(hash_tree_root(block))

    # Check the block is valid and compute the post-state
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
