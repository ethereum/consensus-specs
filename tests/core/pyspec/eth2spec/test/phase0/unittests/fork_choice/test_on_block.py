from copy import deepcopy
from eth2spec.utils.ssz.ssz_impl import hash_tree_root

from eth2spec.test.context import with_all_phases, spec_state_test
from eth2spec.test.helpers.block import build_empty_block_for_next_slot, sign_block, transition_unsigned_block, \
    build_empty_block
from eth2spec.test.helpers.attestations import next_epoch_with_attestations
from eth2spec.test.helpers.state import next_epoch, state_transition_and_sign_block


def run_on_block(spec, store, signed_block, valid=True):
    if not valid:
        try:
            spec.on_block(store, signed_block)
        except AssertionError:
            return
        else:
            assert False

    spec.on_block(store, signed_block)
    assert store.blocks[hash_tree_root(signed_block.message)] == signed_block.message


def apply_next_epoch_with_attestations(spec, state, store):
    _, new_signed_blocks, post_state = next_epoch_with_attestations(spec, state, True, False)
    for signed_block in new_signed_blocks:
        block = signed_block.message
        block_root = hash_tree_root(block)
        store.blocks[block_root] = block
        store.block_states[block_root] = post_state
        last_signed_block = signed_block
    spec.on_tick(store, store.time + state.slot * spec.SECONDS_PER_SLOT)
    return post_state, store, last_signed_block


@with_all_phases
@spec_state_test
def test_basic(spec, state):
    # Initialization
    store = spec.get_forkchoice_store(state)
    time = 100
    spec.on_tick(store, time)
    assert store.time == time

    # On receiving a block of `GENESIS_SLOT + 1` slot
    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block)
    run_on_block(spec, store, signed_block)

    # On receiving a block of next epoch
    store.time = time + spec.SECONDS_PER_SLOT * spec.SLOTS_PER_EPOCH
    block = build_empty_block(spec, state, state.slot + spec.SLOTS_PER_EPOCH)
    signed_block = state_transition_and_sign_block(spec, state, block)

    run_on_block(spec, store, signed_block)

    # TODO: add tests for justified_root and finalized_root


@with_all_phases
@spec_state_test
def test_on_block_checkpoints(spec, state):
    # Initialization
    store = spec.get_forkchoice_store(state)
    time = 100
    spec.on_tick(store, time)

    next_epoch(spec, state)
    spec.on_tick(store, store.time + state.slot * spec.SECONDS_PER_SLOT)
    state, store, last_signed_block = apply_next_epoch_with_attestations(spec, state, store)
    next_epoch(spec, state)
    spec.on_tick(store, store.time + state.slot * spec.SECONDS_PER_SLOT)
    last_block_root = hash_tree_root(last_signed_block.message)

    # Mock the finalized_checkpoint
    fin_state = store.block_states[last_block_root]
    fin_state.finalized_checkpoint = (
        store.block_states[last_block_root].current_justified_checkpoint
    )

    block = build_empty_block_for_next_slot(spec, fin_state)
    signed_block = state_transition_and_sign_block(spec, deepcopy(fin_state), block)
    run_on_block(spec, store, signed_block)


@with_all_phases
@spec_state_test
def test_on_block_future_block(spec, state):
    # Initialization
    store = spec.get_forkchoice_store(state)

    # do not tick time

    # Fail receiving block of `GENESIS_SLOT + 1` slot
    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block)
    run_on_block(spec, store, signed_block, False)


@with_all_phases
@spec_state_test
def test_on_block_bad_parent_root(spec, state):
    # Initialization
    store = spec.get_forkchoice_store(state)
    time = 100
    spec.on_tick(store, time)

    # Fail receiving block of `GENESIS_SLOT + 1` slot
    block = build_empty_block_for_next_slot(spec, state)
    transition_unsigned_block(spec, state, block)
    block.state_root = state.hash_tree_root()

    block.parent_root = b'\x45' * 32

    signed_block = sign_block(spec, state, block)

    run_on_block(spec, store, signed_block, False)


