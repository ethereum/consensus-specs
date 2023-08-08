from eth2spec.test.context import spec_state_test, with_config_overrides, with_presets, with_bellatrix_and_later
from eth2spec.test.helpers.attestations import (
    get_valid_attestation_at_slot
)
from eth2spec.test.helpers.constants import MINIMAL
from eth2spec.test.helpers.fork_choice import (
    apply_next_epoch_with_attestations,
    apply_next_slots_with_attestations,
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


def apply_next_epoch_with_attestations_no_checks_and_optimistic(
    spec, state, store, fill_cur_epoch, fill_prev_epoch, participation_fn=None, test_steps=None
):
    post_state, store, last_signed_block = yield from apply_next_epoch_with_attestations(
        spec, state, store, fill_cur_epoch, fill_prev_epoch, participation_fn=participation_fn,
        test_steps=test_steps, is_optimistic=True, store_checks=False)

    return post_state, store, last_signed_block


def apply_next_slots_with_attestations_no_checks_and_optimistic(
    spec, state, store, slots, fill_cur_epoch, fill_prev_epoch, test_steps, participation_fn=None
):
    post_state, store, last_signed_block = yield from apply_next_slots_with_attestations(
        spec, state, store, slots, fill_cur_epoch, fill_prev_epoch, test_steps, participation_fn=participation_fn,
        is_optimistic=True, store_checks=False)

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
    assert spec.is_ffg_confirmed(store, root)

    check_is_confirmed(spec, store, root, test_steps, False)
    check_get_confirmation_score(spec, store, root, test_steps, -1)

    confirmed_block = get_block_root_from_head(spec, store, 3)
    assert spec.compute_epoch_at_slot(store.blocks[confirmed_block].slot) == spec.get_current_store_epoch(store) - 1

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
    on_tick_and_append_step_no_checks(spec, store, store.genesis_time + state.slot * spec.config.SECONDS_PER_SLOT,
                                      test_steps)

    for _ in range(2):
        state, store, _ = yield from apply_next_epoch_with_attestations_no_checks_and_optimistic(
            spec, state, store, True, True, test_steps=test_steps
        )

    root = get_block_root_from_head(spec, store, 1)
    block = store.blocks[root]

    assert spec.compute_epoch_at_slot(block.slot) + 1 == spec.get_current_store_epoch(store)

    assert spec.is_lmd_confirmed(store, root)
    assert spec.is_ffg_confirmed(store, root)
    check_is_confirmed(spec, store, root, test_steps, False)
    check_get_confirmation_score(spec, store, root, test_steps, -1)

    yield "steps", test_steps


@with_bellatrix_and_later
@spec_state_test
@with_config_overrides({
    'CONFIRMATION_BYZANTINE_THRESHOLD': 30,
    'CONFIRMATION_SLASHING_THRESHOLD': 0
})
def test_no_confirm_current_epoch_but_ffg_confirmed(spec, state):
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
        spec, state, store, 2, True, True, test_steps=test_steps
    )

    root = get_block_root_from_head(spec, store, 1)
    block = store.blocks[root]

    assert spec.compute_epoch_at_slot(block.slot) == spec.get_current_store_epoch(store)

    assert spec.is_ffg_confirmed(store, root)
    block_state = store.block_states[root]
    assert block_state.current_justified_checkpoint.epoch + 1 == spec.get_current_store_epoch(store)
    check_is_confirmed(spec, store, root, test_steps, False)
    assert spec.get_confirmation_score(store, root) < 30
    check_get_confirmation_score(spec, store, root, test_steps)

    yield "steps", test_steps


