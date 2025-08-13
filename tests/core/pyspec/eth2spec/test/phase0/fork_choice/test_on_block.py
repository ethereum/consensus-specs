import random

from eth_utils import encode_hex

from eth2spec.test.context import MINIMAL, spec_state_test, with_altair_and_later, with_presets
from eth2spec.test.helpers.attestations import (
    next_epoch_with_attestations,
    next_slots_with_attestations,
)
from eth2spec.test.helpers.block import (
    build_empty_block,
    build_empty_block_for_next_slot,
    sign_block,
    transition_unsigned_block,
)
from eth2spec.test.helpers.execution_payload import (
    build_empty_execution_payload,
    compute_el_block_hash,
    compute_el_block_hash_for_block,
)
from eth2spec.test.helpers.fork_choice import (
    add_block,
    apply_next_epoch_with_attestations,
    apply_next_slots_with_attestations,
    check_head_against_root,
    find_next_justifying_slot,
    get_genesis_forkchoice_store_and_block,
    get_store_full_state,
    is_ready_to_justify,
    on_tick_and_append_step,
    tick_and_add_block,
)
from eth2spec.test.helpers.forks import (
    is_post_bellatrix,
    is_post_eip7732,
)
from eth2spec.test.helpers.state import (
    next_epoch,
    next_slots,
    payload_state_transition,
    state_transition_and_sign_block,
)
from eth2spec.utils.ssz.ssz_impl import hash_tree_root

rng = random.Random(2020)


def _drop_random_one_third(_slot, _index, indices):
    committee_len = len(indices)
    assert committee_len >= 3
    filter_len = committee_len // 3
    participant_count = committee_len - filter_len
    return rng.sample(sorted(indices), participant_count)


@with_altair_and_later
@spec_state_test
def test_basic(spec, state):
    test_steps = []
    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    assert store.time == current_time

    # On receiving a block of `GENESIS_SLOT + 1` slot
    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block)
    yield from tick_and_add_block(spec, store, signed_block, test_steps)
    check_head_against_root(spec, store, signed_block.message.hash_tree_root())
    payload_state_transition(spec, store, signed_block.message)

    # On receiving a block of next epoch
    store.time = current_time + spec.config.SECONDS_PER_SLOT * spec.SLOTS_PER_EPOCH
    block = build_empty_block(spec, state, state.slot + spec.SLOTS_PER_EPOCH)
    signed_block = state_transition_and_sign_block(spec, state, block)
    yield from tick_and_add_block(spec, store, signed_block, test_steps)
    check_head_against_root(spec, store, signed_block.message.hash_tree_root())
    payload_state_transition(spec, store, signed_block.message)

    yield "steps", test_steps

    # TODO: add tests for justified_root and finalized_root


@with_altair_and_later
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_on_block_checkpoints(spec, state):
    test_steps = []
    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    assert store.time == current_time

    # Run for 1 epoch with full attestations
    next_epoch(spec, state)
    on_tick_and_append_step(
        spec, store, store.genesis_time + state.slot * spec.config.SECONDS_PER_SLOT, test_steps
    )

    state, store, last_signed_block = yield from apply_next_epoch_with_attestations(
        spec, state, store, True, False, test_steps=test_steps
    )
    last_block_root = hash_tree_root(last_signed_block.message)
    check_head_against_root(spec, store, last_block_root)

    # Forward 1 epoch
    next_epoch(spec, state)
    on_tick_and_append_step(
        spec, store, store.genesis_time + state.slot * spec.config.SECONDS_PER_SLOT, test_steps
    )

    # Mock the finalized_checkpoint and build a block on it
    if is_post_eip7732(spec):
        fin_state = store.execution_payload_states[last_block_root].copy()
    else:
        fin_state = store.block_states[last_block_root].copy()

    fin_state.finalized_checkpoint = store.block_states[
        last_block_root
    ].current_justified_checkpoint.copy()
    block = build_empty_block_for_next_slot(spec, fin_state)
    signed_block = state_transition_and_sign_block(spec, fin_state, block)
    yield from tick_and_add_block(spec, store, signed_block, test_steps)
    check_head_against_root(spec, store, signed_block.message.hash_tree_root())
    payload_state_transition(spec, store, signed_block.message)
    yield "steps", test_steps


@with_altair_and_later
@spec_state_test
def test_on_block_future_block(spec, state):
    test_steps = []
    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    assert store.time == current_time

    # Do NOT tick time to `GENESIS_SLOT + 1` slot
    # Fail receiving block of `GENESIS_SLOT + 1` slot
    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block)
    yield from add_block(spec, store, signed_block, test_steps, valid=False)

    yield "steps", test_steps


@with_altair_and_later
@spec_state_test
def test_on_block_bad_parent_root(spec, state):
    test_steps = []
    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    assert store.time == current_time

    # Fail receiving block of `GENESIS_SLOT + 1` slot
    block = build_empty_block_for_next_slot(spec, state)
    transition_unsigned_block(spec, state, block)
    block.state_root = state.hash_tree_root()

    block.parent_root = b"\x45" * 32
    if is_post_eip7732(spec):
        payload = build_empty_execution_payload(spec, state)
        block.body.signed_execution_payload_header.message.block_hash = compute_el_block_hash(
            spec, payload, state
        )
    elif is_post_bellatrix(spec):
        block.body.execution_payload.block_hash = compute_el_block_hash_for_block(spec, block)

    signed_block = sign_block(spec, state, block)

    yield from add_block(spec, store, signed_block, test_steps, valid=False)

    yield "steps", test_steps


@with_altair_and_later
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_on_block_before_finalized(spec, state):
    test_steps = []
    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    assert store.time == current_time

    # Fork
    another_state = state.copy()

    # Create a finalized chain
    for _ in range(4):
        state, store, _ = yield from apply_next_epoch_with_attestations(
            spec, state, store, True, False, test_steps=test_steps
        )
    assert store.finalized_checkpoint.epoch == 2

    # Fail receiving block of `GENESIS_SLOT + 1` slot
    block = build_empty_block_for_next_slot(spec, another_state)
    block.body.graffiti = b"\x12" * 32
    signed_block = state_transition_and_sign_block(spec, another_state, block)
    assert signed_block.message.hash_tree_root() not in store.blocks
    yield from tick_and_add_block(spec, store, signed_block, test_steps, valid=False)

    yield "steps", test_steps


