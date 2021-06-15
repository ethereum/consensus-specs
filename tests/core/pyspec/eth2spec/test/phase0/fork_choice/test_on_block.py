from eth2spec.utils.ssz.ssz_impl import hash_tree_root

from eth2spec.test.context import MINIMAL, spec_state_test, with_all_phases, with_presets
from eth2spec.test.helpers.attestations import next_epoch_with_attestations
from eth2spec.test.helpers.block import build_empty_block_for_next_slot, build_empty_block
from eth2spec.test.helpers.fork_choice import (
    get_genesis_forkchoice_store_and_block,
    on_tick_and_append_step,
    run_on_block,
    tick_and_run_on_block,
)
from eth2spec.test.helpers.state import next_epoch, state_transition_and_sign_block


def apply_next_epoch_with_attestations(spec, state, store, test_steps=None):
    if test_steps is None:
        test_steps = []

    _, new_signed_blocks, post_state = next_epoch_with_attestations(spec, state, True, False)
    for signed_block in new_signed_blocks:
        block = signed_block.message
        block_root = hash_tree_root(block)
        store.blocks[block_root] = block
        store.block_states[block_root] = post_state
        yield from tick_and_run_on_block(spec, store, signed_block, test_steps)
        last_signed_block = signed_block

    return post_state, store, last_signed_block


@with_all_phases
@spec_state_test
def test_basic(spec, state):
    # Initialization
    test_steps = []
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield 'anchor_state', state
    yield 'anchor_block', anchor_block
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    assert store.time == current_time

    # On receiving a block of `GENESIS_SLOT + 1` slot
    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block)
    yield from tick_and_run_on_block(spec, store, signed_block, test_steps)
    assert spec.get_head(store) == signed_block.message.hash_tree_root()

    # On receiving a block of next epoch
    store.time = current_time + spec.config.SECONDS_PER_SLOT * spec.SLOTS_PER_EPOCH
    block = build_empty_block(spec, state, state.slot + spec.SLOTS_PER_EPOCH)
    signed_block = state_transition_and_sign_block(spec, state, block)
    yield from tick_and_run_on_block(spec, store, signed_block, test_steps)
    assert spec.get_head(store) == signed_block.message.hash_tree_root()

    yield 'steps', test_steps

    # TODO: add tests for justified_root and finalized_root


@with_all_phases
@with_presets([MINIMAL], reason="too slow")
@spec_state_test
def test_on_block_checkpoints(spec, state):
    test_steps = []
    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield 'anchor_state', state
    yield 'anchor_block', anchor_block
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    assert store.time == current_time

    # Run for 1 epoch with full attestations
    next_epoch(spec, state)
    on_tick_and_append_step(spec, store, store.time + state.slot * spec.config.SECONDS_PER_SLOT, test_steps)
    state, store, last_signed_block = yield from apply_next_epoch_with_attestations(spec, state, store, test_steps)
    last_block_root = hash_tree_root(last_signed_block.message)
    assert spec.get_head(store) == last_block_root

    # Forward 1 epoch
    next_epoch(spec, state)
    on_tick_and_append_step(spec, store, store.time + state.slot * spec.config.SECONDS_PER_SLOT, test_steps)

    # Mock the finalized_checkpoint and build a block on it
    fin_state = store.block_states[last_block_root]
    fin_state.finalized_checkpoint = (
        store.block_states[last_block_root].current_justified_checkpoint
    )

    block = build_empty_block_for_next_slot(spec, fin_state)
    signed_block = state_transition_and_sign_block(spec, fin_state.copy(), block)
    yield from tick_and_run_on_block(spec, store, signed_block, test_steps)
    assert spec.get_head(store) == signed_block.message.hash_tree_root()
    yield 'steps', test_steps


@with_all_phases
@spec_state_test
def test_on_block_future_block(spec, state):
    test_steps = []
    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield 'anchor_state', state
    yield 'anchor_block', anchor_block
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    assert store.time == current_time

    # do not tick time

    # Fail receiving block of `GENESIS_SLOT + 1` slot
    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block)
    run_on_block(spec, store, signed_block, test_steps, valid=False)

    yield 'steps', test_steps


# @with_all_phases
# @spec_state_test
# def test_on_block_bad_parent_root(spec, state):
#     test_steps = []
#     # Initialization
#     store = get_genesis_forkchoice_store(spec, state)
#     time = 100
#     on_tick_and_append_step(spec, store, time, test_steps)

#     # Fail receiving block of `GENESIS_SLOT + 1` slot
#     block = build_empty_block_for_next_slot(spec, state)
#     transition_unsigned_block(spec, state, block)
#     block.state_root = state.hash_tree_root()

#     block.parent_root = b'\x45' * 32

#     signed_block = sign_block(spec, state, block)

