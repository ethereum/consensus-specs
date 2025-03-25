# Altair Light Client -- Full Node

## Table of contents

<!-- TOC -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Introduction](#introduction)
- [Helper functions](#helper-functions)
  - [`compute_merkle_proof`](#compute_merkle_proof)
  - [`block_to_light_client_header`](#block_to_light_client_header)
- [Deriving light client data](#deriving-light-client-data)
  - [`create_light_client_bootstrap`](#create_light_client_bootstrap)
  - [`create_light_client_update`](#create_light_client_update)
  - [`create_light_client_finality_update`](#create_light_client_finality_update)
  - [`create_light_client_optimistic_update`](#create_light_client_optimistic_update)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
<!-- /TOC -->

## Introduction

This document provides helper functions to enable full nodes to serve light client data. Full nodes SHOULD implement the described functionality to enable light clients to sync with the network.

## Helper functions

### `compute_merkle_proof`

This function return the Merkle proof of the given SSZ object `object` at generalized index `index`.

```python
def compute_merkle_proof(
    object: SSZObject, index: GeneralizedIndex
) -> Sequence[Bytes32]: ...
```

### `block_to_light_client_header`

```python
def block_to_light_client_header(block: SignedBeaconBlock) -> LightClientHeader:
    return LightClientHeader(
        beacon=BeaconBlockHeader(
            slot=block.message.slot,
            proposer_index=block.message.proposer_index,
            parent_root=block.message.parent_root,
            state_root=block.message.state_root,
            body_root=hash_tree_root(block.message.body),
        ),
    )
```

## Deriving light client data

Full nodes are expected to derive light client data from historic blocks and states and provide it to other clients.

### `create_light_client_bootstrap`

To form a `LightClientBootstrap`, the following objects are needed:
- `state`: the post state of any post-Altair block
- `block`: the corresponding block

```python
def create_light_client_bootstrap(
    state: BeaconState, block: SignedBeaconBlock
) -> LightClientBootstrap:
    assert compute_epoch_at_slot(state.slot) >= ALTAIR_FORK_EPOCH

    assert state.slot == state.latest_block_header.slot
    header = state.latest_block_header.copy()
    header.state_root = hash_tree_root(state)
    assert hash_tree_root(header) == hash_tree_root(block.message)

    return LightClientBootstrap(
        header=block_to_light_client_header(block),
        current_sync_committee=state.current_sync_committee,
        current_sync_committee_branch=CurrentSyncCommitteeBranch(
            compute_merkle_proof(
                state, current_sync_committee_gindex_at_slot(state.slot)
            )
        ),
    )
```

Full nodes SHOULD provide `LightClientBootstrap` for all finalized epoch boundary blocks in the epoch range `[max(ALTAIR_FORK_EPOCH, current_epoch - MIN_EPOCHS_FOR_BLOCK_REQUESTS), current_epoch]` where `current_epoch` is defined by the current wall-clock time. Full nodes MAY also provide `LightClientBootstrap` for other blocks.

Blocks are considered to be epoch boundary blocks if their block root can occur as part of a valid `Checkpoint`, i.e., if their slot is the initial slot of an epoch, or if all following slots through the initial slot of the next epoch are empty (no block proposed / orphaned).

`LightClientBootstrap` is computed from the block's immediate post state (without applying empty slots).

### `create_light_client_update`

To form a `LightClientUpdate`, the following historical states and blocks are needed:
- `state`: the post state of any block with a post-Altair parent block
- `block`: the corresponding block
- `attested_state`: the post state of `attested_block`
- `attested_block`: the block referred to by `block.parent_root`
- `finalized_block`: the block referred to by `attested_state.finalized_checkpoint.root`, if locally available (may be unavailable, e.g., when using checkpoint sync, or if it was pruned locally)

```python
def create_light_client_update(
    state: BeaconState,
    block: SignedBeaconBlock,
    attested_state: BeaconState,
    attested_block: SignedBeaconBlock,
    finalized_block: Optional[SignedBeaconBlock],
) -> LightClientUpdate:
    assert compute_epoch_at_slot(attested_state.slot) >= ALTAIR_FORK_EPOCH
    assert (
        sum(block.message.body.sync_aggregate.sync_committee_bits)
        >= MIN_SYNC_COMMITTEE_PARTICIPANTS
    )

    assert state.slot == state.latest_block_header.slot
    header = state.latest_block_header.copy()
    header.state_root = hash_tree_root(state)
    assert hash_tree_root(header) == hash_tree_root(block.message)
    update_signature_period = compute_sync_committee_period_at_slot(block.message.slot)

    assert attested_state.slot == attested_state.latest_block_header.slot
    attested_header = attested_state.latest_block_header.copy()
    attested_header.state_root = hash_tree_root(attested_state)
    assert (
        hash_tree_root(attested_header)
        == hash_tree_root(attested_block.message)
        == block.message.parent_root
    )
    update_attested_period = compute_sync_committee_period_at_slot(
        attested_block.message.slot
    )

    update = LightClientUpdate()

    update.attested_header = block_to_light_client_header(attested_block)

    # `next_sync_committee` is only useful if the message is signed by the current sync committee
    if update_attested_period == update_signature_period:
        update.next_sync_committee = attested_state.next_sync_committee
        update.next_sync_committee_branch = NextSyncCommitteeBranch(
            compute_merkle_proof(
                attested_state, next_sync_committee_gindex_at_slot(attested_state.slot)
            )
        )

    # Indicate finality whenever possible
    if finalized_block is not None:
        if finalized_block.message.slot != GENESIS_SLOT:
            update.finalized_header = block_to_light_client_header(finalized_block)
            assert (
                hash_tree_root(update.finalized_header.beacon)
                == attested_state.finalized_checkpoint.root
            )
        else:
            assert attested_state.finalized_checkpoint.root == Bytes32()
        update.finality_branch = FinalityBranch(
            compute_merkle_proof(
                attested_state, finalized_root_gindex_at_slot(attested_state.slot)
            )
        )

    update.sync_aggregate = block.message.body.sync_aggregate
    update.signature_slot = block.message.slot

    return update
```

Full nodes SHOULD provide the best derivable `LightClientUpdate` (according to `is_better_update`) for each sync committee period covering any epochs in range `[max(ALTAIR_FORK_EPOCH, current_epoch - MIN_EPOCHS_FOR_BLOCK_REQUESTS), current_epoch]` where `current_epoch` is defined by the current wall-clock time. Full nodes MAY also provide `LightClientUpdate` for other sync committee periods.

- `LightClientUpdate` are assigned to sync committee periods based on their `attested_header.beacon.slot`
- `LightClientUpdate` are only considered if `compute_sync_committee_period_at_slot(update.attested_header.beacon.slot) == compute_sync_committee_period_at_slot(update.signature_slot)`
- Only `LightClientUpdate` with `sync_aggregate` from blocks on the canonical chain as selected by fork choice are considered, regardless of ranking by `is_better_update`. `LightClientUpdate` referring to orphaned blocks SHOULD NOT be provided.

### `create_light_client_finality_update`

```python
def create_light_client_finality_update(
    update: LightClientUpdate,
) -> LightClientFinalityUpdate:
    return LightClientFinalityUpdate(
        attested_header=update.attested_header,
        finalized_header=update.finalized_header,
        finality_branch=update.finality_branch,
        sync_aggregate=update.sync_aggregate,
        signature_slot=update.signature_slot,
    )
```

Full nodes SHOULD provide the `LightClientFinalityUpdate` with the highest `attested_header.beacon.slot` (if multiple, highest `signature_slot`) as selected by fork choice, and SHOULD support a push mechanism to deliver new `LightClientFinalityUpdate` whenever `finalized_header` changes. If that `LightClientFinalityUpdate` does not have supermajority (> 2/3) sync committee participation, a second `LightClientFinalityUpdate` SHOULD be delivered for the same `finalized_header` once supermajority participation is obtained.

### `create_light_client_optimistic_update`

```python
def create_light_client_optimistic_update(
    update: LightClientUpdate,
) -> LightClientOptimisticUpdate:
    return LightClientOptimisticUpdate(
        attested_header=update.attested_header,
        sync_aggregate=update.sync_aggregate,
        signature_slot=update.signature_slot,
    )
```

Full nodes SHOULD provide the `LightClientOptimisticUpdate` with the highest `attested_header.beacon.slot` (if multiple, highest `signature_slot`) as selected by fork choice, and SHOULD support a push mechanism to deliver new `LightClientOptimisticUpdate` whenever `attested_header` changes.