@with_altair_and_later
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_on_block_finalized_skip_slots(spec, state):
    """
    Test case was originally from https://github.com/ethereum/consensus-specs/pull/1579
    And then rewrote largely.
    """
    test_steps = []
    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    assert store.time == current_time

    # Fill epoch 0 and the first slot of epoch 1
    state, store, _ = yield from apply_next_slots_with_attestations(
        spec, state, store, spec.SLOTS_PER_EPOCH, True, False, test_steps
    )

    # Skip the rest slots of epoch 1 and the first slot of epoch 2
    next_slots(spec, state, spec.SLOTS_PER_EPOCH)

    # The state after the skipped slots
    target_state = state.copy()

    # Fill epoch 3 and 4
    for _ in range(2):
        state, store, _ = yield from apply_next_epoch_with_attestations(
            spec, state, store, True, True, test_steps=test_steps
        )

    # Now we get finalized epoch 2, where `compute_start_slot_at_epoch(2)` is a skipped slot
    assert state.finalized_checkpoint.epoch == store.finalized_checkpoint.epoch == 2
    assert (
        store.finalized_checkpoint.root
        == spec.get_block_root(state, 1)
        == spec.get_block_root(state, 2)
    )
    assert state.current_justified_checkpoint.epoch == store.justified_checkpoint.epoch == 3
    assert store.justified_checkpoint == state.current_justified_checkpoint

    # Now build a block at later slot than finalized *epoch*
    # Includes finalized block in chain and the skipped slots
    block = build_empty_block_for_next_slot(spec, target_state)
    signed_block = state_transition_and_sign_block(spec, target_state, block)
    yield from tick_and_add_block(spec, store, signed_block, test_steps)
    payload_state_transition(spec, store, signed_block.message)

    yield "steps", test_steps


@with_altair_and_later
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_on_block_finalized_skip_slots_not_in_skip_chain(spec, state):
    """
    Test case was originally from https://github.com/ethereum/consensus-specs/pull/1579
    And then rewrote largely.
    """
    test_steps = []
    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    assert store.time == current_time

    # Fill epoch 0 and the first slot of epoch 1
    state, store, _ = yield from apply_next_slots_with_attestations(
        spec, state, store, spec.SLOTS_PER_EPOCH, True, False, test_steps
    )

    # Skip the rest slots of epoch 1 and the first slot of epoch 2
    next_slots(spec, state, spec.SLOTS_PER_EPOCH)

    # Fill epoch 3 and 4
    for _ in range(2):
        state, store, _ = yield from apply_next_epoch_with_attestations(
            spec, state, store, True, True, test_steps=test_steps
        )

    # Now we get finalized epoch 2, where `compute_start_slot_at_epoch(2)` is a skipped slot
    assert state.finalized_checkpoint.epoch == store.finalized_checkpoint.epoch == 2
    assert (
        store.finalized_checkpoint.root
        == spec.get_block_root(state, 1)
        == spec.get_block_root(state, 2)
    )
    assert state.current_justified_checkpoint.epoch == store.justified_checkpoint.epoch == 3
    assert store.justified_checkpoint == state.current_justified_checkpoint

    # Now build a block after the block of the finalized **root**
    # Includes finalized block in chain, but does not include finalized skipped slots
    another_state = store.block_states[store.finalized_checkpoint.root].copy()
    assert another_state.slot == spec.compute_start_slot_at_epoch(
        store.finalized_checkpoint.epoch - 1
    )
    block = build_empty_block_for_next_slot(spec, another_state)
    signed_block = state_transition_and_sign_block(spec, another_state, block)
    yield from tick_and_add_block(spec, store, signed_block, test_steps, valid=False)

    yield "steps", test_steps


"""
@with_altair_and_later
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_new_finalized_slot_is_not_justified_checkpoint_ancestor(spec, state):
    # J: Justified
    # F: Finalized
    # state (forked from genesis):
    #     epoch
    #     [0] <- [1] <- [2] <- [3] <- [4] <- [5]
    #      F                    J

    # another_state (forked from epoch 0):
    #      └──── [1] <- [2] <- [3] <- [4] <- [5]
    #                    F      J

    test_steps = []
    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield 'anchor_state', state
    yield 'anchor_block', anchor_block
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    assert store.time == current_time

    # ----- Process state
    # Goal: make `store.finalized_checkpoint.epoch == 0` and `store.justified_checkpoint.epoch == 3`
    # Skip epoch 0
    next_epoch(spec, state)

    # Forking another_state
    another_state = state.copy()

    # Fill epoch 1 with previous epoch attestations
    state, store, _ = yield from apply_next_epoch_with_attestations(
        spec, state, store, False, True, test_steps=test_steps)
    # Skip epoch 2
    next_epoch(spec, state)
    # Fill epoch 3 & 4 with previous epoch attestations
    for _ in range(2):
        state, store, _ = yield from apply_next_epoch_with_attestations(
            spec, state, store, False, True, test_steps=test_steps)

    assert state.finalized_checkpoint.epoch == store.finalized_checkpoint.epoch == 0
    assert state.current_justified_checkpoint.epoch == store.justified_checkpoint.epoch == 3
    assert store.justified_checkpoint == state.current_justified_checkpoint

    # Create another chain
    # Goal: make `another_state.finalized_checkpoint.epoch == 2` and `another_state.justified_checkpoint.epoch == 3`
    all_blocks = []
    # Fill epoch 1 & 2 with previous + current epoch attestations
    for _ in range(3):
        _, signed_blocks, another_state = next_epoch_with_attestations(spec, another_state, True, True)
        all_blocks += signed_blocks

    assert another_state.finalized_checkpoint.epoch == 2
    assert another_state.current_justified_checkpoint.epoch == 3
    assert state.finalized_checkpoint != another_state.finalized_checkpoint
    assert state.current_justified_checkpoint != another_state.current_justified_checkpoint

    pre_store_justified_checkpoint_root = store.justified_checkpoint.root

    # Apply blocks of `another_state` to `store`
    for block in all_blocks:
        # NOTE: Do not call `on_tick` here
        yield from add_block(spec, store, block, test_steps)

    ancestor_at_finalized_slot = spec.get_checkpoint_block(
        store,
        pre_store_justified_checkpoint_root,
        store.finalized_checkpoint.epoch
    )
    assert ancestor_at_finalized_slot != store.finalized_checkpoint.root

    assert store.finalized_checkpoint == another_state.finalized_checkpoint

    # NOTE: inconsistent justified/finalized checkpoints in this edge case.
    # This can only happen when >1/3 validators are slashable, as this testcase requires that
    # store.justified_checkpoint is higher than store.finalized_checkpoint and on a different branch.
    # Ignoring this testcase for now.
    assert store.justified_checkpoint != another_state.current_justified_checkpoint

    yield 'steps', test_steps
"""


