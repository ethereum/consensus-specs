import random
from eth_utils import encode_hex

from eth2spec.test.context import (
    is_post_altair,
    spec_state_test,
    with_all_phases,
    with_presets,
)
from eth2spec.test.helpers.attestations import get_valid_attestation, next_epoch_with_attestations
from eth2spec.test.helpers.block import build_empty_block_for_next_slot
from eth2spec.test.helpers.constants import MINIMAL
from eth2spec.test.helpers.fork_choice import (
    tick_and_run_on_attestation,
    tick_and_add_block,
    get_anchor_root,
    get_genesis_forkchoice_store_and_block,
    get_formatted_head_output,
    on_tick_and_append_step,
    add_block,
)
from eth2spec.test.helpers.state import (
    next_slots,
    next_epoch,
    state_transition_and_sign_block,
)


rng = random.Random(1001)


@with_all_phases
@spec_state_test
def test_genesis(spec, state):
    test_steps = []
    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield 'anchor_state', state
    yield 'anchor_block', anchor_block

    anchor_root = get_anchor_root(spec, state)
    assert spec.get_head(store) == anchor_root
    test_steps.append({
        'checks': {
            'genesis_time': int(store.genesis_time),
            'head': get_formatted_head_output(spec, store),
        }
    })

    yield 'steps', test_steps

    if is_post_altair(spec):
        yield 'description', 'meta', f"Although it's not phase 0, we may use {spec.fork} spec to start testnets."


@with_all_phases
@spec_state_test
def test_chain_no_attestations(spec, state):
    test_steps = []
    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield 'anchor_state', state
    yield 'anchor_block', anchor_block

    anchor_root = get_anchor_root(spec, state)
    assert spec.get_head(store) == anchor_root
    test_steps.append({
        'checks': {
            'head': get_formatted_head_output(spec, store),
        }
    })

    # On receiving a block of `GENESIS_SLOT + 1` slot
    block_1 = build_empty_block_for_next_slot(spec, state)
    signed_block_1 = state_transition_and_sign_block(spec, state, block_1)
    yield from tick_and_add_block(spec, store, signed_block_1, test_steps)

    # On receiving a block of next epoch
    block_2 = build_empty_block_for_next_slot(spec, state)
    signed_block_2 = state_transition_and_sign_block(spec, state, block_2)
    yield from tick_and_add_block(spec, store, signed_block_2, test_steps)

    assert spec.get_head(store) == spec.hash_tree_root(block_2)
    test_steps.append({
        'checks': {
            'head': get_formatted_head_output(spec, store),
        }
    })

    yield 'steps', test_steps


@with_all_phases
@spec_state_test
def test_split_tie_breaker_no_attestations(spec, state):
    test_steps = []
    genesis_state = state.copy()

    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield 'anchor_state', state
    yield 'anchor_block', anchor_block
    anchor_root = get_anchor_root(spec, state)
    assert spec.get_head(store) == anchor_root
    test_steps.append({
        'checks': {
            'head': get_formatted_head_output(spec, store),
        }
    })

    # Create block at slot 1
    block_1_state = genesis_state.copy()
    block_1 = build_empty_block_for_next_slot(spec, block_1_state)
    signed_block_1 = state_transition_and_sign_block(spec, block_1_state, block_1)

    # Create additional block at slot 1
    block_2_state = genesis_state.copy()
    block_2 = build_empty_block_for_next_slot(spec, block_2_state)
    block_2.body.graffiti = b'\x42' * 32
    signed_block_2 = state_transition_and_sign_block(spec, block_2_state, block_2)

    # Tick time past slot 1 so proposer score boost does not apply
    time = store.genesis_time + (block_2.slot + 1) * spec.config.SECONDS_PER_SLOT
    on_tick_and_append_step(spec, store, time, test_steps)

    yield from add_block(spec, store, signed_block_1, test_steps)
    yield from add_block(spec, store, signed_block_2, test_steps)

    highest_root = max(spec.hash_tree_root(block_1), spec.hash_tree_root(block_2))
    assert spec.get_head(store) == highest_root
    test_steps.append({
        'checks': {
            'head': get_formatted_head_output(spec, store),
        }
    })

    yield 'steps', test_steps


