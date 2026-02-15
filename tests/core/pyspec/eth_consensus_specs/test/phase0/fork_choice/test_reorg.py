from eth_consensus_specs.test.context import (
    spec_state_test,
    with_altair_and_later,
    with_presets,
)
from eth_consensus_specs.test.helpers.attestations import (
    get_valid_attestation,
    get_valid_attestations_at_slot,
    state_transition_with_full_block,
)
from eth_consensus_specs.test.helpers.block import (
    build_empty_block,
    build_empty_block_for_next_slot,
)
from eth_consensus_specs.test.helpers.constants import (
    MINIMAL,
)
from eth_consensus_specs.test.helpers.fork_choice import (
    add_attestations,
    apply_next_epoch_with_attestations,
    check_head_against_root,
    find_next_justifying_slot,
    get_genesis_forkchoice_store_and_block,
    is_ready_to_justify,
    on_tick_and_append_step,
    tick_and_add_block,
)
from eth_consensus_specs.test.helpers.forks import is_post_gloas
from eth_consensus_specs.test.helpers.state import (
    next_epoch,
    next_slot,
    state_transition_and_sign_block,
    transition_to,
)

TESTING_PRESETS = [MINIMAL]


@with_altair_and_later
@spec_state_test
@with_presets(TESTING_PRESETS, reason="too slow")
def test_simple_attempted_reorg_without_enough_ffg_votes(spec, state):
    """
    [Case 1]

    {      epoch 4             }{     epoch 5     }
    [c4]<--[a]<--[-]<--[y]
            ↑____[-]<--[z]

    At c4, c3 is the latest justified checkpoint (or something earlier)

    The block y doesn't have enough votes to justify c4.
    The block z also doesn't have enough votes to justify c4.
    """
    test_steps = []
    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block
    current_time = state.slot * spec.config.SLOT_DURATION_MS // 1000 + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    assert store.time == current_time

    next_epoch(spec, state)
    on_tick_and_append_step(
        spec,
        store,
        store.genesis_time + state.slot * spec.config.SLOT_DURATION_MS // 1000,
        test_steps,
    )

    # Fill epoch 1 to 3
    for _ in range(3):
        state, store, _ = yield from apply_next_epoch_with_attestations(
            spec, state, store, True, True, test_steps=test_steps
        )

    assert state.current_justified_checkpoint.epoch == store.justified_checkpoint.epoch == 3

    # create block_a, it needs 2 more full blocks to justify epoch 4
    signed_blocks, justifying_slot = find_next_justifying_slot(spec, state, True, True)
    assert spec.compute_epoch_at_slot(justifying_slot) == spec.get_current_epoch(state)
    for signed_block in signed_blocks[:-2]:
        yield from tick_and_add_block(spec, store, signed_block, test_steps)
        check_head_against_root(spec, store, signed_block.message.hash_tree_root())

    if is_post_gloas(spec):
        head_root = spec.get_head(store).root
    else:
        head_root = spec.get_head(store)
    state = store.block_states[head_root].copy()

    assert state.current_justified_checkpoint.epoch == 3
    next_slot(spec, state)
    state_a = state.copy()

    # to test the "no withholding" situation, temporarily store the blocks in lists
    signed_blocks_of_y = []
    signed_blocks_of_z = []

    # add an empty block on chain y
    block_y = build_empty_block_for_next_slot(spec, state)
    signed_block_y = state_transition_and_sign_block(spec, state, block_y)
    signed_blocks_of_y.append(signed_block_y)

    # chain y has some on-chain attestations, but not enough to justify c4
    signed_block_y = state_transition_with_full_block(spec, state, True, True)
    assert not is_ready_to_justify(spec, state)
    signed_blocks_of_y.append(signed_block_y)
    assert store.justified_checkpoint.epoch == 3

    state = state_a.copy()
    signed_block_z = None
    # add one block on chain z, which is not enough to justify c4
    attestation = get_valid_attestation(spec, state, slot=state.slot, signed=True)
    block_z = build_empty_block_for_next_slot(spec, state)
    block_z.body.attestations = [attestation]
    signed_block_z = state_transition_and_sign_block(spec, state, block_z)
    signed_blocks_of_z.append(signed_block_z)

    # add an empty block on chain z
    block_z = build_empty_block_for_next_slot(spec, state)
    signed_block_z = state_transition_and_sign_block(spec, state, block_z)
    signed_blocks_of_z.append(signed_block_z)

    # ensure z couldn't justify c4
    assert not is_ready_to_justify(spec, state)

    # apply blocks to store
    # (i) slot block_a.slot + 1
    signed_block_y = signed_blocks_of_y.pop(0)
    yield from tick_and_add_block(spec, store, signed_block_y, test_steps)
    # apply block of chain `z`
    signed_block_z = signed_blocks_of_z.pop(0)
    yield from tick_and_add_block(spec, store, signed_block_z, test_steps)

    # (ii) slot block_a.slot + 2
    # apply block of chain `z`
    signed_block_z = signed_blocks_of_z.pop(0)
    yield from tick_and_add_block(spec, store, signed_block_z, test_steps)
    # apply block of chain `y`
    signed_block_y = signed_blocks_of_y.pop(0)
    yield from tick_and_add_block(spec, store, signed_block_y, test_steps)
    # chain `y` remains the winner since it arrives earlier than `z`
    check_head_against_root(spec, store, signed_block_y.message.hash_tree_root())
    assert len(signed_blocks_of_y) == len(signed_blocks_of_z) == 0
    assert state.current_justified_checkpoint.epoch == store.justified_checkpoint.epoch == 3
    assert spec.compute_epoch_at_slot(spec.get_current_slot(store)) == 4

    # tick to the prior of the epoch boundary
    slot = state.slot + spec.SLOTS_PER_EPOCH - (state.slot % spec.SLOTS_PER_EPOCH) - 1
    current_time = slot * spec.config.SLOT_DURATION_MS // 1000 + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    assert state.current_justified_checkpoint.epoch == store.justified_checkpoint.epoch == 3
    assert spec.compute_epoch_at_slot(spec.get_current_slot(store)) == 4
    # chain `y` reminds the winner
    check_head_against_root(spec, store, signed_block_y.message.hash_tree_root())

    # to next block
    next_epoch(spec, state)
    current_time = state.slot * spec.config.SLOT_DURATION_MS // 1000 + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    assert spec.compute_epoch_at_slot(spec.get_current_slot(store)) == 5
    check_head_against_root(spec, store, signed_block_y.message.hash_tree_root())
    assert state.current_justified_checkpoint.epoch == store.justified_checkpoint.epoch == 3

    yield "steps", test_steps