@with_altair_and_later
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
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
    test_steps = []
    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    assert store.time == current_time

    # Process state
    next_epoch(spec, state)

    state, store, _ = yield from apply_next_epoch_with_attestations(
        spec, state, store, False, True, test_steps=test_steps
    )

    state, store, _ = yield from apply_next_epoch_with_attestations(
        spec, state, store, True, False, test_steps=test_steps
    )
    next_epoch(spec, state)

    for _ in range(2):
        state, store, _ = yield from apply_next_epoch_with_attestations(
            spec, state, store, False, True, test_steps=test_steps
        )

    assert state.finalized_checkpoint.epoch == store.finalized_checkpoint.epoch == 2
    assert state.current_justified_checkpoint.epoch == store.justified_checkpoint.epoch == 4
    assert store.justified_checkpoint == state.current_justified_checkpoint

    # Create another chain
    # Forking from epoch 3
    all_blocks = []
    slot = spec.compute_start_slot_at_epoch(3)
    block_root = spec.get_block_root_at_slot(state, slot)
    another_state = get_store_full_state(spec, store, block_root).copy()
    for _ in range(2):
        _, signed_blocks, another_state = next_epoch_with_attestations(
            spec, another_state, True, True
        )
        all_blocks += signed_blocks

    assert another_state.finalized_checkpoint.epoch == 3
    assert another_state.current_justified_checkpoint.epoch == 4

    pre_store_justified_checkpoint_root = store.justified_checkpoint.root
    for block in all_blocks:
        yield from tick_and_add_block(spec, store, block, test_steps)
        payload_state_transition(spec, store, block.message)

    ancestor_at_finalized_slot = spec.get_checkpoint_block(
        store, pre_store_justified_checkpoint_root, store.finalized_checkpoint.epoch
    )
    assert ancestor_at_finalized_slot == store.finalized_checkpoint.root

    assert store.finalized_checkpoint == another_state.finalized_checkpoint

    # NOTE: inconsistent justified/finalized checkpoints in this edge case
    assert store.justified_checkpoint != another_state.current_justified_checkpoint

    yield "steps", test_steps


@with_altair_and_later
@spec_state_test
def test_proposer_boost(spec, state):
    test_steps = []
    genesis_state = state.copy()

    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block

    # Build block that serves as head ONLY on timely arrival, and ONLY in that slot
    state = genesis_state.copy()
    next_slots(spec, state, 3)
    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block)

    # Process block on timely arrival just before end of boost interval
    # Round up to nearest second
    if is_post_eip7732(spec):
        late_block_cutoff_ms = spec.get_slot_component_duration_ms(
            spec.config.ATTESTATION_DUE_BPS_EIP7732
        )
    else:
        late_block_cutoff_ms = spec.get_slot_component_duration_ms(spec.config.ATTESTATION_DUE_BPS)
    late_block_cutoff = (late_block_cutoff_ms + 999) // 1000
    time = store.genesis_time + block.slot * spec.config.SECONDS_PER_SLOT + late_block_cutoff - 1

    on_tick_and_append_step(spec, store, time, test_steps)
    yield from add_block(spec, store, signed_block, test_steps)
    payload_state_transition(spec, store, signed_block.message)
    assert store.proposer_boost_root == spec.hash_tree_root(block)
    if is_post_eip7732(spec):
        node = spec.ForkChoiceNode(
            root=spec.hash_tree_root(block),
            payload_status=spec.PAYLOAD_STATUS_PENDING,
        )
        assert spec.get_weight(store, node) > 0
    else:
        assert spec.get_weight(store, spec.hash_tree_root(block)) > 0

    # Ensure that boost is removed after slot is over
    time = (
        store.genesis_time
        + block.slot * spec.config.SECONDS_PER_SLOT
        + spec.config.SECONDS_PER_SLOT
    )
    on_tick_and_append_step(spec, store, time, test_steps)
    assert store.proposer_boost_root == spec.Root()
    if is_post_eip7732(spec):
        node = spec.ForkChoiceNode(
            root=spec.hash_tree_root(block),
            payload_status=spec.PAYLOAD_STATUS_PENDING,
        )
        assert spec.get_weight(store, node) == 0
    else:
        assert spec.get_weight(store, spec.hash_tree_root(block)) == 0

    next_slots(spec, state, 3)
    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block)

    # Process block on timely arrival at start of boost interval
    time = store.genesis_time + block.slot * spec.config.SECONDS_PER_SLOT
    on_tick_and_append_step(spec, store, time, test_steps)
    yield from add_block(spec, store, signed_block, test_steps)
    payload_state_transition(spec, store, signed_block.message)
    assert store.proposer_boost_root == spec.hash_tree_root(block)
    if is_post_eip7732(spec):
        node = spec.ForkChoiceNode(
            root=spec.hash_tree_root(block),
            payload_status=spec.PAYLOAD_STATUS_PENDING,
        )
        assert spec.get_weight(store, node) > 0
    else:
        assert spec.get_weight(store, spec.hash_tree_root(block)) > 0

    # Ensure that boost is removed after slot is over
    time = (
        store.genesis_time
        + block.slot * spec.config.SECONDS_PER_SLOT
        + spec.config.SECONDS_PER_SLOT
    )
    on_tick_and_append_step(spec, store, time, test_steps)
    assert store.proposer_boost_root == spec.Root()
    if is_post_eip7732(spec):
        node = spec.ForkChoiceNode(
            root=spec.hash_tree_root(block),
            payload_status=spec.PAYLOAD_STATUS_PENDING,
        )
        assert spec.get_weight(store, node) == 0
    else:
        assert spec.get_weight(store, spec.hash_tree_root(block)) == 0

    test_steps.append(
        {
            "checks": {
                "proposer_boost_root": encode_hex(store.proposer_boost_root),
            }
        }
    )

    yield "steps", test_steps


@with_altair_and_later
@spec_state_test
def test_proposer_boost_root_same_slot_untimely_block(spec, state):
    test_steps = []
    genesis_state = state.copy()

    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block

    # Build block that serves as head ONLY on timely arrival, and ONLY in that slot
    state = genesis_state.copy()
    next_slots(spec, state, 3)
    block = build_empty_block_for_next_slot(spec, state)
    signed_block = state_transition_and_sign_block(spec, state, block)

    # Process block on untimely arrival in the same slot
    # Round up to nearest second
    if is_post_eip7732(spec):
        late_block_cutoff_ms = spec.get_slot_component_duration_ms(
            spec.config.ATTESTATION_DUE_BPS_EIP7732
        )
    else:
        late_block_cutoff_ms = spec.get_slot_component_duration_ms(spec.config.ATTESTATION_DUE_BPS)
    late_block_cutoff = (late_block_cutoff_ms + 999) // 1000
    time = store.genesis_time + block.slot * spec.config.SECONDS_PER_SLOT + late_block_cutoff

    on_tick_and_append_step(spec, store, time, test_steps)
    yield from add_block(spec, store, signed_block, test_steps)
    payload_state_transition(spec, store, signed_block.message)

    assert store.proposer_boost_root == spec.Root()

    test_steps.append(
        {
            "checks": {
                "proposer_boost_root": encode_hex(store.proposer_boost_root),
            }
        }
    )

    yield "steps", test_steps


