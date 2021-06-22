from eth2spec.utils.ssz.ssz_impl import hash_tree_root

from eth2spec.test.context import MINIMAL, spec_state_test, with_all_phases, with_presets
from eth2spec.test.helpers.block import (
    build_empty_block_for_next_slot,
    build_empty_block,
    transition_unsigned_block,
    sign_block,
)
from eth2spec.test.helpers.fork_choice import (
    get_genesis_forkchoice_store_and_block,
    on_tick_and_append_step,
    add_block,
    tick_and_add_block,
    apply_next_epoch_with_attestations,
)
from eth2spec.test.helpers.state import (
    next_epoch,
    state_transition_and_sign_block,
    transition_to,
)


@with_all_phases
@spec_state_test
def test_basic(spec, state):
    test_steps = []
    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield 'anchor_state', state
    yield 'anchor_block', anchor_block
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    assert store.time == current_time

    # On receiving a block of `GENESIS_SLOT + 1` slot
    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block)
    yield from tick_and_add_block(spec, store, signed_block, test_steps)
    assert spec.get_head(store) == signed_block.message.hash_tree_root()

    # On receiving a block of next epoch
    store.time = current_time + spec.config.SECONDS_PER_SLOT * spec.SLOTS_PER_EPOCH
    block = build_empty_block(spec, state, state.slot + spec.SLOTS_PER_EPOCH)
    signed_block = state_transition_and_sign_block(spec, state, block)
    yield from tick_and_add_block(spec, store, signed_block, test_steps)
    assert spec.get_head(store) == signed_block.message.hash_tree_root()

    yield 'steps', test_steps

    # TODO: add tests for justified_root and finalized_root


@with_all_phases
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
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
    fin_state = store.block_states[last_block_root].copy()
    fin_state.finalized_checkpoint = store.block_states[last_block_root].current_justified_checkpoint.copy()

    block = build_empty_block_for_next_slot(spec, fin_state)
    signed_block = state_transition_and_sign_block(spec, fin_state.copy(), block)
    yield from tick_and_add_block(spec, store, signed_block, test_steps)
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

    # Do NOT tick time to `GENESIS_SLOT + 1` slot
    # Fail receiving block of `GENESIS_SLOT + 1` slot
    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block)
    yield from add_block(spec, store, signed_block, test_steps, valid=False)

    yield 'steps', test_steps


@with_all_phases
@spec_state_test
def test_on_block_bad_parent_root(spec, state):
    test_steps = []
    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield 'anchor_state', state
    yield 'anchor_block', anchor_block
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    assert store.time == current_time

    # Fail receiving block of `GENESIS_SLOT + 1` slot
    block = build_empty_block_for_next_slot(spec, state)
    transition_unsigned_block(spec, state, block)
    block.state_root = state.hash_tree_root()

    block.parent_root = b'\x45' * 32

    signed_block = sign_block(spec, state, block)

    yield from add_block(spec, store, signed_block, test_steps, valid=False)

    yield 'steps', test_steps


@with_all_phases
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_on_block_before_finalized(spec, state):
    test_steps = []
    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield 'anchor_state', state
    yield 'anchor_block', anchor_block
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    assert store.time == current_time

    # Fork
    another_state = state.copy()

    # Create a finalized chain
    for _ in range(4):
        state, store, _ = yield from apply_next_epoch_with_attestations(spec, state, store, test_steps)
    assert store.finalized_checkpoint.epoch == 2

    # Fail receiving block of `GENESIS_SLOT + 1` slot
    block = build_empty_block_for_next_slot(spec, another_state)
    block.body.graffiti = b'\x12' * 32
    signed_block = state_transition_and_sign_block(spec, another_state, block)
    assert signed_block.message.hash_tree_root() not in store.blocks
    yield from tick_and_add_block(spec, store, signed_block, test_steps, valid=False)

    yield 'steps', test_steps


@with_all_phases
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_on_block_finalized_skip_slots(spec, state):
    test_steps = []
    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield 'anchor_state', state
    yield 'anchor_block', anchor_block
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    assert store.time == current_time

    # Create a finalized chain
    for _ in range(4):
        state, store, _ = yield from apply_next_epoch_with_attestations(spec, state, store, test_steps)
    assert store.finalized_checkpoint.epoch == 2

    # Another chain
    another_state = store.block_states[store.finalized_checkpoint.root].copy()
    # Build block that includes the skipped slots up to finality in chain
    block = build_empty_block(spec,
                              another_state,
                              spec.compute_start_slot_at_epoch(store.finalized_checkpoint.epoch) + 2)
    block.body.graffiti = b'\x12' * 32
    signed_block = state_transition_and_sign_block(spec, another_state, block)

    yield from tick_and_add_block(spec, store, signed_block, test_steps)

    yield 'steps', test_steps


@with_all_phases
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_on_block_finalized_skip_slots_not_in_skip_chain(spec, state):
    test_steps = []
    # Initialization
    transition_to(spec, state, state.slot + spec.SLOTS_PER_EPOCH - 1)
    block = build_empty_block_for_next_slot(spec, state)
    transition_unsigned_block(spec, state, block)
    block.state_root = state.hash_tree_root()
    store = spec.get_forkchoice_store(state, block)
    yield 'anchor_state', state
    yield 'anchor_block', block

    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    assert store.time == current_time

    pre_finalized_checkpoint_epoch = store.finalized_checkpoint.epoch

    # Finalized
    for _ in range(3):
        state, store, _ = yield from apply_next_epoch_with_attestations(spec, state, store, test_steps)
    assert store.finalized_checkpoint.epoch == pre_finalized_checkpoint_epoch + 1

    # Now build a block at later slot than finalized epoch
    # Includes finalized block in chain, but not at appropriate skip slot
    pre_state = store.block_states[block.hash_tree_root()].copy()
    block = build_empty_block(spec,
                              state=pre_state,
                              slot=spec.compute_start_slot_at_epoch(store.finalized_checkpoint.epoch) + 2)
    block.body.graffiti = b'\x12' * 32
    signed_block = sign_block(spec, pre_state, block)
    yield from tick_and_add_block(spec, store, signed_block, test_steps, valid=False)

    yield 'steps', test_steps