@with_bellatrix_and_later
@spec_state_test
@with_config_overrides({
    'CONFIRMATION_BYZANTINE_THRESHOLD': 30,
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

    assert spec.is_ffg_confirmed(store, root)
    block_state = store.block_states[root]
    assert block_state.current_justified_checkpoint.epoch + 2 == spec.get_current_store_epoch(store)
    check_is_confirmed(spec, store, root, test_steps, False)
    assert spec.get_confirmation_score(store, root) < 30
    check_get_confirmation_score(spec, store, root, test_steps)

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

    check_is_confirmed(spec, store, root, test_steps, False)
    assert spec.get_confirmation_score(store, root) < 15
    check_get_confirmation_score(spec, store, root, test_steps)

    yield "steps", test_steps


# @with_bellatrix_and_later
# @with_presets([MINIMAL])
# @spec_state_test
# @confirmation_rule_setup(confirmation_byzantine_threshold=15, confirmation_slashing_threshold=2048000000000)
# def test_no_confirm_previous_epoch_but_lmd_confirmed(
#     spec,
#     state,
#     check_is_confirmed,
#     check_get_confirmation_score,
#     is_lmd_confirmed,
#     is_ffg_confirmed
# ):
#     assert spec.get_current_epoch(state) == spec.GENESIS_EPOCH

#     test_steps = []
#     # Initialization
#     store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
#     yield 'anchor_state', state
#     yield 'anchor_block', anchor_block
#     current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
#     on_tick_step(spec, store, current_time, test_steps)
#     assert store.time == current_time

#     next_epoch(spec, state)
#     on_tick_step(spec, store, store.genesis_time + state.slot * spec.config.SECONDS_PER_SLOT, test_steps)

#     # Fill epoch 1 to 3
#     for _ in range(3):
#         state, store, _ = yield from apply_next_epoch_with_attestations_no_checks(
#             spec, state, store, True, True, test_steps=test_steps)

#     root = get_block_root_from_head(spec, store, 1)
#     block = store.blocks[root]

#     assert spec.compute_epoch_at_slot(block.slot) + 1 == spec.get_current_store_epoch(store)

#     # assert is_lmd_confirmed(spec, store, root)
#     block_state = store.block_states[root]
#     assert block_state.current_justified_checkpoint.epoch + 2 == spec.get_current_store_epoch(store)
#     print(spec.get_confirmation_score(store, 2048000000000, root))
#     print(spec.get_lmd_confirmation_score(store, root))
#     print(spec.get_ffg_confirmation_score(store, 2048000000000, root))
#     # check_is_confirmed(spec, store, root, test_steps, False)

#     yield 'steps', test_steps


@with_bellatrix_and_later
@with_presets([MINIMAL])
@spec_state_test
@with_config_overrides({
    'CONFIRMATION_BYZANTINE_THRESHOLD': 0,
    'CONFIRMATION_SLASHING_THRESHOLD': 0
})
def test_current_get_confirmation_score_no_slashing_threshold(spec, state):
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

    check_get_confirmation_score(spec, store, root, test_steps, 23)

    yield "steps", test_steps


@with_bellatrix_and_later
@with_presets([MINIMAL])
@spec_state_test
@with_config_overrides({
    'CONFIRMATION_BYZANTINE_THRESHOLD': 0,
    'CONFIRMATION_SLASHING_THRESHOLD': 2048000000000
})
def test_current_get_confirmation_score_slashing_threshold(spec, state):
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

    check_get_confirmation_score(spec, store, root, test_steps, 13)

    yield "steps", test_steps


@with_bellatrix_and_later
@with_presets([MINIMAL])
@spec_state_test
@with_config_overrides({
    'CONFIRMATION_BYZANTINE_THRESHOLD': 0,
    'CONFIRMATION_SLASHING_THRESHOLD': 0
})
def test_previous_epoch_get_confirmation_score_no_slashing_threshold(spec, state):
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

    for _ in range(3):
        state, store, _ = yield from apply_next_epoch_with_attestations_no_checks_and_optimistic(
            spec, state, store, True, True, test_steps=test_steps
        )

    root = get_block_root_from_head(spec, store, spec.SLOTS_PER_EPOCH // 2)
    block = store.blocks[root]

    assert spec.compute_epoch_at_slot(block.slot) + 1 == spec.get_current_store_epoch(store)

    check_get_confirmation_score(spec, store, root, test_steps, 33)

    yield "steps", test_steps


@with_bellatrix_and_later
@with_presets([MINIMAL])
@spec_state_test
@with_config_overrides({
    'CONFIRMATION_BYZANTINE_THRESHOLD': 0,
    'CONFIRMATION_SLASHING_THRESHOLD': 0
})
def test_prior_to_previous_epoch_get_confirmation_score_no_slashing_threshold(spec, state):
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

    for _ in range(3):
        state, store, _ = yield from apply_next_epoch_with_attestations_no_checks_and_optimistic(
            spec, state, store, True, True, test_steps=test_steps
        )

    root = get_block_root_from_head(spec, store, spec.SLOTS_PER_EPOCH + 1)
    block = store.blocks[root]

    assert spec.compute_epoch_at_slot(block.slot) + 2 == spec.get_current_store_epoch(store)

    check_get_confirmation_score(spec, store, root, test_steps, 33)

    yield "steps", test_steps