@with_altair_and_later
@spec_state_test
def test_proposer_boost_is_first_block(spec, state):
    test_steps = []
    genesis_state = state.copy()

    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block

    # Build block that serves as head ONLY on timely arrival, and ONLY in that slot
    state = genesis_state.copy()
    next_slots(spec, state, 3)
    pre_state = state.copy()
    block_a = build_empty_block_for_next_slot(spec, state)
    signed_block_a = state_transition_and_sign_block(spec, state, block_a)

    # Process block on timely arrival just before end of boost interval
    # Round up to nearest second
    if is_post_eip7732(spec):
        late_block_cutoff_ms = spec.get_slot_component_duration_ms(
            spec.config.ATTESTATION_DUE_BPS_EIP7732
        )
    else:
        late_block_cutoff_ms = spec.get_slot_component_duration_ms(spec.config.ATTESTATION_DUE_BPS)
    late_block_cutoff = (late_block_cutoff_ms + 999) // 1000
    time = store.genesis_time + block_a.slot * spec.config.SECONDS_PER_SLOT + late_block_cutoff - 1

    on_tick_and_append_step(spec, store, time, test_steps)
    yield from add_block(spec, store, signed_block_a, test_steps)
    payload_state_transition(spec, store, signed_block_a.message)
    # `proposer_boost_root` is now `block_a`
    assert store.proposer_boost_root == spec.hash_tree_root(block_a)
    if is_post_eip7732(spec):
        node = spec.ForkChoiceNode(
            root=spec.hash_tree_root(block_a),
            payload_status=spec.PAYLOAD_STATUS_PENDING,
        )
        assert spec.get_weight(store, node) > 0
    else:
        assert spec.get_weight(store, spec.hash_tree_root(block_a)) > 0
    test_steps.append(
        {
            "checks": {
                "proposer_boost_root": encode_hex(store.proposer_boost_root),
            }
        }
    )

    # make a different block at the same slot
    state = pre_state.copy()
    block_b = block_a.copy()
    block_b.body.graffiti = b"\x34" * 32
    signed_block_b = state_transition_and_sign_block(spec, state, block_b)
    yield from add_block(spec, store, signed_block_b, test_steps)
    payload_state_transition(spec, store, signed_block_b.message)
    # `proposer_boost_root` is still `block_a`
    assert store.proposer_boost_root == spec.hash_tree_root(block_a)
    if is_post_eip7732(spec):
        node = spec.ForkChoiceNode(
            root=spec.hash_tree_root(block_b),
            payload_status=spec.PAYLOAD_STATUS_PENDING,
        )
        assert spec.get_weight(store, node) == 0
    else:
        assert spec.get_weight(store, spec.hash_tree_root(block_b)) == 0
    test_steps.append(
        {
            "checks": {
                "proposer_boost_root": encode_hex(store.proposer_boost_root),
            }
        }
    )

    yield "steps", test_steps


@with_altair_and_later
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_justification_withholding(spec, state):
    test_steps = []
    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    assert store.time == current_time

    for _ in range(2):
        next_epoch(spec, state)

    for _ in range(2):
        state, store, _ = yield from apply_next_epoch_with_attestations(
            spec, state, store, True, True, test_steps=test_steps
        )

    assert state.finalized_checkpoint.epoch == store.finalized_checkpoint.epoch == 2
    assert state.current_justified_checkpoint.epoch == store.justified_checkpoint.epoch == 3
    assert spec.get_current_epoch(state) == 4

    # ------------

    # Create attacker's fork that can justify epoch 4
    # Do not apply attacker's blocks to store
    attacker_state = state.copy()
    attacker_signed_blocks = []

    while not is_ready_to_justify(spec, attacker_state):
        attacker_state, signed_blocks, attacker_state = next_slots_with_attestations(
            spec, attacker_state, 1, True, False
        )
        attacker_signed_blocks += signed_blocks

    assert attacker_state.finalized_checkpoint.epoch == 2
    assert attacker_state.current_justified_checkpoint.epoch == 3
    assert spec.get_current_epoch(attacker_state) == 4

    # ------------

    # The honest fork sees all except the last block from attacker_signed_blocks
    # Apply honest fork to store
    honest_signed_blocks = attacker_signed_blocks[:-1]
    assert len(honest_signed_blocks) > 0

    for signed_block in honest_signed_blocks:
        yield from tick_and_add_block(spec, store, signed_block, test_steps)
        payload_state_transition(spec, store, signed_block.message)

    last_honest_block = honest_signed_blocks[-1].message
    honest_state = get_store_full_state(spec, store, hash_tree_root(last_honest_block)).copy()

    assert honest_state.finalized_checkpoint.epoch == store.finalized_checkpoint.epoch == 2
    assert honest_state.current_justified_checkpoint.epoch == store.justified_checkpoint.epoch == 3
    assert spec.get_current_epoch(honest_state) == 4

    # Create & apply an honest block in epoch 5 that can justify epoch 4
    next_epoch(spec, honest_state)
    assert spec.get_current_epoch(honest_state) == 5

    honest_block = build_empty_block_for_next_slot(spec, honest_state)
    honest_block.body.attestations = attacker_signed_blocks[-1].message.body.attestations
    signed_block = state_transition_and_sign_block(spec, honest_state, honest_block)
    yield from tick_and_add_block(spec, store, signed_block, test_steps)
    payload_state_transition(spec, store, signed_block.message)
    assert state.finalized_checkpoint.epoch == store.finalized_checkpoint.epoch == 2
    assert state.current_justified_checkpoint.epoch == store.justified_checkpoint.epoch == 3
    check_head_against_root(spec, store, hash_tree_root(honest_block))
    assert is_ready_to_justify(spec, honest_state)

    # ------------

    # When the attacker's block is received, the honest block is still the head
    # This relies on the honest block's LMD score increasing due to proposer boost
    yield from tick_and_add_block(spec, store, attacker_signed_blocks[-1], test_steps)
    payload_state_transition(spec, store, attacker_signed_blocks[-1].message)
    assert store.finalized_checkpoint.epoch == 3
    assert store.justified_checkpoint.epoch == 4
    check_head_against_root(spec, store, hash_tree_root(honest_block))

    yield "steps", test_steps


