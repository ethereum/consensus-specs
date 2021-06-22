from copy import deepcopy
from eth2spec.utils.ssz.ssz_impl import hash_tree_root

from eth2spec.test.context import MINIMAL, with_all_phases, spec_state_test, with_presets
from eth2spec.test.helpers.attestations import (
    next_epoch_with_attestations,
    next_slots_with_attestations,
    state_transition_with_signed_full_block,
)
from eth2spec.test.helpers.block import (
    build_empty_block,
    build_empty_block_for_next_slot,
    sign_block,
    transition_unsigned_block,
)
from eth2spec.test.helpers.fork_choice import (
    get_genesis_forkchoice_store,
    run_on_block,
    apply_next_epoch_with_attestations,
)
from eth2spec.test.helpers.state import next_epoch, state_transition_and_sign_block, transition_to, next_slots


@with_all_phases
@spec_state_test
def test_on_block_before_finalized(spec, state):
    # Initialization
    store = get_genesis_forkchoice_store(spec, state)

    store.finalized_checkpoint = spec.Checkpoint(
        epoch=store.finalized_checkpoint.epoch + 2,
        root=store.finalized_checkpoint.root
    )

    # Fail receiving block of `GENESIS_SLOT + 1` slot
    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block)
    run_on_block(spec, store, signed_block, valid=False)


@with_all_phases
@spec_state_test
def test_on_block_finalized_skip_slots(spec, state):
    # Initialization
    store = get_genesis_forkchoice_store(spec, state)

    # Create a finalized chain
    store.finalized_checkpoint = spec.Checkpoint(
        epoch=store.finalized_checkpoint.epoch + 2,
        root=store.finalized_checkpoint.root
    )

    # Build block that includes the skipped slots up to finality in chain
    block = build_empty_block(spec, state, spec.compute_start_slot_at_epoch(store.finalized_checkpoint.epoch) + 2)
    signed_block = state_transition_and_sign_block(spec, state, block)
    spec.on_tick(store, store.genesis_time + state.slot * spec.config.SECONDS_PER_SLOT)
    run_on_block(spec, store, signed_block)


@with_all_phases
@spec_state_test
def test_on_block_finalized_skip_slots_not_in_skip_chain(spec, state):
    # Initialization
    transition_to(spec, state, state.slot + spec.SLOTS_PER_EPOCH - 1)
    block = build_empty_block_for_next_slot(spec, state)
    transition_unsigned_block(spec, state, block)
    block.state_root = state.hash_tree_root()
    store = spec.get_forkchoice_store(state, block)

    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    spec.on_tick(store, current_time)
    assert store.time == current_time

    pre_finalized_checkpoint_epoch = store.finalized_checkpoint.epoch

    # Finalized
    for _ in range(3):
        state, store, _ = yield from apply_next_epoch_with_attestations(spec, state, store)
    assert store.finalized_checkpoint.epoch == pre_finalized_checkpoint_epoch + 1

    # Now build a block at later slot than finalized epoch
    # Includes finalized block in chain, but not at appropriate skip slot
    pre_state = store.block_states[block.hash_tree_root()]
    block = build_empty_block(spec,
                              state=pre_state,
                              slot=spec.compute_start_slot_at_epoch(store.finalized_checkpoint.epoch) + 2)
    signed_block = sign_block(spec, pre_state, block)

    spec.on_tick(store, store.genesis_time + state.slot * spec.config.SECONDS_PER_SLOT)
    run_on_block(spec, store, signed_block, valid=False)


