from eth2spec.test.context import spec_state_test, with_all_phases
from eth2spec.test.helpers.block import (
    build_empty_block_for_next_slot,
)
from eth2spec.test.helpers.fork_choice import get_genesis_forkchoice_store
from eth2spec.test.helpers.state import (
    next_epoch,
    state_transition_and_sign_block,
    transition_to,
)


def run_on_tick(spec, store, time, new_justified_checkpoint=False):
    previous_justified_checkpoint = store.justified_checkpoint

    spec.on_tick(store, time)

    assert store.time == time

    if new_justified_checkpoint:
        assert store.justified_checkpoint.epoch > previous_justified_checkpoint.epoch
        assert store.justified_checkpoint.root != previous_justified_checkpoint.root
    else:
        assert store.justified_checkpoint == previous_justified_checkpoint


@with_all_phases
@spec_state_test
def test_basic(spec, state):
    store = get_genesis_forkchoice_store(spec, state)
    run_on_tick(spec, store, store.time + 1)


"""
@with_all_phases
@spec_state_test
def test_update_justified_single_on_store_finalized_chain(spec, state):
    store = get_genesis_forkchoice_store(spec, state)

    # Create a block at epoch 1
    next_epoch(spec, state)
    block = build_empty_block_for_next_slot(spec, state)
    state_transition_and_sign_block(spec, state, block)
    store.blocks[block.hash_tree_root()] = block.copy()
    store.block_states[block.hash_tree_root()] = state.copy()
    parent_block = block.copy()
    # To make compute_slots_since_epoch_start(current_slot) == 0, transition to the end of the epoch
    slot = state.slot + spec.SLOTS_PER_EPOCH - state.slot % spec.SLOTS_PER_EPOCH - 1
    transition_to(spec, state, slot)
    # Create a block at the start of epoch 2
    block = build_empty_block_for_next_slot(spec, state)
    # Mock state
    state.current_justified_checkpoint = spec.Checkpoint(
        epoch=spec.compute_epoch_at_slot(parent_block.slot),
        root=parent_block.hash_tree_root(),
    )
    state_transition_and_sign_block(spec, state, block)
    store.blocks[block.hash_tree_root()] = block
    store.block_states[block.hash_tree_root()] = state

    run_on_tick(
        spec,
        store,
        store.genesis_time + state.slot * spec.config.SECONDS_PER_SLOT,
        new_justified_checkpoint=True
    )
"""


@with_all_phases
@spec_state_test
def test_update_justified_single_not_on_store_finalized_chain(spec, state):
    store = get_genesis_forkchoice_store(spec, state)
    init_state = state.copy()

    # Chain grows
    # Create a block at epoch 1
    next_epoch(spec, state)
    block = build_empty_block_for_next_slot(spec, state)
    block.body.graffiti = b"\x11" * 32
    state_transition_and_sign_block(spec, state, block)
    store.blocks[block.hash_tree_root()] = block.copy()
    store.block_states[block.hash_tree_root()] = state.copy()
    # Mock store.finalized_checkpoint
    store.finalized_checkpoint = spec.Checkpoint(
        epoch=spec.compute_epoch_at_slot(block.slot),
        root=block.hash_tree_root(),
    )

    # Create a block at epoch 1
    state = init_state.copy()
    next_epoch(spec, state)
    block = build_empty_block_for_next_slot(spec, state)
    block.body.graffiti = b"\x22" * 32
    state_transition_and_sign_block(spec, state, block)
    store.blocks[block.hash_tree_root()] = block.copy()
    store.block_states[block.hash_tree_root()] = state.copy()
    parent_block = block.copy()
    # To make compute_slots_since_epoch_start(current_slot) == 0, transition to the end of the epoch
    slot = state.slot + spec.SLOTS_PER_EPOCH - state.slot % spec.SLOTS_PER_EPOCH - 1
    transition_to(spec, state, slot)
    # Create a block at the start of epoch 2
    block = build_empty_block_for_next_slot(spec, state)
    # Mock state
    state.current_justified_checkpoint = spec.Checkpoint(
        epoch=spec.compute_epoch_at_slot(parent_block.slot),
        root=parent_block.hash_tree_root(),
    )
    state_transition_and_sign_block(spec, state, block)
    store.blocks[block.hash_tree_root()] = block.copy()
    store.block_states[block.hash_tree_root()] = state.copy()

    run_on_tick(
        spec,
        store,
        store.genesis_time + state.slot * spec.config.SECONDS_PER_SLOT,
    )