@with_all_phases
@spec_state_test
def test_shorter_chain_but_heavier_weight(spec, state):
    test_steps = []
    genesis_state = state.copy()

    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield 'anchor_state', state
    yield 'anchor_block', anchor_block
    anchor_root = get_anchor_root(spec, state)
    assert spec.get_head(store) == anchor_root
    test_steps.append({
        'checks': {
            'head': get_formatted_head_output(spec, store),
        }
    })

    # build longer tree
    long_state = genesis_state.copy()
    for _ in range(3):
        long_block = build_empty_block_for_next_slot(spec, long_state)
        signed_long_block = state_transition_and_sign_block(spec, long_state, long_block)
        yield from tick_and_add_block(spec, store, signed_long_block, test_steps)

    # build short tree
    short_state = genesis_state.copy()
    short_block = build_empty_block_for_next_slot(spec, short_state)
    short_block.body.graffiti = b'\x42' * 32
    signed_short_block = state_transition_and_sign_block(spec, short_state, short_block)
    yield from tick_and_add_block(spec, store, signed_short_block, test_steps)

    # Since the long chain has higher proposer_score at slot 1, the latest long block is the head
    assert spec.get_head(store) == spec.hash_tree_root(long_block)

    short_attestation = get_valid_attestation(spec, short_state, short_block.slot, signed=True)
    yield from tick_and_run_on_attestation(spec, store, short_attestation, test_steps)

    assert spec.get_head(store) == spec.hash_tree_root(short_block)
    test_steps.append({
        'checks': {
            'head': get_formatted_head_output(spec, store),
        }
    })

    yield 'steps', test_steps


@with_all_phases
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_filtered_block_tree(spec, state):
    test_steps = []
    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield 'anchor_state', state
    yield 'anchor_block', anchor_block
    anchor_root = get_anchor_root(spec, state)
    assert spec.get_head(store) == anchor_root
    test_steps.append({
        'checks': {
            'head': get_formatted_head_output(spec, store),
        }
    })

    # transition state past initial couple of epochs
    next_epoch(spec, state)
    next_epoch(spec, state)
    # fill in attestations for entire epoch, justifying the recent epoch
    prev_state, signed_blocks, state = next_epoch_with_attestations(spec, state, True, False)
    assert state.current_justified_checkpoint.epoch > prev_state.current_justified_checkpoint.epoch

    # tick time forward and add blocks and attestations to store
    current_time = state.slot * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)
    for signed_block in signed_blocks:
        yield from add_block(spec, store, signed_block, test_steps)

    assert store.justified_checkpoint == state.current_justified_checkpoint

    # the last block in the branch should be the head
    expected_head_root = spec.hash_tree_root(signed_blocks[-1].message)
    assert spec.get_head(store) == expected_head_root

    test_steps.append({
        'checks': {
            'head': get_formatted_head_output(spec, store),
            'justified_checkpoint_root': encode_hex(store.justified_checkpoint.root),
        }
    })

    #
    # create branch containing the justified block but not containing enough on
    # chain votes to justify that block
    #

    # build a chain without attestations off of previous justified block
    non_viable_state = store.block_states[store.justified_checkpoint.root].copy()

    # ensure that next wave of votes are for future epoch
    next_epoch(spec, non_viable_state)
    next_epoch(spec, non_viable_state)
    next_epoch(spec, non_viable_state)
    assert spec.get_current_epoch(non_viable_state) > store.justified_checkpoint.epoch

    # create rogue block that will be attested to in this non-viable branch
    rogue_block = build_empty_block_for_next_slot(spec, non_viable_state)
    signed_rogue_block = state_transition_and_sign_block(spec, non_viable_state, rogue_block)

    # create an epoch's worth of attestations for the rogue block
    next_epoch(spec, non_viable_state)
    attestations = []
    for i in range(spec.SLOTS_PER_EPOCH):
        slot = rogue_block.slot + i
        for index in range(spec.get_committee_count_per_slot(non_viable_state, spec.compute_epoch_at_slot(slot))):
            attestation = get_valid_attestation(spec, non_viable_state, slot, index, signed=True)
            attestations.append(attestation)

    # tick time forward to be able to include up to the latest attestation
    current_time = (attestations[-1].data.slot + 1) * spec.config.SECONDS_PER_SLOT + store.genesis_time
    on_tick_and_append_step(spec, store, current_time, test_steps)

    # include rogue block and associated attestations in the store
    yield from add_block(spec, store, signed_rogue_block, test_steps)

    for attestation in attestations:
        yield from tick_and_run_on_attestation(spec, store, attestation, test_steps)

    # ensure that get_head still returns the head from the previous branch
    assert spec.get_head(store) == expected_head_root
    test_steps.append({
        'checks': {
            'head': get_formatted_head_output(spec, store)
        }
    })

    yield 'steps', test_steps