@with_all_phases
@spec_state_test
def test_on_block_update_justified_checkpoint_within_safe_slots(spec, state):
    # Initialization
    store = get_genesis_forkchoice_store(spec, state)

    next_epoch(spec, state)
    spec.on_tick(store, store.genesis_time + state.slot * spec.config.SECONDS_PER_SLOT)
    state, store, last_signed_block = yield from apply_next_epoch_with_attestations(spec, state, store)
    next_epoch(spec, state)
    spec.on_tick(store, store.genesis_time + state.slot * spec.config.SECONDS_PER_SLOT)
    last_block_root = last_signed_block.message.hash_tree_root()

    # NOTE: Mock the justified checkpoint
    just_state = store.block_states[last_block_root]
    new_justified = spec.Checkpoint(
        epoch=just_state.current_justified_checkpoint.epoch + 1,
        root=b'\x77' * 32,
    )
    just_state.current_justified_checkpoint = new_justified  # Mutate `store`

    assert store.block_states[last_block_root].hash_tree_root() == just_state.hash_tree_root()

    block = build_empty_block_for_next_slot(spec, just_state)

    # NOTE: Mock store so that the modified state could be accessed
    parent_block = last_signed_block.message.copy()
    parent_block.state_root = just_state.hash_tree_root()
    store.blocks[block.parent_root] = parent_block
    store.block_states[block.parent_root] = just_state.copy()
    assert block.parent_root in store.blocks.keys()
    assert block.parent_root in store.block_states.keys()

    signed_block = state_transition_and_sign_block(spec, just_state.copy(), block)
    assert spec.get_current_slot(store) % spec.SLOTS_PER_EPOCH < spec.SAFE_SLOTS_TO_UPDATE_JUSTIFIED
    run_on_block(spec, store, signed_block)

    assert store.justified_checkpoint == new_justified


@with_all_phases
@spec_state_test
def test_on_block_outside_safe_slots_and_multiple_better_justified(spec, state):
    # Initialization
    store = get_genesis_forkchoice_store(spec, state)

    next_epoch(spec, state)
    spec.on_tick(store, store.genesis_time + state.slot * spec.config.SECONDS_PER_SLOT)
    state, store, last_signed_block = yield from apply_next_epoch_with_attestations(spec, state, store)
    last_block_root = hash_tree_root(last_signed_block.message)

    # NOTE: Mock fictitious justified checkpoint in store
    store.justified_checkpoint = spec.Checkpoint(
        epoch=spec.compute_epoch_at_slot(last_signed_block.message.slot),
        root=spec.Root("0x4a55535449464945440000000000000000000000000000000000000000000000")
    )

    next_epoch(spec, state)
    spec.on_tick(store, store.genesis_time + state.slot * spec.config.SECONDS_PER_SLOT)

    # Create new higher justified checkpoint not in branch of store's justified checkpoint
    just_block = build_empty_block_for_next_slot(spec, state)
    store.blocks[just_block.hash_tree_root()] = just_block

    # Step time past safe slots
    spec.on_tick(store, store.time + spec.SAFE_SLOTS_TO_UPDATE_JUSTIFIED * spec.config.SECONDS_PER_SLOT)
    assert spec.get_current_slot(store) % spec.SLOTS_PER_EPOCH >= spec.SAFE_SLOTS_TO_UPDATE_JUSTIFIED

    previously_justified = store.justified_checkpoint

    # Add a series of new blocks with "better" justifications
    best_justified_checkpoint = spec.Checkpoint(epoch=0)
    for i in range(3, 0, -1):
        # Mutate store
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

        # NOTE: Mock store so that the modified state could be accessed
        parent_block = store.blocks[last_block_root].copy()
        parent_block.state_root = just_state.hash_tree_root()
        store.blocks[block.parent_root] = parent_block
        store.block_states[block.parent_root] = just_state.copy()
        assert block.parent_root in store.blocks.keys()
        assert block.parent_root in store.block_states.keys()

        run_on_block(spec, store, signed_block)

    assert store.justified_checkpoint == previously_justified
    # ensure the best from the series was stored
    assert store.best_justified_checkpoint == best_justified_checkpoint


