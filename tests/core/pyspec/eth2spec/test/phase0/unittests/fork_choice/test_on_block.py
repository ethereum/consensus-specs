from copy import deepcopy

from eth2spec.utils.ssz.ssz_impl import hash_tree_root
from eth2spec.test.context import (
    spec_state_test,
    with_all_phases,
)
from eth2spec.test.helpers.block import (
    build_empty_block_for_next_slot,
)
from eth2spec.test.helpers.fork_choice import (
    get_genesis_forkchoice_store,
    run_on_block,
    apply_next_epoch_with_attestations,
)
from eth2spec.test.helpers.state import (
    next_epoch,
    state_transition_and_sign_block,
)


@with_all_phases
@spec_state_test
def test_on_block_outside_safe_slots_and_multiple_better_justified(spec, state):
    """
    NOTE: test_new_justified_is_later_than_store_justified also tests best_justified_checkpoint
    """
    # Initialization
    store = get_genesis_forkchoice_store(spec, state)

    next_epoch(spec, state)
    spec.on_tick(store, store.genesis_time + state.slot * spec.config.SECONDS_PER_SLOT)
    state, store, last_signed_block = yield from apply_next_epoch_with_attestations(
        spec, state, store, True, False)
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

    previously_finalized = store.finalized_checkpoint
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

    assert store.finalized_checkpoint == previously_finalized
    assert store.justified_checkpoint == previously_justified
    # ensure the best from the series was stored
    assert store.best_justified_checkpoint == best_justified_checkpoint
