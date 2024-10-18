from eth2spec.test.context import spec_state_test, with_config_overrides, with_presets, with_bellatrix_and_later
from eth2spec.test.helpers.attestations import (
    get_valid_attestation_at_slot,
    get_valid_attestations_at_slot,
    next_epoch_with_attestations,
    next_slots_with_attestations,
    state_transition_with_full_block
)
from eth2spec.test.helpers.constants import MINIMAL
from eth2spec.test.helpers.fork_choice import (
    add_attestations,
    add_block,
    get_genesis_forkchoice_store_and_block,
    on_tick_and_append_step
)

from eth2spec.test.helpers.state import (
    next_epoch,
)


def on_tick_and_append_step_no_checks(spec, store, time, test_steps):
    on_tick_and_append_step(spec, store, time, test_steps, store_checks=False)


def tick_to_next_slot(spec, store, test_steps):
    time = store.genesis_time + (spec.get_current_slot(store) + 1) * spec.config.SECONDS_PER_SLOT
    on_tick_and_append_step_no_checks(spec, store, time, test_steps)


def conf_rule_apply_next_epoch_with_attestations(
    spec, state, store, fill_cur_epoch, fill_prev_epoch, participation_fn=None, test_steps=None,
    is_optimistic=False, store_checks=True
):

    if test_steps is None:
        test_steps = []

    _, new_signed_blocks, post_state = next_epoch_with_attestations(
        spec, state, fill_cur_epoch, fill_prev_epoch, participation_fn=participation_fn)
    for signed_block in new_signed_blocks:
        block = signed_block.message
        yield from conf_rule_tick_and_add_block(
            spec, store, signed_block, test_steps, is_optimistic=is_optimistic, store_checks=store_checks)
        block_root = block.hash_tree_root()
        assert store.blocks[block_root] == block
        last_signed_block = signed_block

    assert store.block_states[block_root].hash_tree_root() == post_state.hash_tree_root()

    return post_state, store, last_signed_block


def conf_rule_apply_next_slots_with_attestations(
    spec, state, store, slots, fill_cur_epoch, fill_prev_epoch, participation_fn=None, test_steps=None,
    is_optimistic=False, store_checks=True
):
    _, new_signed_blocks, post_state = next_slots_with_attestations(
        spec, state, slots, fill_cur_epoch, fill_prev_epoch, participation_fn=participation_fn)

    for signed_block in new_signed_blocks:
        block = signed_block.message
        yield from conf_rule_tick_and_add_block(
            spec, store, signed_block, test_steps, is_optimistic=is_optimistic, store_checks=store_checks)
        block_root = block.hash_tree_root()
        assert store.blocks[block_root] == block
        last_signed_block = signed_block

    assert store.block_states[block_root].hash_tree_root() == post_state.hash_tree_root()

    return post_state, store, last_signed_block


def apply_next_epoch_with_attestations_no_checks_and_optimistic(
    spec, state, store, fill_cur_epoch, fill_prev_epoch, participation_fn=None, test_steps=None
):
    post_state, store, last_signed_block = yield from conf_rule_apply_next_epoch_with_attestations(
        spec, state, store, fill_cur_epoch, fill_prev_epoch, participation_fn=participation_fn,
        test_steps=test_steps, is_optimistic=True, store_checks=False)

    return post_state, store, last_signed_block


def apply_next_slots_with_attestations_no_checks_and_optimistic(
    spec, state, store, slots, fill_cur_epoch, fill_prev_epoch, test_steps, participation_fn=None
):
    post_state, store, last_signed_block = yield from conf_rule_apply_next_slots_with_attestations(
        spec, state, store, slots, fill_cur_epoch, fill_prev_epoch,
        participation_fn=participation_fn, test_steps=test_steps,
        is_optimistic=True, store_checks=False)

    return post_state, store, last_signed_block


def conf_rule_tick_and_add_block(
    spec, store, signed_block, test_steps, valid=True, merge_block=False, block_not_found=False,
    is_optimistic=False, blob_data=None, store_checks=True
):

    pre_state = store.block_states[signed_block.message.parent_root]
    if merge_block:
        assert spec.is_merge_transition_block(pre_state, signed_block.message.body)

    block_time = pre_state.genesis_time + signed_block.message.slot * spec.config.SECONDS_PER_SLOT
    while store.time < block_time:
        time = pre_state.genesis_time + (spec.get_current_slot(store) + 1) * spec.config.SECONDS_PER_SLOT
        on_tick_and_append_step(spec, store, time, test_steps, store_checks)
        yield from add_attestations(spec, store, signed_block.message.body.attestations, test_steps, False)
        spec.immediately_after_on_tick_if_slot_changed(store)

    post_state = yield from add_block(
        spec, store, signed_block, test_steps,
        valid=valid,
        block_not_found=block_not_found,
        is_optimistic=is_optimistic,
        blob_data=blob_data,
    )

    return post_state