@with_all_phases
@spec_state_test
def test_on_block_outside_safe_slots_but_finality(spec, state):
    # Initialization
    store = get_genesis_forkchoice_store(spec, state)

    next_epoch(spec, state)
    spec.on_tick(store, store.genesis_time + state.slot * spec.config.SECONDS_PER_SLOT)
    state, store, last_signed_block = yield from apply_next_epoch_with_attestations(spec, state, store)
    last_block_root = hash_tree_root(last_signed_block.message)

    # NOTE: Mock fictitious justified checkpoint in store
    store.justified_checkpoint = spec.Checkpoint(
        epoch=spec.compute_epoch_at_slot(last_signed_block.message.slot),
        root=spec.Root("0x4a55535449464945440000000000000000000000000000000000000000000000")
    )

    next_epoch(spec, state)
    spec.on_tick(store, store.genesis_time + state.slot * spec.config.SECONDS_PER_SLOT)

    # NOTE: Mock a new higher justified checkpoint not in branch of store's justified checkpoint
    just_block = build_empty_block_for_next_slot(spec, state)
    store.blocks[just_block.hash_tree_root()] = just_block

    # Step time past safe slots
    spec.on_tick(store, store.time + spec.SAFE_SLOTS_TO_UPDATE_JUSTIFIED * spec.config.SECONDS_PER_SLOT)
    assert spec.get_current_slot(store) % spec.SLOTS_PER_EPOCH >= spec.SAFE_SLOTS_TO_UPDATE_JUSTIFIED

    # NOTE: Mock justified and finalized update in state
    just_fin_state = store.block_states[last_block_root]
    new_justified = spec.Checkpoint(
        epoch=spec.compute_epoch_at_slot(just_block.slot) + 1,
        root=just_block.hash_tree_root(),
    )
    assert new_justified.epoch > store.justified_checkpoint.epoch
    new_finalized = spec.Checkpoint(
        epoch=spec.compute_epoch_at_slot(just_block.slot),
        root=just_block.parent_root,
    )
    assert new_finalized.epoch > store.finalized_checkpoint.epoch
    just_fin_state.current_justified_checkpoint = new_justified
    just_fin_state.finalized_checkpoint = new_finalized

    # Build and add block that includes the new justified/finalized info
    block = build_empty_block_for_next_slot(spec, just_fin_state)
    signed_block = state_transition_and_sign_block(spec, deepcopy(just_fin_state), block)

    # NOTE: Mock store so that the modified state could be accessed
    parent_block = last_signed_block.message.copy()
    parent_block.state_root = just_fin_state.hash_tree_root()
    store.blocks[block.parent_root] = parent_block
    store.block_states[block.parent_root] = just_fin_state.copy()
    assert block.parent_root in store.blocks.keys()
    assert block.parent_root in store.block_states.keys()

    run_on_block(spec, store, signed_block)

    assert store.finalized_checkpoint == new_finalized
    assert store.justified_checkpoint == new_justified