def _run_delayed_justification(spec, state, attempted_reorg, is_justifying_previous_epoch):
    """ """
    test_steps = []
    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block
    current_time = state.slot * spec.config.SLOT_DURATION_MS // 1000 + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    assert store.time == current_time

    next_epoch(spec, state)
    on_tick_and_append_step(
        spec,
        store,
        store.genesis_time + state.slot * spec.config.SLOT_DURATION_MS // 1000,
        test_steps,
    )

    # Fill epoch 1 to 2
    for _ in range(2):
        state, store, _ = yield from apply_next_epoch_with_attestations(
            spec, state, store, True, True, test_steps=test_steps
        )

    if is_justifying_previous_epoch:
        state, store, _ = yield from apply_next_epoch_with_attestations(
            spec, state, store, False, False, test_steps=test_steps
        )
        assert state.current_justified_checkpoint.epoch == store.justified_checkpoint.epoch == 2
    else:
        state, store, _ = yield from apply_next_epoch_with_attestations(
            spec, state, store, True, True, test_steps=test_steps
        )
        assert state.current_justified_checkpoint.epoch == store.justified_checkpoint.epoch == 3

    if is_justifying_previous_epoch:
        # try to find the block that can justify epoch 3
        signed_blocks, justifying_slot = find_next_justifying_slot(spec, state, False, True)
    else:
        # try to find the block that can justify epoch 4
        signed_blocks, justifying_slot = find_next_justifying_slot(spec, state, True, True)

    assert spec.compute_epoch_at_slot(justifying_slot) == spec.get_current_epoch(state)
    for signed_block in signed_blocks:
        yield from tick_and_add_block(spec, store, signed_block, test_steps)
    if is_post_gloas(spec):
        head_root = spec.get_head(store).root
    else:
        head_root = spec.get_head(store)
    state = store.block_states[head_root].copy()
    if is_justifying_previous_epoch:
        assert state.current_justified_checkpoint.epoch == 2
    else:
        assert state.current_justified_checkpoint.epoch == 3

    assert is_ready_to_justify(spec, state)
    state_b = state.copy()

    # add chain y
    if is_justifying_previous_epoch:
        signed_block_y = state_transition_with_full_block(spec, state, False, True)
    else:
        signed_block_y = state_transition_with_full_block(spec, state, True, True)
    yield from tick_and_add_block(spec, store, signed_block_y, test_steps)
    check_head_against_root(spec, store, signed_block_y.message.hash_tree_root())
    if is_justifying_previous_epoch:
        assert store.justified_checkpoint.epoch == 2
    else:
        assert store.justified_checkpoint.epoch == 3

    # add attestations of y
    temp_state = state.copy()
    next_slot(spec, temp_state)
    attestations_for_y = list(
        get_valid_attestations_at_slot(temp_state, spec, signed_block_y.message.slot)
    )
    current_time = temp_state.slot * spec.config.SLOT_DURATION_MS // 1000 + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    yield from add_attestations(spec, store, attestations_for_y, test_steps)
    check_head_against_root(spec, store, signed_block_y.message.hash_tree_root())

    if attempted_reorg:
        # add chain z
        state = state_b.copy()
        slot = state.slot + spec.SLOTS_PER_EPOCH - (state.slot % spec.SLOTS_PER_EPOCH) - 1
        transition_to(spec, state, slot)
        block_z = build_empty_block_for_next_slot(spec, state)
        assert spec.compute_epoch_at_slot(block_z.slot) == 5
        signed_block_z = state_transition_and_sign_block(spec, state, block_z)
        yield from tick_and_add_block(spec, store, signed_block_z, test_steps)
    else:
        # next epoch
        state = state_b.copy()
        next_epoch(spec, state)
        current_time = state.slot * spec.config.SLOT_DURATION_MS // 1000 + store.genesis_time
        on_tick_and_append_step(spec, store, current_time, test_steps)

    # no reorg
    check_head_against_root(spec, store, signed_block_y.message.hash_tree_root())
    if is_justifying_previous_epoch:
        assert state.current_justified_checkpoint.epoch == store.justified_checkpoint.epoch == 3
    else:
        assert state.current_justified_checkpoint.epoch == store.justified_checkpoint.epoch == 4

    yield "steps", test_steps


