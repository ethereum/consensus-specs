from eth_consensus_specs.test.helpers.attestations import (
    state_transition_with_full_block,
)
from eth_consensus_specs.test.helpers.block import build_empty_block_for_next_slot
from eth_consensus_specs.test.helpers.execution_payload_bid import (
    prepare_signed_execution_payload_bid,
)
from eth_consensus_specs.test.helpers.fork_choice import (
    get_genesis_forkchoice_store_and_block,
)
from eth_consensus_specs.test.helpers.gossip import get_filename, wrap_genesis_block
from eth_consensus_specs.test.helpers.keys import builder_privkeys
from eth_consensus_specs.test.helpers.state import state_transition_and_sign_block


def activate_builders(spec, state, store, blocks):
    """
    Make every builder active by finalizing epoch 1, so that the builders'
    ``deposit_epoch`` (0 at genesis) is less than the finalized epoch.

    A replayed chain of empty blocks never finalizes, so this cannot be baked
    into the anchor state (a genesis state with a non-zero finalized epoch
    underflows ``get_finality_delay`` during epoch processing). Instead, both
    the store's and the head state's finalized checkpoints are set here, and
    the returned ``finalized_checkpoint`` meta entry communicates the same
    override to fixture consumers.
    """
    head_root = blocks[-1].message.hash_tree_root()
    checkpoint_root = spec.get_checkpoint_block(store, head_root, spec.Epoch(1))
    checkpoint = spec.Checkpoint(epoch=spec.Epoch(1), root=checkpoint_root)
    state.finalized_checkpoint = checkpoint
    store.finalized_checkpoint = checkpoint
    signed_block = next(b for b in blocks if b.message.hash_tree_root() == checkpoint_root)
    return {"epoch": 1, "block": get_filename(signed_block)}


def setup_store_advanced_for_bid(spec, state):
    """
    Advance ``state`` to at least the (MIN_SEED_LOOKAHEAD + 1)-th epoch so
    bid validation's dependent_root lookup doesn't underflow, then build a
    genesis store containing every produced block and its state.
    Returns (store, blocks, parent_block_root).
    """
    return _build_store_advanced_to(
        spec,
        state,
        spec.compute_start_slot_at_epoch(spec.Epoch(spec.MIN_SEED_LOOKAHEAD + 1)),
    )


def setup_store_advanced_to_epoch_end(spec, state):
    """
    Like ``setup_store_advanced_for_bid``, but stop at the last slot of an epoch
    so that a bid for the next slot (the first slot of the following epoch)
    forces the validation function to advance the state across an epoch
    boundary. Returns (store, blocks, parent_block_root).
    """
    target_slot = spec.Slot(
        spec.compute_start_slot_at_epoch(spec.Epoch(spec.MIN_SEED_LOOKAHEAD + 2)) - 1
    )
    return _build_store_advanced_to(spec, state, target_slot)


def _build_store_advanced_to(spec, state, target_slot):
    """Build a genesis store and advance ``state`` to ``target_slot`` with empty
    blocks, recording every produced block and its post-state in the store."""
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    blocks = [signed_anchor]
    while state.slot < target_slot:
        block = build_empty_block_for_next_slot(spec, state)
        signed_block = state_transition_and_sign_block(spec, state, block)
        block_root = signed_block.message.hash_tree_root()
        store.blocks[block_root] = signed_block.message
        store.block_states[block_root] = state.copy()
        blocks.append(signed_block)
    return store, blocks, blocks[-1].message.hash_tree_root()