#     run_on_block(spec, store, signed_block, test_steps, valid=False)


# @with_all_phases
# @spec_state_test
# def test_on_block_before_finalized(spec, state):
#     test_steps = []
#     # Initialization
#     store = get_genesis_forkchoice_store(spec, state)
#     time = 100
#     on_tick_and_append_step(spec, store, time, test_steps)

#     store.finalized_checkpoint = spec.Checkpoint(
#         epoch=store.finalized_checkpoint.epoch + 2,
#         root=store.finalized_checkpoint.root
#     )

#     # Fail receiving block of `GENESIS_SLOT + 1` slot
#     block = build_empty_block_for_next_slot(spec, state)
#     signed_block = state_transition_and_sign_block(spec, state, block)
#     run_on_block(spec, store, signed_block, test_steps, valid=False)


# @with_all_phases
# @spec_state_test
# def test_on_block_finalized_skip_slots(spec, state):
#     test_steps = []
#     # Initialization
#     store = get_genesis_forkchoice_store(spec, state)
#     time = 100
#     on_tick_and_append_step(spec, store, time, test_steps)

#     store.finalized_checkpoint = spec.Checkpoint(
#         epoch=store.finalized_checkpoint.epoch + 2,
#         root=store.finalized_checkpoint.root
#     )

#     # Build block that includes the skipped slots up to finality in chain
#     block = build_empty_block(spec, state, spec.compute_start_slot_at_epoch(store.finalized_checkpoint.epoch) + 2)
#     signed_block = state_transition_and_sign_block(spec, state, block)
#     on_tick_and_append_step(spec, store, store.time + state.slot * spec.config.SECONDS_PER_SLOT, test_steps)
#     run_on_block(spec, store, signed_block, test_steps)


# @with_all_phases
# @spec_state_test
# def test_on_block_finalized_skip_slots_not_in_skip_chain(spec, state):
#     test_steps = []
#     # Initialization
#     transition_to(spec, state, state.slot + spec.SLOTS_PER_EPOCH - 1)
#     block = build_empty_block_for_next_slot(spec, state)
#     transition_unsigned_block(spec, state, block)
#     block.state_root = state.hash_tree_root()
#     store = spec.get_forkchoice_store(state, block)
#     store.finalized_checkpoint = spec.Checkpoint(
#         epoch=store.finalized_checkpoint.epoch + 2,
#         root=store.finalized_checkpoint.root
#     )

#     # First transition through the epoch to ensure no skipped slots
#     state, store, _ = apply_next_epoch_with_attestations(spec, state, store)

#     # Now build a block at later slot than finalized epoch
#     # Includes finalized block in chain, but not at appropriate skip slot
#     block = build_empty_block(spec, state, spec.compute_start_slot_at_epoch(store.finalized_checkpoint.epoch) + 2)
#     signed_block = state_transition_and_sign_block(spec, state, block)
#     on_tick_and_append_step(spec, store, store.time + state.slot * spec.config.SECONDS_PER_SLOT, test_steps)
#     run_on_block(spec, store, signed_block, test_steps, valid=False)


# @with_all_phases
# @spec_state_test
# def test_on_block_update_justified_checkpoint_within_safe_slots(spec, state):
#     test_steps = []
#     # Initialization
#     store = get_genesis_forkchoice_store(spec, state)
#     time = 0
#     on_tick_and_append_step(spec, store, time, test_steps)

#     next_epoch(spec, state)
#     on_tick_and_append_step(spec, store, store.time + state.slot * spec.config.SECONDS_PER_SLOT, test_steps)
#     state, store, last_signed_block = apply_next_epoch_with_attestations(spec, state, store)
#     next_epoch(spec, state)
#     on_tick_and_append_step(spec, store, store.time + state.slot * spec.config.SECONDS_PER_SLOT, test_steps)
#     last_block_root = hash_tree_root(last_signed_block.message)

#     # Mock the justified checkpoint
#     just_state = store.block_states[last_block_root]
#     new_justified = spec.Checkpoint(
#         epoch=just_state.current_justified_checkpoint.epoch + 1,
#         root=b'\x77' * 32,
#     )
#     just_state.current_justified_checkpoint = new_justified

#     block = build_empty_block_for_next_slot(spec, just_state)
#     signed_block = state_transition_and_sign_block(spec, deepcopy(just_state), block)
#     assert spec.get_current_slot(store) % spec.SLOTS_PER_EPOCH < spec.SAFE_SLOTS_TO_UPDATE_JUSTIFIED
#     run_on_block(spec, store, signed_block, test_steps)

#     assert store.justified_checkpoint == new_justified


# @with_all_phases
# @spec_state_test
# def test_on_block_outside_safe_slots_and_multiple_better_justified(spec, state):
#     test_steps = []
#     # Initialization
#     store = get_genesis_forkchoice_store(spec, state)
#     time = 0
#     on_tick_and_append_step(spec, store, time, test_steps)