@with_altair_and_later
@spec_state_test
@with_presets(TESTING_PRESETS, reason="too slow")
def test_simple_attempted_reorg_delayed_justification_current_epoch(spec, state):
    """
    [Case 2]

    {      epoch 4     }{     epoch 5     }
    [c4]<--[b]<--[y]
             ↑______________[z]
    At c4, c3 is the latest justified checkpoint (or something earlier)

    block_b: the block that can justify c4.
    z: the child of block of x at the first slot of epoch 5.
    block z can reorg the chain from block y.
    """
    yield from _run_delayed_justification(
        spec, state, attempted_reorg=True, is_justifying_previous_epoch=False
    )


def _run_include_votes_of_another_empty_chain(
    spec, state, enough_ffg, is_justifying_previous_epoch
):
    test_steps = []
    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block
    current_time = state.slot * spec.config.SLOT_DURATION_MS // 1000 + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    assert store.time == current_time

    next_epoch(spec, state)
    on_tick_and_append_step(
        spec,
        store,
        store.genesis_time + state.slot * spec.config.SLOT_DURATION_MS // 1000,
        test_steps,
    )

    # Fill epoch 1 to 2
    for _ in range(2):
        state, store, _ = yield from apply_next_epoch_with_attestations(
            spec, state, store, True, True, test_steps=test_steps
        )

    if is_justifying_previous_epoch:
        # build chain with head in epoch 3 and justified checkpoint in epoch 2
        block_a = build_empty_block_for_next_slot(spec, state)
        signed_block_a = state_transition_and_sign_block(spec, state, block_a)
        yield from tick_and_add_block(spec, store, signed_block_a, test_steps)
        assert spec.compute_epoch_at_slot(spec.get_current_slot(store)) == 3
        assert state.current_justified_checkpoint.epoch == store.justified_checkpoint.epoch == 2
    else:
        # build chain with head in epoch 4 and justified checkpoint in epoch 3
        state, store, _ = yield from apply_next_epoch_with_attestations(
            spec, state, store, True, True, test_steps=test_steps
        )
        signed_block_a = state_transition_with_full_block(spec, state, True, True)
        yield from tick_and_add_block(spec, store, signed_block_a, test_steps)
        assert spec.compute_epoch_at_slot(spec.get_current_slot(store)) == 4
        assert state.current_justified_checkpoint.epoch == store.justified_checkpoint.epoch == 3
    root_a = signed_block_a.message.hash_tree_root()
    check_head_against_root(spec, store, root_a)
    state = store.block_states[root_a].copy()
    state_a = state.copy()

    if is_justifying_previous_epoch:
        assert spec.compute_epoch_at_slot(spec.get_current_slot(store)) == 3
        assert spec.compute_epoch_at_slot(state.slot) == 3
        assert state.current_justified_checkpoint.epoch == 2
    else:
        assert spec.compute_epoch_at_slot(spec.get_current_slot(store)) == 4
        assert spec.compute_epoch_at_slot(state.slot) == 4
        assert state.current_justified_checkpoint.epoch == 3

    if is_justifying_previous_epoch:
        # try to find the block that can justify epoch 3 by including only previous epoch attestations
        _, justifying_slot = find_next_justifying_slot(spec, state, False, True)
        assert spec.compute_epoch_at_slot(justifying_slot) == 4
    else:
        # try to find the block that can justify epoch 4 by including current epoch attestations
        _, justifying_slot = find_next_justifying_slot(spec, state, True, True)
        assert spec.compute_epoch_at_slot(justifying_slot) == 4

    last_slot_of_z = justifying_slot if enough_ffg else justifying_slot - 1
    last_slot_of_y = justifying_slot if is_justifying_previous_epoch else last_slot_of_z - 1

    # to test the "no withholding" situation, temporarily store the blocks in lists
    signed_blocks_of_y = []

    # build an empty chain to the slot prior epoch boundary
    states_of_empty_chain = []
    for slot in range(state.slot + 1, last_slot_of_y + 1):
        block = build_empty_block(spec, state, slot=slot)
        signed_block = state_transition_and_sign_block(spec, state, block)
        states_of_empty_chain.append(state.copy())
        signed_blocks_of_y.append(signed_block)
    signed_block_y = signed_blocks_of_y[-1]
    assert spec.compute_epoch_at_slot(signed_block_y.message.slot) == 4

    # create 2/3 votes for the empty chain
    attestations_for_y = []
    # target_is_current = not is_justifying_previous_epoch
    attestations = list(get_valid_attestations_at_slot(state, spec, state_a.slot))
    attestations_for_y.append(attestations)
    for state in states_of_empty_chain:
        attestations = list(get_valid_attestations_at_slot(state, spec, state.slot))
        attestations_for_y.append(attestations)

    state = state_a.copy()
    signed_block_z = None
    for slot in range(state_a.slot + 1, last_slot_of_z + 1):
        # apply chain y, the empty chain
        if slot <= last_slot_of_y and len(signed_blocks_of_y) > 0:
            signed_block_y = signed_blocks_of_y.pop(0)
            assert signed_block_y.message.slot == slot
            yield from tick_and_add_block(spec, store, signed_block_y, test_steps)

        # apply chain z, a fork chain that includes these attestations_for_y
        block = build_empty_block(spec, state, slot=slot)
        if len(attestations_for_y) > 0 and (
            (not is_justifying_previous_epoch)
            or (is_justifying_previous_epoch and attestations_for_y[0][0].data.slot == slot - 5)
        ):
            block.body.attestations = attestations_for_y.pop(0)
        signed_block_z = state_transition_and_sign_block(spec, state, block)
        if signed_block_y != signed_block_z:
            yield from tick_and_add_block(spec, store, signed_block_z, test_steps)
        if is_ready_to_justify(spec, state):
            break

    assert spec.compute_epoch_at_slot(spec.get_current_slot(store)) == 4
    assert spec.compute_epoch_at_slot(signed_block_y.message.slot) == 4
    assert spec.compute_epoch_at_slot(signed_block_z.message.slot) == 4

    # y is not filtered out & wins the LMD competition, so y should be the head
    y_voting_source_epoch = spec.get_voting_source(
        store, signed_block_y.message.hash_tree_root()
    ).epoch
    if is_justifying_previous_epoch:
        assert state.current_justified_checkpoint.epoch == store.justified_checkpoint.epoch == 2
        assert y_voting_source_epoch == 2
        assert y_voting_source_epoch == store.justified_checkpoint.epoch
    else:
        assert state.current_justified_checkpoint.epoch == store.justified_checkpoint.epoch == 3
        assert y_voting_source_epoch == 3
        assert y_voting_source_epoch == store.justified_checkpoint.epoch
    check_head_against_root(spec, store, signed_block_y.message.hash_tree_root())

    if enough_ffg:
        assert is_ready_to_justify(spec, state)
    else:
        assert not is_ready_to_justify(spec, state)

    # to next epoch
    next_epoch(spec, state)
    current_time = state.slot * spec.config.SLOT_DURATION_MS // 1000 + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    assert spec.compute_epoch_at_slot(spec.get_current_slot(store)) == 5

    y_voting_source_epoch = spec.get_voting_source(
        store, signed_block_y.message.hash_tree_root()
    ).epoch
    if is_justifying_previous_epoch:
        # y is filtered out & so z should be the head
        assert state.current_justified_checkpoint.epoch == store.justified_checkpoint.epoch == 3
        assert y_voting_source_epoch == 2
        assert y_voting_source_epoch != store.justified_checkpoint.epoch
        assert not (
            y_voting_source_epoch + 2 >= spec.compute_epoch_at_slot(spec.get_current_slot(store))
        )
        check_head_against_root(spec, store, signed_block_z.message.hash_tree_root())
    elif enough_ffg:
        # y is not filtered out & wins the LMD competition, so y should be the head
        assert state.current_justified_checkpoint.epoch == store.justified_checkpoint.epoch == 4
        assert y_voting_source_epoch == 3
        assert y_voting_source_epoch != store.justified_checkpoint.epoch
        assert y_voting_source_epoch + 2 >= spec.compute_epoch_at_slot(spec.get_current_slot(store))
        check_head_against_root(spec, store, signed_block_y.message.hash_tree_root())
    else:
        # y is not filtered out & wins the LMD competition, so y should be the head
        assert state.current_justified_checkpoint.epoch == store.justified_checkpoint.epoch == 3
        assert y_voting_source_epoch == 3
        assert y_voting_source_epoch == store.justified_checkpoint.epoch
        check_head_against_root(spec, store, signed_block_y.message.hash_tree_root())

    # to next epoch
    next_epoch(spec, state)
    current_time = state.slot * spec.config.SLOT_DURATION_MS // 1000 + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    assert spec.compute_epoch_at_slot(spec.get_current_slot(store)) == 6

    y_voting_source_epoch = spec.get_voting_source(
        store, signed_block_y.message.hash_tree_root()
    ).epoch
    if is_justifying_previous_epoch:
        # y is filtered out & so z should be the head
        assert state.current_justified_checkpoint.epoch == store.justified_checkpoint.epoch == 3
        assert y_voting_source_epoch == 2
        assert y_voting_source_epoch != store.justified_checkpoint.epoch
        assert not (
            y_voting_source_epoch + 2 >= spec.compute_epoch_at_slot(spec.get_current_slot(store))
        )
        check_head_against_root(spec, store, signed_block_z.message.hash_tree_root())
    elif enough_ffg:
        # y is filtered out & so z should be the head
        assert state.current_justified_checkpoint.epoch == store.justified_checkpoint.epoch == 4
        assert y_voting_source_epoch == 3
        assert y_voting_source_epoch != store.justified_checkpoint.epoch
        assert not (
            y_voting_source_epoch + 2 >= spec.compute_epoch_at_slot(spec.get_current_slot(store))
        )
        check_head_against_root(spec, store, signed_block_z.message.hash_tree_root())
    else:
        # y is not filtered out & wins the LMD competition, so y should be the head
        assert state.current_justified_checkpoint.epoch == store.justified_checkpoint.epoch == 3
        assert y_voting_source_epoch == 3
        assert y_voting_source_epoch == store.justified_checkpoint.epoch
        check_head_against_root(spec, store, signed_block_y.message.hash_tree_root())

    yield "steps", test_steps


