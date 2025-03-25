from eth2spec.test.context import (
    spec_state_test,
    with_altair_and_later,
    with_presets,
)
from eth2spec.test.helpers.constants import (
    MINIMAL,
)
from eth2spec.test.helpers.attestations import (
    state_transition_with_full_block,
)
from eth2spec.test.helpers.block import (
    build_empty_block_for_next_slot,
)
from eth2spec.test.helpers.forks import is_post_eip7732
from eth2spec.test.helpers.fork_choice import (
    check_head_against_root,
    get_genesis_forkchoice_store_and_block,
    get_store_full_state,
    on_tick_and_append_step,
    payload_state_transition,
    payload_state_transition_no_store,
    tick_and_add_block,
    apply_next_epoch_with_attestations,
    find_next_justifying_slot,
)
from eth2spec.test.helpers.state import (
    state_transition_and_sign_block,
    next_epoch,
)


TESTING_PRESETS = [MINIMAL]


@with_altair_and_later
@spec_state_test
@with_presets(TESTING_PRESETS, reason="too slow")
def test_withholding_attack(spec, state):
    """ """
    test_steps = []
    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    assert store.time == current_time

    next_epoch(spec, state)
    on_tick_and_append_step(
        spec,
        store,
        store.genesis_time + state.slot * spec.config.SECONDS_PER_SLOT,
        test_steps,
    )

    # Fill epoch 1 to 3
    for _ in range(3):
        state, store, _ = yield from apply_next_epoch_with_attestations(
            spec, state, store, True, True, test_steps=test_steps
        )

    assert spec.compute_epoch_at_slot(spec.get_current_slot(store)) == 4
    assert state.current_justified_checkpoint.epoch == store.justified_checkpoint.epoch == 3

    # Create the attack block that includes justifying attestations for epoch 4
    # This block is withheld & revealed only in epoch 5
    signed_blocks, justifying_slot = find_next_justifying_slot(spec, state, True, False)
    assert spec.compute_epoch_at_slot(justifying_slot) == spec.get_current_epoch(state)
    assert len(signed_blocks) > 1
    signed_attack_block = signed_blocks[-1]
    for signed_block in signed_blocks[:-1]:
        current_root = signed_block.message.hash_tree_root()
        yield from tick_and_add_block(spec, store, signed_block, test_steps)
        payload_state_transition(spec, store, signed_block.message)
        check_head_against_root(spec, store, current_root)
    head_root = signed_blocks[-2].message.hash_tree_root()
    check_head_against_root(spec, store, head_root)
    assert spec.compute_epoch_at_slot(state.slot) == 4
    assert spec.compute_epoch_at_slot(spec.get_current_slot(store)) == 4
    assert state.current_justified_checkpoint.epoch == store.justified_checkpoint.epoch == 3
    state = get_store_full_state(spec, store, head_root).copy()

    # Create an honest chain in epoch 5 that includes the justifying attestations from the attack block
    next_epoch(spec, state)
    assert spec.compute_epoch_at_slot(state.slot) == 5
    assert state.current_justified_checkpoint.epoch == 3
    # Create two blocks in the honest chain with full attestations, and add to the store
    honest_state = state.copy()
    for _ in range(2):
        signed_block = state_transition_with_full_block(spec, honest_state, True, False)
        yield from tick_and_add_block(spec, store, signed_block, test_steps)
        honest_state = payload_state_transition(spec, store, signed_block.message).copy()
    # Create final block in the honest chain that includes the justifying attestations from the attack block
    honest_block = build_empty_block_for_next_slot(spec, honest_state)
    honest_block.body.attestations = signed_attack_block.message.body.attestations
    signed_honest_block = state_transition_and_sign_block(spec, honest_state, honest_block)
    # Add the honest block to the store
    yield from tick_and_add_block(spec, store, signed_honest_block, test_steps)
    payload_state_transition(spec, store, signed_honest_block.message)
    check_head_against_root(spec, store, signed_honest_block.message.hash_tree_root())
    assert spec.compute_epoch_at_slot(spec.get_current_slot(store)) == 5
    assert state.current_justified_checkpoint.epoch == store.justified_checkpoint.epoch == 3

    # Tick to the next slot so proposer boost is not a factor in choosing the head
    current_time = (honest_block.slot + 1) * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    check_head_against_root(spec, store, signed_honest_block.message.hash_tree_root())
    assert spec.compute_epoch_at_slot(spec.get_current_slot(store)) == 5
    assert state.current_justified_checkpoint.epoch == store.justified_checkpoint.epoch == 3

    # Upon revealing the withheld attack block, the honest block should still be the head
    yield from tick_and_add_block(spec, store, signed_attack_block, test_steps)
    check_head_against_root(spec, store, signed_honest_block.message.hash_tree_root())
    # As a side effect of the pull-up logic, the attack block is pulled up and store.justified_checkpoint is updated
    assert store.justified_checkpoint.epoch == 4

    # Even after going to the next epoch, the honest block should remain the head
    slot = spec.get_current_slot(store) + spec.SLOTS_PER_EPOCH - (state.slot % spec.SLOTS_PER_EPOCH)
    current_time = slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    assert spec.compute_epoch_at_slot(spec.get_current_slot(store)) == 6
    check_head_against_root(spec, store, signed_honest_block.message.hash_tree_root())

    yield "steps", test_steps