@with_altair_and_later
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_justification_withholding_reverse_order(spec, state):
    test_steps = []
    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield "anchor_state", state
    yield "anchor_block", anchor_block
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    assert store.time == current_time

    for _ in range(2):
        next_epoch(spec, state)

    for _ in range(2):
        state, store, _ = yield from apply_next_epoch_with_attestations(
            spec, state, store, True, True, test_steps=test_steps
        )

    assert state.finalized_checkpoint.epoch == store.finalized_checkpoint.epoch == 2
    assert state.current_justified_checkpoint.epoch == store.justified_checkpoint.epoch == 3
    assert spec.get_current_epoch(state) == 4

    # ------------

    # Create attacker's fork that can justify epoch 4
    attacker_state = state.copy()
    attacker_signed_blocks = []

    while not is_ready_to_justify(spec, attacker_state):
        attacker_state, signed_blocks, attacker_state = next_slots_with_attestations(
            spec, attacker_state, 1, True, False
        )
        assert len(signed_blocks) == 1
        attacker_signed_blocks += signed_blocks
        yield from tick_and_add_block(spec, store, signed_blocks[0], test_steps)
        payload_state_transition(spec, store, signed_blocks[0].message)

    assert attacker_state.finalized_checkpoint.epoch == 2
    assert attacker_state.current_justified_checkpoint.epoch == 3
    assert spec.get_current_epoch(attacker_state) == 4
    attackers_head = hash_tree_root(attacker_signed_blocks[-1].message)
    check_head_against_root(spec, store, attackers_head)

    # ------------

    # The honest fork sees all except the last block from attacker_signed_blocks
    honest_signed_blocks = attacker_signed_blocks[:-1]
    assert len(honest_signed_blocks) > 0

    last_honest_block = honest_signed_blocks[-1].message
    honest_state = get_store_full_state(spec, store, hash_tree_root(last_honest_block)).copy()

    assert honest_state.finalized_checkpoint.epoch == store.finalized_checkpoint.epoch == 2
    assert honest_state.current_justified_checkpoint.epoch == store.justified_checkpoint.epoch == 3
    assert spec.get_current_epoch(honest_state) == 4

    # Create an honest block in epoch 5 that can justify epoch 4
    next_epoch(spec, honest_state)
    assert spec.get_current_epoch(honest_state) == 5

    honest_block = build_empty_block_for_next_slot(spec, honest_state)
    honest_block.body.attestations = attacker_signed_blocks[-1].message.body.attestations
    signed_block = state_transition_and_sign_block(spec, honest_state, honest_block)
    assert honest_state.finalized_checkpoint.epoch == store.finalized_checkpoint.epoch == 2
    assert honest_state.current_justified_checkpoint.epoch == store.justified_checkpoint.epoch == 3
    assert is_ready_to_justify(spec, honest_state)

    # When the honest block is received, the honest block becomes the head
    # This relies on the honest block's LMD score increasing due to proposer boost
    yield from tick_and_add_block(spec, store, signed_block, test_steps)
    payload_state_transition(spec, store, signed_block.message)
    assert store.finalized_checkpoint.epoch == 3
    assert store.justified_checkpoint.epoch == 4
    check_head_against_root(spec, store, hash_tree_root(honest_block))

    yield "steps", test_steps


@with_altair_and_later
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_justification_update_beginning_of_epoch(spec, state):
    """
    Check that the store's justified checkpoint is updated when a block containing better justification is
    revealed at the first slot of an epoch
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
        spec, store, store.genesis_time + state.slot * spec.config.SECONDS_PER_SLOT, test_steps
    )

    # Fill epoch 1 to 3
    for _ in range(3):
        state, store, _ = yield from apply_next_epoch_with_attestations(
            spec, state, store, True, True, test_steps=test_steps
        )

    assert spec.compute_epoch_at_slot(spec.get_current_slot(store)) == 4
    assert state.current_justified_checkpoint.epoch == store.justified_checkpoint.epoch == 3

    # Create a block that has new justification information contained within it, but don't add to store yet
    another_state = state.copy()
    _, signed_blocks, another_state = next_epoch_with_attestations(spec, another_state, True, False)
    assert spec.compute_epoch_at_slot(another_state.slot) == 5
    assert another_state.current_justified_checkpoint.epoch == 4

    # Tick store to the start of the next epoch
    slot = spec.get_current_slot(store) + spec.SLOTS_PER_EPOCH - (state.slot % spec.SLOTS_PER_EPOCH)
    current_time = slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    assert spec.compute_epoch_at_slot(spec.get_current_slot(store)) == 5

    # Now add the blocks & check that justification update was triggered
    for signed_block in signed_blocks:
        yield from tick_and_add_block(spec, store, signed_block, test_steps)
        payload_state_transition(spec, store, signed_block.message)
        check_head_against_root(spec, store, signed_block.message.hash_tree_root())
    assert store.justified_checkpoint.epoch == 4

    yield "steps", test_steps


@with_altair_and_later
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_justification_update_end_of_epoch(spec, state):
    """
    Check that the store's justified checkpoint is updated when a block containing better justification is
    revealed at the last slot of an epoch
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
        spec, store, store.genesis_time + state.slot * spec.config.SECONDS_PER_SLOT, test_steps
    )

    # Fill epoch 1 to 3
    for _ in range(3):
        state, store, _ = yield from apply_next_epoch_with_attestations(
            spec, state, store, True, True, test_steps=test_steps
        )

    assert spec.compute_epoch_at_slot(spec.get_current_slot(store)) == 4
    assert state.current_justified_checkpoint.epoch == store.justified_checkpoint.epoch == 3

    # Create a block that has new justification information contained within it, but don't add to store yet
    another_state = state.copy()
    _, signed_blocks, another_state = next_epoch_with_attestations(spec, another_state, True, False)
    assert spec.compute_epoch_at_slot(another_state.slot) == 5
    assert another_state.current_justified_checkpoint.epoch == 4

    # Tick store to the last slot of the next epoch
    slot = spec.get_current_slot(store) + spec.SLOTS_PER_EPOCH - (state.slot % spec.SLOTS_PER_EPOCH)
    slot = slot + spec.SLOTS_PER_EPOCH - 1
    current_time = slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    assert spec.compute_epoch_at_slot(spec.get_current_slot(store)) == 5

    # Now add the blocks & check that justification update was triggered
    for signed_block in signed_blocks:
        yield from tick_and_add_block(spec, store, signed_block, test_steps)
        check_head_against_root(spec, store, signed_block.message.hash_tree_root())
        payload_state_transition(spec, store, signed_block.message)
    assert store.justified_checkpoint.epoch == 4
    yield "steps", test_steps