@with_altair_and_later
@spec_state_test
@with_presets(TESTING_PRESETS, reason="too slow")
def test_include_votes_another_empty_chain_with_enough_ffg_votes_current_epoch(spec, state):
    """
    [Case 3]
    """
    yield from _run_include_votes_of_another_empty_chain(
        spec, state, enough_ffg=True, is_justifying_previous_epoch=False
    )


@with_altair_and_later
@spec_state_test
@with_presets(TESTING_PRESETS, reason="too slow")
def test_include_votes_another_empty_chain_without_enough_ffg_votes_current_epoch(spec, state):
    """
    [Case 4]
    """
    yield from _run_include_votes_of_another_empty_chain(
        spec, state, enough_ffg=False, is_justifying_previous_epoch=False
    )


@with_altair_and_later
@spec_state_test
@with_presets(TESTING_PRESETS, reason="too slow")
def test_delayed_justification_current_epoch(spec, state):
    """
    [Case 5]

    To compare with ``test_simple_attempted_reorg_delayed_justification_current_epoch``,
    this is the basic case if there is no chain z

    {      epoch 4     }{     epoch 5     }
    [c4]<--[b]<--[y]

    At c4, c3 is the latest justified checkpoint.

    block_b: the block that can justify c4.
    """
    yield from _run_delayed_justification(
        spec, state, attempted_reorg=False, is_justifying_previous_epoch=False
    )