@with_all_phases
@spec_state_test
def test_on_block_before_finalized(spec, state):
    # Initialization
    store = spec.get_forkchoice_store(state)
    time = 100
    spec.on_tick(store, time)

    store.finalized_checkpoint = spec.Checkpoint(
        epoch=store.finalized_checkpoint.epoch + 2,
        root=store.finalized_checkpoint.root
    )

    # Fail receiving block of `GENESIS_SLOT + 1` slot
    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block)
    run_on_block(spec, store, signed_block, False)


@with_all_phases
@spec_state_test
def test_on_block_finalized_skip_slots(spec, state):
    # Initialization
    store = spec.get_forkchoice_store(state)
    time = 100
    spec.on_tick(store, time)

    store.finalized_checkpoint = spec.Checkpoint(
        epoch=store.finalized_checkpoint.epoch + 2,
        root=store.finalized_checkpoint.root
    )

    # Build block that includes the skipped slots up to finality in chain
    block = build_empty_block(spec, state, spec.compute_start_slot_at_epoch(store.finalized_checkpoint.epoch) + 2)
    signed_block = state_transition_and_sign_block(spec, state, block)
    spec.on_tick(store, store.time + state.slot * spec.SECONDS_PER_SLOT)
    run_on_block(spec, store, signed_block)


@with_all_phases
@spec_state_test
def test_on_block_finalized_skip_slots_not_in_skip_chain(spec, state):
    # Initialization
    next_epoch(spec, state)
    store = spec.get_forkchoice_store(state)

    store.finalized_checkpoint = spec.Checkpoint(
        epoch=store.finalized_checkpoint.epoch + 2,
        root=store.finalized_checkpoint.root
    )

    # First transition through the epoch to ensure no skipped slots
    state, store, last_signed_block = apply_next_epoch_with_attestations(spec, state, store)

    # Now build a block at later slot than finalized epoch
    # Includes finalized block in chain, but not at appropriate skip slot
    block = build_empty_block(spec, state, spec.compute_start_slot_at_epoch(store.finalized_checkpoint.epoch) + 2)
    signed_block = state_transition_and_sign_block(spec, state, block)
    spec.on_tick(store, store.time + state.slot * spec.SECONDS_PER_SLOT)
    run_on_block(spec, store, signed_block, False)


@with_all_phases
@spec_state_test
def test_on_block_update_justified_checkpoint_within_safe_slots(spec, state):
    # Initialization
    store = spec.get_forkchoice_store(state)
    time = 0
    spec.on_tick(store, time)

    next_epoch(spec, state)
    spec.on_tick(store, store.time + state.slot * spec.SECONDS_PER_SLOT)
    state, store, last_signed_block = apply_next_epoch_with_attestations(spec, state, store)
    next_epoch(spec, state)
    spec.on_tick(store, store.time + state.slot * spec.SECONDS_PER_SLOT)
    last_block_root = hash_tree_root(last_signed_block.message)

    # Mock the justified checkpoint
    just_state = store.block_states[last_block_root]
    new_justified = spec.Checkpoint(
        epoch=just_state.current_justified_checkpoint.epoch + 1,
        root=b'\x77' * 32,
    )
    just_state.current_justified_checkpoint = new_justified

    block = build_empty_block_for_next_slot(spec, just_state)
    signed_block = state_transition_and_sign_block(spec, deepcopy(just_state), block)
    assert spec.get_current_slot(store) % spec.SLOTS_PER_EPOCH < spec.SAFE_SLOTS_TO_UPDATE_JUSTIFIED
    run_on_block(spec, store, signed_block)

    assert store.justified_checkpoint == new_justified