@with_altair_and_later
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_incompatible_justification_update_start_of_epoch(spec, state):
    """
    Check that the store's justified checkpoint is updated when a block containing better justification is
    revealed at the start slot of an epoch, even when the better justified checkpoint is not a descendant of
    the store's justified checkpoint
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
        spec, store, store.genesis_time + state.slot * spec.config.SECONDS_PER_SLOT, test_steps
    )

    # Fill epoch 1 to 3
    for _ in range(3):
        state, store, _ = yield from apply_next_epoch_with_attestations(
            spec, state, store, True, True, test_steps=test_steps
        )

    assert spec.compute_epoch_at_slot(spec.get_current_slot(store)) == 4
    assert state.current_justified_checkpoint.epoch == store.justified_checkpoint.epoch == 3
    assert state.finalized_checkpoint.epoch == store.finalized_checkpoint.epoch == 2

    # Copy the state to create a fork later
    another_state = state.copy()

    # Fill epoch 4 and 5
    for _ in range(2):
        state, store, _ = yield from apply_next_epoch_with_attestations(
            spec, state, store, True, True, test_steps=test_steps
        )

    assert spec.compute_epoch_at_slot(spec.get_current_slot(store)) == 6
    assert state.current_justified_checkpoint.epoch == store.justified_checkpoint.epoch == 5
    assert state.finalized_checkpoint.epoch == store.finalized_checkpoint.epoch == 4

    # Create a block that has new justification information contained within it, but don't add to store yet
    next_epoch(spec, another_state)
    signed_blocks = []
    _, signed_blocks_temp, another_state = next_epoch_with_attestations(
        spec, another_state, False, False
    )
    signed_blocks += signed_blocks_temp
    assert spec.compute_epoch_at_slot(another_state.slot) == 6
    assert another_state.current_justified_checkpoint.epoch == 3
    assert another_state.finalized_checkpoint.epoch == 2
    _, signed_blocks_temp, another_state = next_epoch_with_attestations(
        spec, another_state, True, False
    )
    signed_blocks += signed_blocks_temp
    assert spec.compute_epoch_at_slot(another_state.slot) == 7
    assert another_state.current_justified_checkpoint.epoch == 6
    assert another_state.finalized_checkpoint.epoch == 2
    last_block_root = another_state.latest_block_header.parent_root

    # Tick store to the last slot of the next epoch
    slot = another_state.slot + spec.SLOTS_PER_EPOCH - (state.slot % spec.SLOTS_PER_EPOCH)
    current_time = slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    assert spec.compute_epoch_at_slot(spec.get_current_slot(store)) == 8

    # Now add the blocks & check that justification update was triggered
    for signed_block in signed_blocks:
        yield from tick_and_add_block(spec, store, signed_block, test_steps)
        payload_state_transition(spec, store, signed_block.message)
    finalized_checkpoint_block = spec.get_checkpoint_block(
        store,
        last_block_root,
        state.finalized_checkpoint.epoch,
    )
    assert finalized_checkpoint_block == state.finalized_checkpoint.root
    justified_checkpoint_block = spec.get_checkpoint_block(
        store,
        last_block_root,
        state.current_justified_checkpoint.epoch,
    )
    assert justified_checkpoint_block != state.current_justified_checkpoint.root
    assert store.finalized_checkpoint.epoch == 4
    assert store.justified_checkpoint.epoch == 6

    yield "steps", test_steps


@with_altair_and_later
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_incompatible_justification_update_end_of_epoch(spec, state):
    """
    Check that the store's justified checkpoint is updated when a block containing better justification is
    revealed at the last slot of an epoch, even when the better justified checkpoint is not a descendant of
    the store's justified checkpoint
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
        spec, store, store.genesis_time + state.slot * spec.config.SECONDS_PER_SLOT, test_steps
    )

    # Fill epoch 1 to 3
    for _ in range(3):
        state, store, _ = yield from apply_next_epoch_with_attestations(
            spec, state, store, True, True, test_steps=test_steps
        )

    assert spec.compute_epoch_at_slot(spec.get_current_slot(store)) == 4
    assert state.current_justified_checkpoint.epoch == store.justified_checkpoint.epoch == 3
    assert state.finalized_checkpoint.epoch == store.finalized_checkpoint.epoch == 2

    # Copy the state to create a fork later
    another_state = state.copy()

    # Fill epoch 4 and 5
    for _ in range(2):
        state, store, _ = yield from apply_next_epoch_with_attestations(
            spec, state, store, True, True, test_steps=test_steps
        )

    assert spec.compute_epoch_at_slot(spec.get_current_slot(store)) == 6
    assert state.current_justified_checkpoint.epoch == store.justified_checkpoint.epoch == 5
    assert state.finalized_checkpoint.epoch == store.finalized_checkpoint.epoch == 4

    # Create a block that has new justification information contained within it, but don't add to store yet
    next_epoch(spec, another_state)
    signed_blocks = []
    _, signed_blocks_temp, another_state = next_epoch_with_attestations(
        spec, another_state, False, False
    )
    signed_blocks += signed_blocks_temp
    assert spec.compute_epoch_at_slot(another_state.slot) == 6
    assert another_state.current_justified_checkpoint.epoch == 3
    assert another_state.finalized_checkpoint.epoch == 2
    _, signed_blocks_temp, another_state = next_epoch_with_attestations(
        spec, another_state, True, False
    )
    signed_blocks += signed_blocks_temp
    assert spec.compute_epoch_at_slot(another_state.slot) == 7
    assert another_state.current_justified_checkpoint.epoch == 6
    assert another_state.finalized_checkpoint.epoch == 2
    last_block_root = another_state.latest_block_header.parent_root

    # Tick store to the last slot of the next epoch
    slot = another_state.slot + spec.SLOTS_PER_EPOCH - (state.slot % spec.SLOTS_PER_EPOCH)
    slot = slot + spec.SLOTS_PER_EPOCH - 1
    current_time = slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    assert spec.compute_epoch_at_slot(spec.get_current_slot(store)) == 8

    # Now add the blocks & check that justification update was triggered
    for signed_block in signed_blocks:
        yield from tick_and_add_block(spec, store, signed_block, test_steps)
        payload_state_transition(spec, store, signed_block.message)
    finalized_checkpoint_block = spec.get_checkpoint_block(
        store,
        last_block_root,
        state.finalized_checkpoint.epoch,
    )
    assert finalized_checkpoint_block == state.finalized_checkpoint.root
    justified_checkpoint_block = spec.get_checkpoint_block(
        store,
        last_block_root,
        state.current_justified_checkpoint.epoch,
    )
    assert justified_checkpoint_block != state.current_justified_checkpoint.root
    assert store.finalized_checkpoint.epoch == 4
    assert store.justified_checkpoint.epoch == 6

    yield "steps", test_steps