@with_all_phases
@with_presets([MINIMAL], reason="It assumes that `MAX_ATTESTATIONS` >= 2/3 attestations of an epoch")
@spec_state_test
def test_new_justified_is_later_than_store_justified(spec, state):
    """
    J: Justified
    F: Finalized
    fork_1_state (forked from genesis):
        epoch
        [0] <- [1] <- [2] <- [3] <- [4]
         F                    J

    fork_2_state (forked from fork_1_state's epoch 2):
        epoch
                       └──── [3] <- [4] <- [5] <- [6]
         F                           J

    fork_3_state (forked from genesis):
        [0] <- [1] <- [2] <- [3] <- [4] <- [5]
                              F      J
    """
    # The 1st fork, from genesis
    fork_1_state = state.copy()
    # The 3rd fork, from genesis
    fork_3_state = state.copy()

    # Initialization
    store = get_genesis_forkchoice_store(spec, fork_1_state)

    # ----- Process fork_1_state
    # Skip epoch 0
    next_epoch(spec, fork_1_state)
    # Fill epoch 1 with previous epoch attestations
    _, signed_blocks, fork_1_state = next_epoch_with_attestations(spec, fork_1_state, False, True)
    for block in signed_blocks:
        spec.on_tick(store, store.genesis_time + fork_1_state.slot * spec.config.SECONDS_PER_SLOT)
        run_on_block(spec, store, block)

    # Fork `fork_2_state` at the start of epoch 2
    fork_2_state = fork_1_state.copy()
    assert spec.get_current_epoch(fork_2_state) == 2

    # Skip epoch 2
    next_epoch(spec, fork_1_state)
    # # Fill epoch 3 & 4 with previous epoch attestations
    for _ in range(2):
        _, signed_blocks, fork_1_state = next_epoch_with_attestations(spec, fork_1_state, False, True)
        for block in signed_blocks:
            spec.on_tick(store, store.genesis_time + fork_1_state.slot * spec.config.SECONDS_PER_SLOT)
            run_on_block(spec, store, block)

    assert fork_1_state.finalized_checkpoint.epoch == store.finalized_checkpoint.epoch == 0
    assert fork_1_state.current_justified_checkpoint.epoch == store.justified_checkpoint.epoch == 3
    assert store.justified_checkpoint.hash_tree_root() == fork_1_state.current_justified_checkpoint.hash_tree_root()

    # ------ fork_2_state: Create a chain to set store.best_justified_checkpoint
    # NOTE: The goal is to make `store.best_justified_checkpoint.epoch > store.justified_checkpoint.epoch`
    all_blocks = []

    # Proposed an empty block at epoch 2, 1st slot
    block = build_empty_block_for_next_slot(spec, fork_2_state)
    signed_block = state_transition_and_sign_block(spec, fork_2_state, block)
    all_blocks.append(signed_block.copy())
    assert fork_2_state.current_justified_checkpoint.epoch == 0

    # Skip to epoch 4
    for _ in range(2):
        next_epoch(spec, fork_2_state)
        assert fork_2_state.current_justified_checkpoint.epoch == 0

    # Propose a block at epoch 4, 5th slot
    # Propose a block at epoch 5, 5th slot
    for _ in range(2):
        next_epoch(spec, fork_2_state)
        next_slots(spec, fork_2_state, 4)
        signed_block = state_transition_with_signed_full_block(spec, fork_2_state, True, True)
        all_blocks.append(signed_block.copy())
        assert fork_2_state.current_justified_checkpoint.epoch == 0

    # Propose a block at epoch 6, SAFE_SLOTS_TO_UPDATE_JUSTIFIED + 2 slot
    next_epoch(spec, fork_2_state)
    next_slots(spec, fork_2_state, spec.SAFE_SLOTS_TO_UPDATE_JUSTIFIED + 2)
    signed_block = state_transition_with_signed_full_block(spec, fork_2_state, True, True)
    all_blocks.append(signed_block.copy())
    assert fork_2_state.finalized_checkpoint.epoch == 0
    assert fork_2_state.current_justified_checkpoint.epoch == 5

    # Check SAFE_SLOTS_TO_UPDATE_JUSTIFIED
    spec.on_tick(store, store.genesis_time + fork_2_state.slot * spec.config.SECONDS_PER_SLOT)
    assert spec.compute_slots_since_epoch_start(spec.get_current_slot(store)) >= spec.SAFE_SLOTS_TO_UPDATE_JUSTIFIED

    # Apply blocks of `fork_3_state` to `store`
    for block in all_blocks:
        if store.time < spec.compute_time_at_slot(fork_2_state, block.message.slot):
            spec.on_tick(store, store.genesis_time + block.message.slot * spec.config.SECONDS_PER_SLOT)
        run_on_block(spec, store, block)

    assert store.finalized_checkpoint.epoch == 0
    assert store.justified_checkpoint.epoch == 3
    assert store.best_justified_checkpoint.epoch == 5

    # ------ fork_3_state: Create another chain to test the
    # "Update justified if new justified is later than store justified" case
    all_blocks = []
    for _ in range(3):
        next_epoch(spec, fork_3_state)

    # epoch 3
    _, signed_blocks, fork_3_state = next_epoch_with_attestations(spec, fork_3_state, True, True)
    all_blocks += signed_blocks
    assert fork_3_state.finalized_checkpoint.epoch == 0

    # epoch 4, attest the first 5 blocks
    _, blocks, fork_3_state = next_slots_with_attestations(spec, fork_3_state, 5, True, True)
    all_blocks += blocks.copy()
    assert fork_3_state.finalized_checkpoint.epoch == 0

    # Propose a block at epoch 5, 5th slot
    next_epoch(spec, fork_3_state)
    next_slots(spec, fork_3_state, 4)
    signed_block = state_transition_with_signed_full_block(spec, fork_3_state, True, True)
    all_blocks.append(signed_block.copy())
    assert fork_3_state.finalized_checkpoint.epoch == 0

    # Propose a block at epoch 6, 5th slot
    next_epoch(spec, fork_3_state)
    next_slots(spec, fork_3_state, 4)
    signed_block = state_transition_with_signed_full_block(spec, fork_3_state, True, True)
    all_blocks.append(signed_block.copy())
    assert fork_3_state.finalized_checkpoint.epoch == 3
    assert fork_3_state.current_justified_checkpoint.epoch == 4

    # Apply blocks of `fork_3_state` to `store`
    for block in all_blocks:
        if store.time < spec.compute_time_at_slot(fork_2_state, block.message.slot):
            spec.on_tick(store, store.genesis_time + block.message.slot * spec.config.SECONDS_PER_SLOT)
        run_on_block(spec, store, block)

    assert store.finalized_checkpoint.hash_tree_root() == fork_3_state.finalized_checkpoint.hash_tree_root()
    assert (store.justified_checkpoint.hash_tree_root()
            == fork_3_state.current_justified_checkpoint.hash_tree_root()
            != store.best_justified_checkpoint.hash_tree_root())
    assert (store.best_justified_checkpoint.hash_tree_root()
            == fork_2_state.current_justified_checkpoint.hash_tree_root())