def apply_next_epoch_with_attestations_in_blocks_and_on_attestation_no_checks_and_opt(
    spec, state, store, fill_cur_epoch, fill_prev_epoch, participation_fn=None, test_steps=None
):

    post_state = state.copy()

    for _ in range(spec.SLOTS_PER_EPOCH):
        attestations = list(get_valid_attestations_at_slot(
            post_state,
            spec,
            post_state.slot - spec.MIN_ATTESTATION_INCLUSION_DELAY + 1,
            None
        ))
        last_signed_block = state_transition_with_full_block(
            spec,
            post_state,
            fill_cur_epoch,
            fill_prev_epoch,
            participation_fn,
        )

        yield from conf_rule_tick_and_add_block(
            spec, store, last_signed_block, test_steps, is_optimistic=True, store_checks=False)

        yield from add_attestations(spec, store, attestations, test_steps, False)

    return post_state, store, last_signed_block


def get_ancestor(store, root, ancestor_number):
    if ancestor_number == 0:
        return root
    else:
        return get_ancestor(store, store.blocks[root].parent_root, ancestor_number - 1)


def get_block_root_from_head(spec, store, depth):
    head_root = spec.get_head(store)
    return get_ancestor(store, head_root, depth)


def get_valid_attestation_for_block(spec, store, block_root, perc):
    """
    Get attestation filled by `perc`%
    """
    return list(
        get_valid_attestation_at_slot(
            store.block_states[block_root],
            spec,
            spec.get_slots_since_genesis(store),
            lambda slot, index, comm: set(list(comm)[0: int(len(comm) * perc)]),
        )
    )


def check_is_confirmed(spec, store, block_root, test_steps, expected=None):
    confirmed = int(spec.is_confirmed(store, block_root))

    if expected is not None:
        assert confirmed == expected
    test_steps.append({"check_is_confirmed": {"result": confirmed, "block_root": str(block_root)}})


def check_get_confirmation_score(spec, store, block_root, test_steps, expected=None):
    confirmation_score = int(spec.get_confirmation_score(store, block_root))
    if expected is not None:
        assert confirmation_score == expected
    test_steps.append(
        {"check_get_confirmation_score": {"result": confirmation_score, "block_root": str(block_root)}}
    )


@with_bellatrix_and_later
@spec_state_test
@with_config_overrides({
    'CONFIRMATION_BYZANTINE_THRESHOLD': 0,
    'CONFIRMATION_SLASHING_THRESHOLD': 0
})
def test_confirm_current_epoch_no_byz(spec, state):
    assert spec.get_current_epoch(state) == spec.GENESIS_EPOCH

    test_steps = []
    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step_no_checks(spec, store, current_time, test_steps)
    assert store.time == current_time

    next_epoch(spec, state)
    on_tick_and_append_step_no_checks(spec, store, store.genesis_time + state.slot * spec.config.SECONDS_PER_SLOT,
                                      test_steps)

    # Fill epoch 1 to 2
    for _ in range(2):
        state, store, _ = yield from apply_next_epoch_with_attestations_no_checks_and_optimistic(
            spec, state, store, True, True, test_steps=test_steps
        )

    state, store, _ = yield from apply_next_slots_with_attestations_no_checks_and_optimistic(
        spec, state, store, 2, True, True, test_steps=test_steps
    )

    root = get_block_root_from_head(spec, store, 1)
    block = store.blocks[root]

    assert spec.compute_epoch_at_slot(block.slot) == spec.get_current_store_epoch(store)

    check_is_confirmed(spec, store, root, test_steps, True)

    yield "steps", test_steps


@with_bellatrix_and_later
@spec_state_test
@with_config_overrides({
    'CONFIRMATION_BYZANTINE_THRESHOLD': 0,
    'CONFIRMATION_SLASHING_THRESHOLD': 0
})
def test_confirm_previous_epoch_no_byz(spec, state):
    assert spec.get_current_epoch(state) == spec.GENESIS_EPOCH

    test_steps = []
    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step_no_checks(spec, store, current_time, test_steps)
    assert store.time == current_time

    next_epoch(spec, state)
    on_tick_and_append_step_no_checks(spec, store, store.genesis_time + state.slot * spec.config.SECONDS_PER_SLOT,
                                      test_steps)

    # Fill epoch 1 to 3
    for _ in range(3):
        state, store, _ = yield from apply_next_epoch_with_attestations_no_checks_and_optimistic(
            spec, state, store, True, True, test_steps=test_steps
        )

    root = get_block_root_from_head(spec, store, 1)
    block = store.blocks[root]

    assert spec.compute_epoch_at_slot(block.slot) + 1 == spec.get_current_store_epoch(store)

    check_is_confirmed(spec, store, root, test_steps, True)

    yield "steps", test_steps