#     next_epoch(spec, state)
#     on_tick_and_append_step(spec, store, store.time + state.slot * spec.config.SECONDS_PER_SLOT, test_steps)
#     state, store, last_signed_block = apply_next_epoch_with_attestations(spec, state, store)
#     next_epoch(spec, state)
#     on_tick_and_append_step(spec, store, store.time + state.slot * spec.config.SECONDS_PER_SLOT, test_steps)
#     last_block_root = hash_tree_root(last_signed_block.message)

#     # Mock justified block in store
#     just_block = build_empty_block_for_next_slot(spec, state)
#     # Slot is same as justified checkpoint so does not trigger an override in the store
#     just_block.slot = spec.compute_start_slot_at_epoch(store.justified_checkpoint.epoch)
#     store.blocks[just_block.hash_tree_root()] = just_block

#     # Step time past safe slots
#     time = store.time + spec.SAFE_SLOTS_TO_UPDATE_JUSTIFIED * spec.config.SECONDS_PER_SLOT
#     on_tick_and_append_step(spec, store, time, test_steps)
#     assert spec.get_current_slot(store) % spec.SLOTS_PER_EPOCH >= spec.SAFE_SLOTS_TO_UPDATE_JUSTIFIED

#     previously_justified = store.justified_checkpoint

#     # Add a series of new blocks with "better" justifications
#     best_justified_checkpoint = spec.Checkpoint(epoch=0)
#     for i in range(3, 0, -1):
#         just_state = store.block_states[last_block_root]
#         new_justified = spec.Checkpoint(
#             epoch=previously_justified.epoch + i,
#             root=just_block.hash_tree_root(),
#         )
#         if new_justified.epoch > best_justified_checkpoint.epoch:
#             best_justified_checkpoint = new_justified

#         just_state.current_justified_checkpoint = new_justified

#         block = build_empty_block_for_next_slot(spec, just_state)
#         signed_block = state_transition_and_sign_block(spec, deepcopy(just_state), block)

#         run_on_block(spec, store, signed_block, test_steps)

#     assert store.justified_checkpoint == previously_justified
#     # ensure the best from the series was stored
#     assert store.best_justified_checkpoint == best_justified_checkpoint


# @with_all_phases
# @spec_state_test
# def test_on_block_outside_safe_slots_but_finality(spec, state):
#     test_steps = []
#     # Initialization
#     store = get_genesis_forkchoice_store(spec, state)
#     time = 100
#     on_tick_and_append_step(spec, store, time, test_steps)

#     next_epoch(spec, state)
#     on_tick_and_append_step(spec, store, store.time + state.slot * spec.config.SECONDS_PER_SLOT, test_steps)
#     state, store, last_signed_block = apply_next_epoch_with_attestations(spec, state, store)
#     next_epoch(spec, state)
#     on_tick_and_append_step(spec, store, store.time + state.slot * spec.config.SECONDS_PER_SLOT, test_steps)
#     last_block_root = hash_tree_root(last_signed_block.message)

#     # Mock justified block in store
#     just_block = build_empty_block_for_next_slot(spec, state)
#     # Slot is same as justified checkpoint so does not trigger an override in the store
#     just_block.slot = spec.compute_start_slot_at_epoch(store.justified_checkpoint.epoch)
#     store.blocks[just_block.hash_tree_root()] = just_block

#     # Step time past safe slots
#     time = store.time + spec.SAFE_SLOTS_TO_UPDATE_JUSTIFIED * spec.config.SECONDS_PER_SLOT
#     on_tick_and_append_step(spec, store, time, test_steps)
#     assert spec.get_current_slot(store) % spec.SLOTS_PER_EPOCH >= spec.SAFE_SLOTS_TO_UPDATE_JUSTIFIED

#     # Mock justified and finalized update in state
#     just_fin_state = store.block_states[last_block_root]
#     new_justified = spec.Checkpoint(
#         epoch=store.justified_checkpoint.epoch + 1,
#         root=just_block.hash_tree_root(),
#     )
#     new_finalized = spec.Checkpoint(
#         epoch=store.finalized_checkpoint.epoch + 1,
#         root=just_block.parent_root,
#     )
#     just_fin_state.current_justified_checkpoint = new_justified
#     just_fin_state.finalized_checkpoint = new_finalized

#     # Build and add block that includes the new justified/finalized info
#     block = build_empty_block_for_next_slot(spec, just_fin_state)
#     signed_block = state_transition_and_sign_block(spec, deepcopy(just_fin_state), block)

#     run_on_block(spec, store, signed_block, test_steps)

#     assert store.finalized_checkpoint == new_finalized
#     assert store.justified_checkpoint == new_justified