@with_all_phases
@spec_state_test
def test_proposer_boost_correct_head(spec, state):
    test_steps = []
    genesis_state = state.copy()

    # Initialization
    store, anchor_block = get_genesis_forkchoice_store_and_block(spec, state)
    yield 'anchor_state', state
    yield 'anchor_block', anchor_block
    anchor_root = get_anchor_root(spec, state)
    assert spec.get_head(store) == anchor_root
    test_steps.append({
        'checks': {
            'head': get_formatted_head_output(spec, store),
        }
    })

    # Build block that serves as head ONLY on timely arrival, and ONLY in that slot
    state_1 = genesis_state.copy()
    next_slots(spec, state_1, 3)
    block_1 = build_empty_block_for_next_slot(spec, state_1)
    signed_block_1 = state_transition_and_sign_block(spec, state_1, block_1)

    # Build block that serves as current head, and remains the head after block_1.slot
    state_2 = genesis_state.copy()
    next_slots(spec, state_2, 2)
    block_2 = build_empty_block_for_next_slot(spec, state_2)
    signed_block_2 = state_transition_and_sign_block(spec, state_2.copy(), block_2)
    while spec.hash_tree_root(block_1) >= spec.hash_tree_root(block_2):
        block_2.body.graffiti = spec.Bytes32(hex(rng.getrandbits(8 * 32))[2:].zfill(64))
        signed_block_2 = state_transition_and_sign_block(spec, state_2.copy(), block_2)
    assert spec.hash_tree_root(block_1) < spec.hash_tree_root(block_2)

    # Tick to block_1 slot time
    time = store.genesis_time + block_1.slot * spec.config.SECONDS_PER_SLOT
    on_tick_and_append_step(spec, store, time, test_steps)

    # Process block_2
    yield from add_block(spec, store, signed_block_2, test_steps)
    assert store.proposer_boost_root == spec.Root()
    assert spec.get_head(store) == spec.hash_tree_root(block_2)

    # Process block_1 on timely arrival
    # The head should temporarily change to block_1
    yield from add_block(spec, store, signed_block_1, test_steps)
    assert store.proposer_boost_root == spec.hash_tree_root(block_1)
    assert spec.get_head(store) == spec.hash_tree_root(block_1)

    # After block_1.slot, the head should revert to block_2
    time = store.genesis_time + (block_1.slot + 1) * spec.config.SECONDS_PER_SLOT
    on_tick_and_append_step(spec, store, time, test_steps)
    assert store.proposer_boost_root == spec.Root()
    assert spec.get_head(store) == spec.hash_tree_root(block_2)

    test_steps.append({
        'checks': {
            'head': get_formatted_head_output(spec, store),
        }
    })

    yield 'steps', test_steps