@with_bellatrix_and_later
@spec_state_test
@with_config_overrides({
    'CONFIRMATION_BYZANTINE_THRESHOLD': 0,
    'CONFIRMATION_SLASHING_THRESHOLD': 0
})
def test_confirm_prior_to_previous_epoch_no_byz(spec, state):
    assert spec.get_current_epoch(state) == spec.GENESIS_EPOCH

    test_steps = []
    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step_no_checks(spec, store, current_time, test_steps)
    assert store.time == current_time

    next_epoch(spec, state)
    on_tick_and_append_step_no_checks(spec, store, store.genesis_time + state.slot * spec.config.SECONDS_PER_SLOT,
                                      test_steps)

    # Fill epoch 1 to 3
    for _ in range(3):
        state, store, _ = yield from apply_next_epoch_with_attestations_no_checks_and_optimistic(
            spec, state, store, True, True, test_steps=test_steps
        )

    root = get_block_root_from_head(spec, store, spec.SLOTS_PER_EPOCH + 1)
    block = store.blocks[root]

    assert spec.compute_epoch_at_slot(block.slot) + 2 == spec.get_current_store_epoch(store)

    check_is_confirmed(spec, store, root, test_steps, True)

    yield "steps", test_steps


@with_bellatrix_and_later
@spec_state_test
@with_config_overrides({
    'CONFIRMATION_BYZANTINE_THRESHOLD': 0,
    'CONFIRMATION_SLASHING_THRESHOLD': 0
})
def test_no_confirm_current_epoch_due_to_no_lmd_confirmed(spec, state):
    assert spec.get_current_epoch(state) == spec.GENESIS_EPOCH

    test_steps = []
    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step_no_checks(spec, store, current_time, test_steps)
    assert store.time == current_time

    next_epoch(spec, state)
    on_tick_and_append_step_no_checks(spec, store, store.genesis_time + state.slot * spec.config.SECONDS_PER_SLOT,
                                      test_steps)

    # Fill epoch 1 to 2
    for _ in range(2):
        state, store, _ = yield from apply_next_epoch_with_attestations_no_checks_and_optimistic(
            spec, state, store, True, True, test_steps=test_steps
        )

    sate_copy = state.copy()

    _, store, _ = yield from apply_next_slots_with_attestations_no_checks_and_optimistic(
        spec, sate_copy, store, 3, True, True, test_steps=test_steps
    )

    state, store, last_signed_block = yield from apply_next_slots_with_attestations_no_checks_and_optimistic(
        spec, state, store, 3, False, False, test_steps=test_steps
    )

    root = get_ancestor(store, last_signed_block.message.parent_root, 1)
    block = store.blocks[root]

    assert spec.compute_epoch_at_slot(block.slot) == spec.get_current_store_epoch(store)

    assert not spec.is_lmd_confirmed(store, root)
    assert spec.is_ffg_confirmed(store, root, spec.get_current_store_epoch(store))
    check_is_confirmed(spec, store, root, test_steps, False)

    yield "steps", test_steps


@with_bellatrix_and_later
@spec_state_test
@with_config_overrides({
    'CONFIRMATION_BYZANTINE_THRESHOLD': 0,
    'CONFIRMATION_SLASHING_THRESHOLD': 0
})
def test_no_confirm_current_epoch_due_to_justified_checkpoint(spec, state):
    assert spec.get_current_epoch(state) == spec.GENESIS_EPOCH

    test_steps = []
    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step_no_checks(spec, store, current_time, test_steps)
    assert store.time == current_time

    next_epoch(spec, state)
    on_tick_and_append_step_no_checks(spec, store, store.genesis_time + state.slot * spec.config.SECONDS_PER_SLOT,
                                      test_steps)

    # Fill epoch 1 to 2
    for _ in range(1):
        state, store, _ = yield from apply_next_epoch_with_attestations_no_checks_and_optimistic(
            spec, state, store, True, True, test_steps=test_steps
        )

    state, store, _ = yield from apply_next_slots_with_attestations_no_checks_and_optimistic(
        spec, state, store, 2, True, True, test_steps=test_steps
    )

    root = get_block_root_from_head(spec, store, 1)
    block = store.blocks[root]

    assert spec.compute_epoch_at_slot(block.slot) == spec.get_current_store_epoch(store)

    assert spec.is_lmd_confirmed(store, root)
    assert spec.is_ffg_confirmed(store, root, spec.get_current_store_epoch(store))

    check_is_confirmed(spec, store, root, test_steps, False)

    yield "steps", test_steps