@with_altair_and_later
@spec_state_test
@with_presets(TESTING_PRESETS, reason="too slow")
def test_withholding_attack_unviable_honest_chain(spec, state):
    """
    Checks that the withholding attack succeeds for one epoch if the honest chain has a voting source beyond
    two epochs ago.
    """
    test_steps = []
    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    assert store.time == current_time

    next_epoch(spec, state)
    on_tick_and_append_step(
        spec,
        store,
        store.genesis_time + state.slot * spec.config.SECONDS_PER_SLOT,
        test_steps,
    )

    # Fill epoch 1 to 3
    for _ in range(3):
        state, store, _ = yield from apply_next_epoch_with_attestations(
            spec, state, store, True, True, test_steps=test_steps
        )

    assert spec.compute_epoch_at_slot(spec.get_current_slot(store)) == 4
    assert state.current_justified_checkpoint.epoch == store.justified_checkpoint.epoch == 3

    next_epoch(spec, state)
    assert spec.compute_epoch_at_slot(state.slot) == 5

    # Create the attack block that includes justifying attestations for epoch 5
    # This block is withheld & revealed only in epoch 6
    signed_blocks, justifying_slot = find_next_justifying_slot(spec, state, True, False)
    assert spec.compute_epoch_at_slot(justifying_slot) == spec.get_current_epoch(state)
    assert len(signed_blocks) > 1
    signed_attack_block = signed_blocks[-1]
    for signed_block in signed_blocks[:-1]:
        yield from tick_and_add_block(spec, store, signed_block, test_steps)
        check_head_against_root(spec, store, signed_block.message.hash_tree_root())
        payload_state_transition(spec, store, signed_block.message)
    state = get_store_full_state(spec, store, signed_block.message.hash_tree_root()).copy()
    assert spec.compute_epoch_at_slot(state.slot) == 5
    assert spec.compute_epoch_at_slot(spec.get_current_slot(store)) == 5
    assert state.current_justified_checkpoint.epoch == store.justified_checkpoint.epoch == 3

    # Create an honest chain in epoch 6 that includes the justifying attestations from the attack block
    next_epoch(spec, state)
    assert spec.compute_epoch_at_slot(state.slot) == 6
    assert state.current_justified_checkpoint.epoch == 3
    # Create two blocks in the honest chain with full attestations, and add to the store
    for _ in range(2):
        signed_block = state_transition_with_full_block(spec, state, True, False)
        payload_state_transition_no_store(spec, state, signed_block.message)
        assert state.current_justified_checkpoint.epoch == 3
        yield from tick_and_add_block(spec, store, signed_block, test_steps)
        check_head_against_root(spec, store, signed_block.message.hash_tree_root())
        payload_state_transition(spec, store, signed_block.message)
    # Create final block in the honest chain that includes the justifying attestations from the attack block
    honest_block = build_empty_block_for_next_slot(spec, state)
    honest_block.body.attestations = signed_attack_block.message.body.attestations
    signed_honest_block = state_transition_and_sign_block(spec, state, honest_block)
    honest_block_root = signed_honest_block.message.hash_tree_root()
    assert state.current_justified_checkpoint.epoch == 3
    # Add the honest block to the store
    yield from tick_and_add_block(spec, store, signed_honest_block, test_steps)
    payload_state_transition(spec, store, signed_honest_block.message)
    current_epoch = spec.compute_epoch_at_slot(spec.get_current_slot(store))
    assert current_epoch == 6
    # assert store.voting_source[honest_block_root].epoch == 3
    check_head_against_root(spec, store, honest_block_root)
    assert spec.compute_epoch_at_slot(spec.get_current_slot(store)) == 6
    assert state.current_justified_checkpoint.epoch == store.justified_checkpoint.epoch == 3

    # Tick to the next slot so proposer boost is not a factor in choosing the head
    current_time = (honest_block.slot + 1) * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    check_head_against_root(spec, store, honest_block_root)
    assert spec.compute_epoch_at_slot(spec.get_current_slot(store)) == 6
    assert state.current_justified_checkpoint.epoch == store.justified_checkpoint.epoch == 3

    # Upon revealing the withheld attack block, it should become the head
    # Except in EIP-7732 in which it's parent becomes head because of the
    # attestations during the attacker's block's committee.
    yield from tick_and_add_block(spec, store, signed_attack_block, test_steps)
    payload_state_transition(spec, store, signed_attack_block.message)
    # The attack block is pulled up and store.justified_checkpoint is updated
    assert store.justified_checkpoint.epoch == 5
    if is_post_eip7732(spec):
        attack_block_root = signed_attack_block.message.parent_root
    else:
        attack_block_root = signed_attack_block.message.hash_tree_root()
    check_head_against_root(spec, store, attack_block_root)

    # After going to the next epoch, the honest block should become the head
    slot = spec.get_current_slot(store) + spec.SLOTS_PER_EPOCH - (state.slot % spec.SLOTS_PER_EPOCH)
    current_time = slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    assert spec.compute_epoch_at_slot(spec.get_current_slot(store)) == 7
    # assert store.voting_source[honest_block_root].epoch == 5
    check_head_against_root(spec, store, honest_block_root)

    yield "steps", test_steps