def setup_store_finalized_with_pending_payment(spec, state):
    """
    Build a chain in which epoch 1 finalizes organically (blocks with full
    attestations), so that builders are active without any finalized
    checkpoint override. A block at the first slot of the next epoch then
    carries a real (value-bearing) builder-0 bid, recording a sub-quorum
    pending payment, and empty blocks follow up to the last slot of the
    following epoch.

    At the returned head, the payment sits in the previous-epoch half of the
    pending-payments queue with zero weight: it counts against the builder's
    coverage until the next epoch transition drops it.

    Returns (store, blocks, parent_block_root, builder_index, pending_value).
    """
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    signed_anchor = wrap_genesis_block(spec, anchor_block)
    blocks = [signed_anchor]

    def record(signed_block):
        block_root = signed_block.message.hash_tree_root()
        store.blocks[block_root] = signed_block.message
        store.block_states[block_root] = state.copy()
        blocks.append(signed_block)

    # Finalize organically: builders activate once their deposit epoch (0)
    # is strictly before the finalized epoch.
    while state.finalized_checkpoint.epoch < 1:
        record(
            state_transition_with_full_block(spec, state, fill_cur_epoch=True, fill_prev_epoch=True)
        )
    assert spec.is_active_builder(state, spec.BuilderIndex(0))

    # Empty blocks up to the last slot before the payment's epoch.
    bid_block_slot = spec.compute_start_slot_at_epoch(
        spec.Epoch(spec.compute_epoch_at_slot(state.slot) + 1)
    )
    while state.slot < bid_block_slot - 1:
        record(
            state_transition_and_sign_block(
                spec, state, build_empty_block_for_next_slot(spec, state)
            )
        )

    # The pending-payment block: a real builder-0 bid with a 1 Gwei value.
    builder_index = spec.BuilderIndex(0)
    pending_value = spec.Gwei(1)
    signed_bid = prepare_signed_execution_payload_bid(
        spec, state.copy(), builder_index=builder_index, value=pending_value, slot=bid_block_slot
    )
    block = build_empty_block_for_next_slot(spec, state)
    block.body.signed_execution_payload_bid = signed_bid
    record(state_transition_and_sign_block(spec, state, block))

    # Empty blocks to the last slot of the following epoch: the payment has
    # then shifted into the previous-epoch half of the queue.
    head_slot = spec.Slot(
        spec.compute_start_slot_at_epoch(spec.Epoch(spec.compute_epoch_at_slot(bid_block_slot) + 2))
        - 1
    )
    while state.slot < head_slot:
        record(
            state_transition_and_sign_block(
                spec, state, build_empty_block_for_next_slot(spec, state)
            )
        )
    payment = state.builder_pending_payments[bid_block_slot % spec.SLOTS_PER_EPOCH]
    assert payment.withdrawal.amount == pending_value

    # Mirror what importing the blocks does to the store's finalized checkpoint.
    store.finalized_checkpoint = state.finalized_checkpoint

    return store, blocks, blocks[-1].message.hash_tree_root(), builder_index, pending_value


def build_signed_bid(
    spec,
    state,
    builder_index,
    slot,
    parent_block_hash,
    parent_block_root,
    fee_recipient=None,
    gas_limit=None,
    value=None,
    execution_payment=None,
    prev_randao=None,
    valid_signature=True,
):
    """Construct a SignedExecutionPayloadBid."""
    bid = spec.ExecutionPayloadBid(
        parent_block_hash=parent_block_hash,
        parent_block_root=parent_block_root,
        block_hash=spec.Hash32(b"\x02" + b"\x00" * 31),
        prev_randao=prev_randao
        if prev_randao is not None
        else spec.get_randao_mix(state, spec.get_current_epoch(state)),
        fee_recipient=fee_recipient
        if fee_recipient is not None
        else spec.ExecutionAddress(b"\x11" * 20),
        gas_limit=gas_limit if gas_limit is not None else spec.uint64(30_000_000),
        builder_index=builder_index,
        slot=slot,
        value=value if value is not None else spec.Gwei(0),
        execution_payment=execution_payment if execution_payment is not None else spec.Gwei(0),
        # blob_kzg_commitments defaults to the field's own (progressive) type.
        # Constructing it as a bounded List would change the hash tree root
        # and invalidate the signature for consumers decoding the vector.
        execution_requests_root=spec.hash_tree_root(spec.ExecutionRequests()),
    )
    if valid_signature and builder_index < len(builder_privkeys):
        privkey = builder_privkeys[builder_index]
        signature = spec.get_execution_payload_bid_signature(state, bid, privkey)
    else:
        signature = spec.BLSSignature()
    return spec.SignedExecutionPayloadBid(message=bid, signature=signature)
