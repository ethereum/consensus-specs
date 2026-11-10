# PQ -- Fork Choice

*Note*: This document is a work-in-progress for researchers and implementers.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=6 --minlevel=2 -->

- [Introduction](#introduction)
- [Handlers](#handlers)
  - [Modified `on_block`](#modified-on_block)
  - [Modified `on_attestation`](#modified-on_attestation)
  - [Modified `on_payload_attestation_message`](#modified-on_payload_attestation_message)
- [Helpers](#helpers)

<!-- mdformat-toc end -->

## Introduction

This is the modification of the fork-choice accompanying the PQ upgrade.

Blocks no longer carry payload attestations, so the votes of the payload
timeliness committee reach fork choice only from the wire. Attestations no
longer carry a signature, so `on_attestation` no longer checks one.

## Handlers

### Modified `on_block`

```python
def on_block(store: Store, signed_block: SignedBeaconBlock) -> None:
    """
    Run ``on_block`` upon receiving a new block.
    """
    block = signed_block.message
    block_root = hash_tree_root(block)

    # Return early if the block is already known
    if block_root in store.blocks:
        return

    # Parent block must be known
    assert block.parent_root in store.block_states

    # If this block builds on the parent's full payload, that payload must
    # have been verified by on_execution_payload_envelope
    if is_parent_node_full(store, block):
        assert is_payload_verified(store, block.parent_root)

    # Blocks cannot be in the future. If they are, their consideration must be delayed until they are in the past.
    current_slot = get_current_slot(store)
    assert current_slot >= block.slot

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

    # Make a copy of the state to avoid mutability issues
    state = store.block_states[block.parent_root].copy()

    # Check the block is valid and compute the post-state
    state_transition(state, signed_block, validate_result=True)

    # Compute head before applying the block
    head = get_head(store)
    # Add new block to the store
    store.blocks[block_root] = block
    # Add new state for this block to the store
    store.block_states[block_root] = state
    # Add a new PTC voting for this block to the store
    store.payload_timeliness_vote[block_root] = [None] * PTC_SIZE
    store.payload_data_availability_vote[block_root] = [None] * PTC_SIZE

    # [Modified in PQ]
    # Removed `notify_ptc_messages`

    record_block_timeliness(store, block_root)
    update_proposer_boost_root(store, head.root, block_root)

    # Update checkpoints in store if necessary
    update_checkpoints(store, state.current_justified_checkpoint, state.finalized_checkpoint)

    # Eagerly compute unrealized justification and finality.
    compute_pulled_up_tip(store, block_root)
```

### Modified `on_attestation`

*Note*: An attestation carries no signature. Gossip validation checks the
signature or `proof` of an attestation from the wire, and `process_stark` proves
the signatures of the attestations in a block, so `on_attestation` only checks
that an attestation has attesters.

```python
def on_attestation(store: Store, attestation: Attestation, is_from_block: bool = False) -> None:
    """
    Run ``on_attestation`` upon receiving a new attestation from either within a block or directly on the wire.

    An ``attestation`` that is asserted as invalid may be valid at a later time,
    consider scheduling it for later processing in such case.
    """
    validate_on_attestation(store, attestation, is_from_block)

    store_target_checkpoint_state(store, attestation.data.target)

    # Get state at the `target` to fully validate attestation
    target_state = store.checkpoint_states[attestation.data.target]
    # [Modified in PQ]
    attesting_indices = sorted(get_attesting_indices(target_state, attestation))
    assert len(attesting_indices) > 0

    # [Modified in PQ]
    # Update latest messages for attesting indices
    update_latest_messages(store, attesting_indices, attestation)
```

### Modified `on_payload_attestation_message`

*Note*: A payload attestation message now always comes from the wire, so its
slot and signature are always checked. The signature is checked with
`xmss.Verify`, since `IndexedPayloadAttestation` is deprecated.

```python
def on_payload_attestation_message(
    store: Store,
    ptc_message: PayloadAttestationMessage,
    # [Modified in PQ]
    # Removed `is_from_block`
) -> None:
    """
    Run ``on_payload_attestation_message`` upon receiving a new payload attestation message.
    """
    data = ptc_message.data

    # PTC attestation must be for a known block. If block is unknown, delay consideration until the block is found
    assert data.beacon_block_root in store.block_states
    state = store.block_states[data.beacon_block_root]

    # PTC votes can only change the vote for their assigned beacon block, return early otherwise
    if data.slot != state.slot:
        return

    # Get all positions of the attester in the PTC
    ptc_indices = []
    ptc = get_ptc(state, data.slot)
    for ptc_index, validator_index in enumerate(ptc):
        if validator_index == ptc_message.validator_index:
            ptc_indices.append(ptc_index)

    # Check that the attester is from the PTC
    assert len(ptc_indices) > 0

    # [Modified in PQ]
    # Check that the attestation is for the current slot
    assert data.slot == get_current_slot(store)
    # Verify the signature
    domain = get_domain(state, DOMAIN_PTC_ATTESTER, compute_epoch_at_slot(data.slot))
    signing_root = compute_signing_root(data, domain)
    leaf_index = compute_xmss_leaf_index(data.slot, LEAF_OFFSET_PTC_ATTESTER)
    pubkey = state.validators[ptc_message.validator_index].pubkey
    assert xmss.Verify(pubkey, leaf_index, signing_root, ptc_message.signature)

    # Update the votes for the block
    payload_timeliness_vote = store.payload_timeliness_vote[data.beacon_block_root]
    payload_data_availability_vote = store.payload_data_availability_vote[data.beacon_block_root]
    for ptc_index in ptc_indices:
        payload_timeliness_vote[ptc_index] = data.payload_present
        payload_data_availability_vote[ptc_index] = data.blob_data_available
```

## Helpers