@with_bellatrix_and_later
@spec_state_test
@with_config_overrides({
    'CONFIRMATION_BYZANTINE_THRESHOLD': 0,
    'CONFIRMATION_SLASHING_THRESHOLD': 0
})
def test_no_confirm_previous_epoch_due_to_justified_checkpoint(spec, state):
    assert spec.get_current_epoch(state) == spec.GENESIS_EPOCH

    test_steps = []
    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step_no_checks(spec, store, current_time, test_steps)
    assert store.time == current_time

    next_epoch(spec, state)
    on_tick_and_append_step_no_checks(
        spec, store, store.genesis_time + state.slot * spec.config.SECONDS_PER_SLOT, test_steps)

    for _ in range(2):
        state, store, _ = yield from apply_next_epoch_with_attestations_in_blocks_and_on_attestation_no_checks_and_opt(
            spec, state, store, False, False, test_steps=test_steps)

    root = get_block_root_from_head(spec, store, 1)
    block = store.blocks[root]

    assert spec.compute_epoch_at_slot(block.slot) + 1 == spec.get_current_store_epoch(store)

    assert spec.is_lmd_confirmed(store, root)
    assert spec.is_ffg_confirmed(store, root, spec.compute_epoch_at_slot(block.slot))
    check_is_confirmed(spec, store, root, test_steps, False)

    yield "steps", test_steps


@with_bellatrix_and_later
@spec_state_test
@with_config_overrides({
    'CONFIRMATION_BYZANTINE_THRESHOLD': 50,
    'CONFIRMATION_SLASHING_THRESHOLD': 0
})
def test_no_confirm_previous_epoch_but_ffg_confirmed(spec, state):
    assert spec.get_current_epoch(state) == spec.GENESIS_EPOCH

    test_steps = []
    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step_no_checks(spec, store, current_time, test_steps)
    assert store.time == current_time

    next_epoch(spec, state)
    on_tick_and_append_step_no_checks(spec, store, store.genesis_time + state.slot * spec.config.SECONDS_PER_SLOT,
                                      test_steps)

    # Fill epoch 1 to 3
    for _ in range(3):
        state, store, _ = yield from apply_next_epoch_with_attestations_no_checks_and_optimistic(
            spec, state, store, True, True, test_steps=test_steps
        )

    root = get_block_root_from_head(spec, store, 1)
    block = store.blocks[root]

    assert spec.compute_epoch_at_slot(block.slot) + 1 == spec.get_current_store_epoch(store)

    assert spec.is_ffg_confirmed(store, root, spec.compute_epoch_at_slot(block.slot))
    block_state = store.block_states[root]
    assert block_state.current_justified_checkpoint.epoch + 2 == spec.get_current_store_epoch(store)
    check_is_confirmed(spec, store, root, test_steps, False)

    yield "steps", test_steps


@with_bellatrix_and_later
@with_presets([MINIMAL])
@spec_state_test
@with_config_overrides({
    'CONFIRMATION_BYZANTINE_THRESHOLD': 15,
    'CONFIRMATION_SLASHING_THRESHOLD': 2048000000000
})
def test_no_confirm_current_epoch_but_lmd_confirmed(spec, state):
    assert spec.get_current_epoch(state) == spec.GENESIS_EPOCH

    test_steps = []
    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step_no_checks(spec, store, current_time, test_steps)
    assert store.time == current_time

    next_epoch(spec, state)
    on_tick_and_append_step_no_checks(spec, store, store.genesis_time + state.slot * spec.config.SECONDS_PER_SLOT,
                                      test_steps)

    for _ in range(2):
        state, store, _ = yield from apply_next_epoch_with_attestations_no_checks_and_optimistic(
            spec, state, store, True, True, test_steps=test_steps
        )

    state, store, _ = yield from apply_next_slots_with_attestations_no_checks_and_optimistic(
        spec, state, store, 3, True, True, test_steps=test_steps
    )

    root = get_block_root_from_head(spec, store, 2)
    block = store.blocks[root]

    assert spec.compute_epoch_at_slot(block.slot) == spec.get_current_store_epoch(store)

    assert spec.is_lmd_confirmed(store, root)
    block_state = store.block_states[root]
    assert block_state.current_justified_checkpoint.epoch + 1 == spec.get_current_store_epoch(store)

    yield "steps", test_steps