@with_all_phases
@spec_state_test
def test_on_block_outside_safe_slots_and_multiple_better_justified(spec, state):
    # Initialization
    store = spec.get_forkchoice_store(state)
    time = 0
    spec.on_tick(store, time)

    next_epoch(spec, state)
    spec.on_tick(store, store.time + state.slot * spec.SECONDS_PER_SLOT)
    state, store, last_signed_block = apply_next_epoch_with_attestations(spec, state, store)
    next_epoch(spec, state)
    spec.on_tick(store, store.time + state.slot * spec.SECONDS_PER_SLOT)
    last_block_root = hash_tree_root(last_signed_block.message)

    # Mock justified block in store
    just_block = build_empty_block_for_next_slot(spec, state)
    # Slot is same as justified checkpoint so does not trigger an override in the store
    just_block.slot = spec.compute_start_slot_at_epoch(store.justified_checkpoint.epoch)
    store.blocks[just_block.hash_tree_root()] = just_block

    # Step time past safe slots
    spec.on_tick(store, store.time + spec.SAFE_SLOTS_TO_UPDATE_JUSTIFIED * spec.SECONDS_PER_SLOT)
    assert spec.get_current_slot(store) % spec.SLOTS_PER_EPOCH >= spec.SAFE_SLOTS_TO_UPDATE_JUSTIFIED

    previously_justified = store.justified_checkpoint

    # Add a series of new blocks with "better" justifications
    best_justified_checkpoint = spec.Checkpoint(epoch=0)
    for i in range(3, 0, -1):
        just_state = store.block_states[last_block_root]
        new_justified = spec.Checkpoint(
            epoch=previously_justified.epoch + i,
            root=just_block.hash_tree_root(),
        )
        if new_justified.epoch > best_justified_checkpoint.epoch:
            best_justified_checkpoint = new_justified

        just_state.current_justified_checkpoint = new_justified

        block = build_empty_block_for_next_slot(spec, just_state)
        signed_block = state_transition_and_sign_block(spec, deepcopy(just_state), block)

        run_on_block(spec, store, signed_block)

    assert store.justified_checkpoint == previously_justified
    # ensure the best from the series was stored
    assert store.best_justified_checkpoint == best_justified_checkpoint


@with_all_phases
@spec_state_test
def test_on_block_outside_safe_slots_but_finality(spec, state):
    # Initialization
    store = spec.get_forkchoice_store(state)
    time = 100
    spec.on_tick(store, time)

    next_epoch(spec, state)
    spec.on_tick(store, store.time + state.slot * spec.SECONDS_PER_SLOT)
    state, store, last_signed_block = apply_next_epoch_with_attestations(spec, state, store)
    next_epoch(spec, state)
    spec.on_tick(store, store.time + state.slot * spec.SECONDS_PER_SLOT)
    last_block_root = hash_tree_root(last_signed_block.message)

    # Mock justified block in store
    just_block = build_empty_block_for_next_slot(spec, state)
    # Slot is same as justified checkpoint so does not trigger an override in the store
    just_block.slot = spec.compute_start_slot_at_epoch(store.justified_checkpoint.epoch)
    store.blocks[just_block.hash_tree_root()] = just_block

    # Step time past safe slots
    spec.on_tick(store, store.time + spec.SAFE_SLOTS_TO_UPDATE_JUSTIFIED * spec.SECONDS_PER_SLOT)
    assert spec.get_current_slot(store) % spec.SLOTS_PER_EPOCH >= spec.SAFE_SLOTS_TO_UPDATE_JUSTIFIED

    # Mock justified and finalized update in state
    just_fin_state = store.block_states[last_block_root]
    new_justified = spec.Checkpoint(
        epoch=store.justified_checkpoint.epoch + 1,
        root=just_block.hash_tree_root(),
    )
    new_finalized = spec.Checkpoint(
        epoch=store.finalized_checkpoint.epoch + 1,
        root=just_block.parent_root,
    )
    just_fin_state.current_justified_checkpoint = new_justified
    just_fin_state.finalized_checkpoint = new_finalized

    # Build and add block that includes the new justified/finalized info
    block = build_empty_block_for_next_slot(spec, just_fin_state)
    signed_block = state_transition_and_sign_block(spec, deepcopy(just_fin_state), block)

    run_on_block(spec, store, signed_block)

    assert store.finalized_checkpoint == new_finalized
    assert store.justified_checkpoint == new_justified