@with_altair_and_later
@spec_state_test
@with_presets(TESTING_PRESETS, reason="too slow")
def test_delayed_justification_previous_epoch(spec, state):
    """
    [Case 6]

    Similar to ``test_delayed_justification_current_epoch``,
    but includes attestations during epoch N to justify checkpoint N-1.

    {     epoch 3     }{     epoch 4     }{     epoch 5     }
    [c3]<---------------[c4]---[b]<---------------------------------[y]

    """
    yield from _run_delayed_justification(
        spec, state, attempted_reorg=False, is_justifying_previous_epoch=True
    )


@with_altair_and_later
@spec_state_test
@with_presets(TESTING_PRESETS, reason="too slow")
def test_simple_attempted_reorg_delayed_justification_previous_epoch(spec, state):
    """
    [Case 7]

    Similar to ``test_simple_attempted_reorg_delayed_justification_current_epoch``,
    but includes attestations during epoch N to justify checkpoint N-1.

    {     epoch 3     }{     epoch 4     }{     epoch 5     }
    [c3]<---------------[c4]<--[b]<--[y]
                                 ↑______________[z]

    At c4, c2 is the latest justified checkpoint.

    block_b: the block that can justify c3.
    z: the child of block of x at the first slot of epoch 5.
    block z can reorg the chain from block y.
    """
    yield from _run_delayed_justification(
        spec, state, attempted_reorg=True, is_justifying_previous_epoch=True
    )


@with_altair_and_later
@spec_state_test
@with_presets(TESTING_PRESETS, reason="too slow")
def test_include_votes_another_empty_chain_with_enough_ffg_votes_previous_epoch(spec, state):
    """
    [Case 8]

    Similar to ``test_include_votes_another_empty_chain_with_enough_ffg_votes_current_epoch``,
    but includes attestations during epoch N to justify checkpoint N-1.

    """
    yield from _run_include_votes_of_another_empty_chain(
        spec, state, enough_ffg=True, is_justifying_previous_epoch=True
    )