@with_all_phases
@spec_state_test
def test_new_finalized_slot_is_not_justified_checkpoint_ancestor(spec, state):
    """
    J: Justified
    F: Finalized
    state (forked from genesis):
        epoch
        [0] <- [1] <- [2] <- [3] <- [4] <- [5]
         F                    J

    another_state (forked from epoch 0):
         └──── [1] <- [2] <- [3] <- [4] <- [5]
                       F      J
    """
    # Initialization
    store = get_genesis_forkchoice_store(spec, state)

    # ----- Process state
    # Goal: make `store.finalized_checkpoint.epoch == 0` and `store.justified_checkpoint.epoch == 3`
    # Skip epoch 0
    next_epoch(spec, state)

    # Forking another_state
    another_state = state.copy()

    # Fill epoch 1 with previous epoch attestations
    _, signed_blocks, state = next_epoch_with_attestations(spec, state, False, True)
    for block in signed_blocks:
        spec.on_tick(store, store.genesis_time + state.slot * spec.config.SECONDS_PER_SLOT)
        run_on_block(spec, store, block)
    # Skip epoch 2
    next_epoch(spec, state)
    # Fill epoch 3 & 4 with previous epoch attestations
    for _ in range(2):
        _, signed_blocks, state = next_epoch_with_attestations(spec, state, False, True)
        for block in signed_blocks:
            spec.on_tick(store, store.genesis_time + state.slot * spec.config.SECONDS_PER_SLOT)
            run_on_block(spec, store, block)

    assert state.finalized_checkpoint.epoch == store.finalized_checkpoint.epoch == 0
    assert state.current_justified_checkpoint.epoch == store.justified_checkpoint.epoch == 3
    assert store.justified_checkpoint.hash_tree_root() == state.current_justified_checkpoint.hash_tree_root()

    # Create another chain
    # Goal: make `another_state.finalized_checkpoint.epoch == 2` and `another_state.justified_checkpoint.epoch == 3`
    all_blocks = []
    # Fill epoch 1 & 2 with previous + current epoch attestations
    for _ in range(3):
        _, signed_blocks, another_state = next_epoch_with_attestations(spec, another_state, True, True)
        all_blocks += signed_blocks

    assert another_state.finalized_checkpoint.epoch == 2
    assert another_state.current_justified_checkpoint.epoch == 3
    assert state.finalized_checkpoint.hash_tree_root() != another_state.finalized_checkpoint.hash_tree_root()
    assert (
        state.current_justified_checkpoint.hash_tree_root()
        != another_state.current_justified_checkpoint.hash_tree_root()
    )
    pre_store_justified_checkpoint_root = store.justified_checkpoint.root

    # Apply blocks of `another_state` to `store`
    for block in all_blocks:
        # NOTE: Do not call `on_tick` here
        run_on_block(spec, store, block)

    finalized_slot = spec.compute_start_slot_at_epoch(store.finalized_checkpoint.epoch)
    ancestor_at_finalized_slot = spec.get_ancestor(store, pre_store_justified_checkpoint_root, finalized_slot)
    assert ancestor_at_finalized_slot != store.finalized_checkpoint.root

    assert store.finalized_checkpoint.hash_tree_root() == another_state.finalized_checkpoint.hash_tree_root()
    assert store.justified_checkpoint.hash_tree_root() == another_state.current_justified_checkpoint.hash_tree_root()