@with_altair_and_later
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_justified_update_not_realized_finality(spec, state):
    """
    Check that the store updates its justified checkpoint if a higher justified checkpoint is found that is
    a descendant of the finalized checkpoint, but does not know about the finality
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
        spec, store, store.genesis_time + state.slot * spec.config.SECONDS_PER_SLOT, test_steps
    )

    # Fill epoch 1 to 3
    for _ in range(3):
        state, store, _ = yield from apply_next_epoch_with_attestations(
            spec, state, store, True, True, test_steps=test_steps
        )

    assert spec.compute_epoch_at_slot(spec.get_current_slot(store)) == 4
    assert state.current_justified_checkpoint.epoch == store.justified_checkpoint.epoch == 3

    # We'll make the current head block the finalized block
    if is_post_eip7732(spec):
        finalized_root = spec.get_head(store).root
    else:
        finalized_root = spec.get_head(store)
    finalized_block = store.blocks[finalized_root]
    assert spec.compute_epoch_at_slot(finalized_block.slot) == 4
    check_head_against_root(spec, store, finalized_root)
    # Copy the post-state to use later
    another_state = state.copy()

    # Create a fork that finalizes our block
    for _ in range(2):
        state, store, _ = yield from apply_next_epoch_with_attestations(
            spec, state, store, True, True, test_steps=test_steps
        )
    assert spec.compute_epoch_at_slot(spec.get_current_slot(store)) == 6
    assert state.current_justified_checkpoint.epoch == store.justified_checkpoint.epoch == 5
    assert state.finalized_checkpoint.epoch == store.finalized_checkpoint.epoch == 4
    assert state.finalized_checkpoint.root == store.finalized_checkpoint.root == finalized_root

    # Create a fork for a better justification that is a descendant of the finalized block,
    # but does not realize the finality.
    # Do not add these blocks to the store yet
    next_epoch(spec, another_state)
    signed_blocks = []
    _, signed_blocks_temp, another_state = next_epoch_with_attestations(
        spec, another_state, False, False
    )
    signed_blocks += signed_blocks_temp
    assert spec.compute_epoch_at_slot(another_state.slot) == 6
    assert another_state.current_justified_checkpoint.epoch == 3
    assert another_state.finalized_checkpoint.epoch == 2
    _, signed_blocks_temp, another_state = next_epoch_with_attestations(
        spec, another_state, True, False
    )
    signed_blocks += signed_blocks_temp
    assert spec.compute_epoch_at_slot(another_state.slot) == 7
    assert another_state.current_justified_checkpoint.epoch == 6

    # Now add the blocks & check that justification update was triggered
    for signed_block in signed_blocks:
        yield from tick_and_add_block(spec, store, signed_block, test_steps)
        payload_state_transition(spec, store, signed_block.message)
    assert store.justified_checkpoint.epoch == 6
    assert store.finalized_checkpoint.epoch == 4
    last_block = signed_blocks[-1]
    last_block_root = last_block.message.hash_tree_root()
    ancestor_at_finalized_slot = spec.get_ancestor(store, last_block_root, finalized_block.slot)
    if is_post_eip7732(spec):
        ancestor_at_finalized_slot = ancestor_at_finalized_slot.root

    assert ancestor_at_finalized_slot == store.finalized_checkpoint.root

    yield "steps", test_steps


@with_altair_and_later
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_justified_update_monotonic(spec, state):
    """
    Check that the store does not update it's justified checkpoint with lower justified checkpoints.
    This testcase checks that the store's justified checkpoint remains the same even when we input a block that has:
    - a higher finalized checkpoint than the store's finalized checkpoint, and
    - a lower justified checkpoint than the store's justified checkpoint
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
        spec, store, store.genesis_time + state.slot * spec.config.SECONDS_PER_SLOT, test_steps
    )

    # Fill epoch 1 to 3
    for _ in range(3):
        state, store, _ = yield from apply_next_epoch_with_attestations(
            spec, state, store, True, True, test_steps=test_steps
        )

    assert spec.compute_epoch_at_slot(spec.get_current_slot(store)) == 4
    assert state.current_justified_checkpoint.epoch == store.justified_checkpoint.epoch == 3
    assert store.finalized_checkpoint.epoch == 2

    # We'll eventually make the current head block the finalized block
    if is_post_eip7732(spec):
        finalized_root = spec.get_head(store).root
    else:
        finalized_root = spec.get_head(store)
    finalized_block = store.blocks[finalized_root]
    assert spec.compute_epoch_at_slot(finalized_block.slot) == 4
    check_head_against_root(spec, store, finalized_root)
    # Copy into another variable so we can use `state` later
    another_state = state.copy()

    # Create a fork with justification that is a descendant of the finalized block
    # Do not add these blocks to the store yet
    next_epoch(spec, another_state)
    signed_blocks = []
    _, signed_blocks_temp, another_state = next_epoch_with_attestations(
        spec, another_state, False, False
    )
    signed_blocks += signed_blocks_temp
    assert spec.compute_epoch_at_slot(another_state.slot) == 6
    assert another_state.current_justified_checkpoint.epoch == 3
    assert another_state.finalized_checkpoint.epoch == 2
    _, signed_blocks_temp, another_state = next_epoch_with_attestations(
        spec, another_state, True, False
    )
    signed_blocks += signed_blocks_temp
    assert spec.compute_epoch_at_slot(another_state.slot) == 7
    assert another_state.current_justified_checkpoint.epoch == 6
    assert another_state.finalized_checkpoint.epoch == 2

    # Now add the blocks & check that justification update was triggered
    for signed_block in signed_blocks:
        yield from tick_and_add_block(spec, store, signed_block, test_steps)
        payload_state_transition(spec, store, signed_block.message)
    assert spec.compute_epoch_at_slot(spec.get_current_slot(store)) == 7
    assert store.justified_checkpoint.epoch == 6
    assert store.finalized_checkpoint.epoch == 2
    last_block = signed_blocks[-1]
    last_block_root = last_block.message.hash_tree_root()
    ancestor_at_finalized_slot = spec.get_ancestor(store, last_block_root, finalized_block.slot)
    if is_post_eip7732(spec):
        ancestor_at_finalized_slot = ancestor_at_finalized_slot.root
    assert ancestor_at_finalized_slot == finalized_root

    # Create a fork with lower justification that also finalizes our chosen block
    for _ in range(2):
        state, store, _ = yield from apply_next_epoch_with_attestations(
            spec, state, store, True, True, test_steps=test_steps
        )
    assert spec.compute_epoch_at_slot(spec.get_current_slot(store)) == 7
    assert state.current_justified_checkpoint.epoch == 5
    # Check that store's finalized checkpoint is updated
    assert state.finalized_checkpoint.epoch == store.finalized_checkpoint.epoch == 4
    # Check that store's justified checkpoint is not updated
    assert store.justified_checkpoint.epoch == 6

    yield "steps", test_steps