@with_all_phases
@spec_state_test
def test_new_finalized_slot_is_justified_checkpoint_ancestor(spec, state):
    """
    J: Justified
    F: Finalized
    state:
        epoch
        [0] <- [1] <- [2] <- [3] <- [4] <- [5]
                       F             J

    another_state (forked from state at epoch 3):
                              └──── [4] <- [5]
                              F      J
    """
    # Initialization
    store = get_genesis_forkchoice_store(spec, state)

    # Process state
    next_epoch(spec, state)
    spec.on_tick(store, store.genesis_time + state.slot * spec.config.SECONDS_PER_SLOT)
    _, signed_blocks, state = next_epoch_with_attestations(spec, state, False, True)
    for block in signed_blocks:
        spec.on_tick(store, store.genesis_time + state.slot * spec.config.SECONDS_PER_SLOT)
        run_on_block(spec, store, block)
    _, signed_blocks, state = next_epoch_with_attestations(spec, state, True, False)
    for block in signed_blocks:
        spec.on_tick(store, store.genesis_time + state.slot * spec.config.SECONDS_PER_SLOT)
        run_on_block(spec, store, block)
    next_epoch(spec, state)
    spec.on_tick(store, store.genesis_time + state.slot * spec.config.SECONDS_PER_SLOT)
    for _ in range(2):
        _, signed_blocks, state = next_epoch_with_attestations(spec, state, False, True)
        for block in signed_blocks:
            spec.on_tick(store, store.genesis_time + state.slot * spec.config.SECONDS_PER_SLOT)
            run_on_block(spec, store, block)

    assert state.finalized_checkpoint.epoch == store.finalized_checkpoint.epoch == 2
    assert state.current_justified_checkpoint.epoch == store.justified_checkpoint.epoch == 4
    assert store.justified_checkpoint.hash_tree_root() == state.current_justified_checkpoint.hash_tree_root()

    # Create another chain
    # Forking from epoch 3
    all_blocks = []
    slot = spec.compute_start_slot_at_epoch(3)
    block_root = spec.get_block_root_at_slot(state, slot)
    another_state = store.block_states[block_root].copy()
    for _ in range(2):
        _, signed_blocks, another_state = next_epoch_with_attestations(spec, another_state, True, True)
        all_blocks += signed_blocks

    assert another_state.finalized_checkpoint.epoch == 3
    assert another_state.current_justified_checkpoint.epoch == 4

    pre_store_justified_checkpoint_root = store.justified_checkpoint.root
    for block in all_blocks:
        if store.time < spec.compute_time_at_slot(another_state, block.message.slot):
            spec.on_tick(store, store.genesis_time + block.message.slot * spec.config.SECONDS_PER_SLOT)
        run_on_block(spec, store, block)

    finalized_slot = spec.compute_start_slot_at_epoch(store.finalized_checkpoint.epoch)
    ancestor_at_finalized_slot = spec.get_ancestor(store, pre_store_justified_checkpoint_root, finalized_slot)
    assert ancestor_at_finalized_slot == store.finalized_checkpoint.root

    assert store.finalized_checkpoint.hash_tree_root() == another_state.finalized_checkpoint.hash_tree_root()
    assert store.justified_checkpoint.hash_tree_root() != another_state.current_justified_checkpoint.hash_tree_root()