@with_altair_and_later
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_justified_update_always_if_better(spec, state):
    """
    Check that the store updates it's justified checkpoint with any higher justified checkpoint.
    This testcase checks that the store's justified checkpoint is updated when we input a block that has:
    - a lower finalized checkpoint than the store's finalized checkpoint, and
    - a higher justified checkpoint than the store's justified checkpoint
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
        spec, store, store.genesis_time + state.slot * spec.config.SECONDS_PER_SLOT, test_steps
    )

    # Fill epoch 1 to 3
    for _ in range(3):
        state, store, _ = yield from apply_next_epoch_with_attestations(
            spec, state, store, True, True, test_steps=test_steps
        )

    assert spec.compute_epoch_at_slot(spec.get_current_slot(store)) == 4
    assert state.current_justified_checkpoint.epoch == store.justified_checkpoint.epoch == 3
    assert store.finalized_checkpoint.epoch == 2

    # We'll eventually make the current head block the finalized block
    if is_post_eip7732(spec):
        finalized_root = spec.get_head(store).root
    else:
        finalized_root = spec.get_head(store)
    finalized_block = store.blocks[finalized_root]
    assert spec.compute_epoch_at_slot(finalized_block.slot) == 4
    check_head_against_root(spec, store, finalized_root)
    # Copy into another variable to use later
    another_state = state.copy()

    # Create a fork with lower justification that also finalizes our chosen block
    for _ in range(2):
        state, store, _ = yield from apply_next_epoch_with_attestations(
            spec, state, store, True, True, test_steps=test_steps
        )
    assert spec.compute_epoch_at_slot(spec.get_current_slot(store)) == 6
    assert state.current_justified_checkpoint.epoch == store.justified_checkpoint.epoch == 5
    assert state.finalized_checkpoint.epoch == store.finalized_checkpoint.epoch == 4

    # Create a fork with higher justification that is a descendant of the finalized block
    # Do not add these blocks to the store yet
    next_epoch(spec, another_state)
    signed_blocks = []
    _, signed_blocks_temp, another_state = next_epoch_with_attestations(
        spec, another_state, False, False
    )
    signed_blocks += signed_blocks_temp
    assert spec.compute_epoch_at_slot(another_state.slot) == 6
    assert another_state.current_justified_checkpoint.epoch == 3
    assert another_state.finalized_checkpoint.epoch == 2
    _, signed_blocks_temp, another_state = next_epoch_with_attestations(
        spec, another_state, True, False
    )
    signed_blocks += signed_blocks_temp
    assert spec.compute_epoch_at_slot(another_state.slot) == 7
    assert another_state.current_justified_checkpoint.epoch == 6
    assert another_state.finalized_checkpoint.epoch == 2

    # Now add the blocks & check that justification update was triggered
    for signed_block in signed_blocks:
        yield from tick_and_add_block(spec, store, signed_block, test_steps)
        payload_state_transition(spec, store, signed_block.message)
    assert spec.compute_epoch_at_slot(spec.get_current_slot(store)) == 7
    assert store.justified_checkpoint.epoch == 6
    assert store.finalized_checkpoint.epoch == 4

    yield "steps", test_steps


@with_altair_and_later
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_pull_up_past_epoch_block(spec, state):
    """
    Check that the store pulls-up a block from the past epoch to realize it's justification & finalization information
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
        spec, store, store.genesis_time + state.slot * spec.config.SECONDS_PER_SLOT, test_steps
    )

    # Fill epoch 1 to 3
    for _ in range(3):
        state, store, _ = yield from apply_next_epoch_with_attestations(
            spec, state, store, True, True, test_steps=test_steps
        )

    assert spec.compute_epoch_at_slot(spec.get_current_slot(store)) == 4
    assert state.current_justified_checkpoint.epoch == store.justified_checkpoint.epoch == 3
    assert store.finalized_checkpoint.epoch == 2

    # Create a chain within epoch 4 that contains a justification for epoch 4
    signed_blocks, justifying_slot = find_next_justifying_slot(spec, state, True, True)
    assert spec.compute_epoch_at_slot(justifying_slot) == spec.get_current_epoch(state) == 4

    # Tick store to the next epoch
    next_epoch(spec, state)
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    assert spec.compute_epoch_at_slot(spec.get_current_slot(store)) == 5
    assert state.current_justified_checkpoint.epoch == store.justified_checkpoint.epoch == 3
    assert store.finalized_checkpoint.epoch == 2

    # Add the previously created chain to the store and check for updates
    for signed_block in signed_blocks:
        yield from tick_and_add_block(spec, store, signed_block, test_steps)
        check_head_against_root(spec, store, signed_block.message.hash_tree_root())
        payload_state_transition(spec, store, signed_block.message)
    assert spec.compute_epoch_at_slot(spec.get_current_slot(store)) == 5
    assert store.justified_checkpoint.epoch == 4
    assert store.finalized_checkpoint.epoch == 3

    yield "steps", test_steps


@with_altair_and_later
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_not_pull_up_current_epoch_block(spec, state):
    """
    Check that the store does not pull-up a block from the current epoch if the previous epoch is not justified
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
        spec, store, store.genesis_time + state.slot * spec.config.SECONDS_PER_SLOT, test_steps
    )

    # Fill epoch 1 to 3
    for _ in range(3):
        state, store, _ = yield from apply_next_epoch_with_attestations(
            spec, state, store, True, True, test_steps=test_steps
        )

    assert spec.compute_epoch_at_slot(spec.get_current_slot(store)) == 4
    assert state.current_justified_checkpoint.epoch == store.justified_checkpoint.epoch == 3
    assert store.finalized_checkpoint.epoch == 2

    # Skip to the next epoch
    next_epoch(spec, state)
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    assert spec.compute_epoch_at_slot(state.slot) == 5

    # Create a chain within epoch 5 that contains a justification for epoch 5
    signed_blocks, justifying_slot = find_next_justifying_slot(spec, state, True, True)
    assert spec.compute_epoch_at_slot(justifying_slot) == spec.get_current_epoch(state) == 5

    # Add the previously created chain to the store and check that store does not apply pull-up updates
    for signed_block in signed_blocks:
        yield from tick_and_add_block(spec, store, signed_block, test_steps)
        check_head_against_root(spec, store, signed_block.message.hash_tree_root())
        payload_state_transition(spec, store, signed_block.message)
    assert spec.compute_epoch_at_slot(spec.get_current_slot(store)) == 5
    assert store.justified_checkpoint.epoch == 3
    assert store.finalized_checkpoint.epoch == 2

    yield "steps", test_steps


@with_altair_and_later
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_pull_up_on_tick(spec, state):
    """
    Check that the store pulls-up current epoch tips on the on_tick transition to the next epoch
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
        spec, store, store.genesis_time + state.slot * spec.config.SECONDS_PER_SLOT, test_steps
    )

    # Fill epoch 1 to 3
    for _ in range(3):
        state, store, _ = yield from apply_next_epoch_with_attestations(
            spec, state, store, True, True, test_steps=test_steps
        )

    assert spec.compute_epoch_at_slot(spec.get_current_slot(store)) == 4
    assert state.current_justified_checkpoint.epoch == store.justified_checkpoint.epoch == 3
    assert store.finalized_checkpoint.epoch == 2

    # Skip to the next epoch
    next_epoch(spec, state)
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    assert spec.compute_epoch_at_slot(state.slot) == 5

    # Create a chain within epoch 5 that contains a justification for epoch 5
    signed_blocks, justifying_slot = find_next_justifying_slot(spec, state, True, True)
    assert spec.compute_epoch_at_slot(justifying_slot) == spec.get_current_epoch(state) == 5

    # Add the previously created chain to the store and check that store does not apply pull-up updates,
    # since the previous epoch was not justified
    for signed_block in signed_blocks:
        yield from tick_and_add_block(spec, store, signed_block, test_steps)
        check_head_against_root(spec, store, signed_block.message.hash_tree_root())
        payload_state_transition(spec, store, signed_block.message)
    assert spec.compute_epoch_at_slot(spec.get_current_slot(store)) == 5
    assert store.justified_checkpoint.epoch == 3
    assert store.finalized_checkpoint.epoch == 2

    # Now tick the store to the next epoch and check that pull-up tip updates were applied
    next_epoch(spec, state)
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    assert spec.compute_epoch_at_slot(state.slot) == 6
    assert store.justified_checkpoint.epoch == 5
    # There's no new finality, so no finality updates expected
    assert store.finalized_checkpoint.epoch == 3

    yield "steps", test_steps
