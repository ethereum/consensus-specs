from eth2spec.test.context import with_all_phases, spec_state_test
from eth2spec.test.helpers.attestations import get_valid_attestation, next_epoch_with_attestations
from eth2spec.test.helpers.block import build_empty_block_for_next_slot
from eth2spec.test.helpers.fork_choice import add_attestation_to_store, add_block_to_store, get_anchor_root
from eth2spec.test.helpers.state import (
    next_epoch,
    state_transition_and_sign_block,
)


@with_all_phases
@spec_state_test
def test_genesis(spec, state):
    # Initialization
    store = spec.get_forkchoice_store(state)
    anchor_root = get_anchor_root(spec, state)
    assert spec.get_head(store) == anchor_root


@with_all_phases
@spec_state_test
def test_chain_no_attestations(spec, state):
    # Initialization
    store = spec.get_forkchoice_store(state)
    anchor_root = get_anchor_root(spec, state)
    assert spec.get_head(store) == anchor_root

    # On receiving a block of `GENESIS_SLOT + 1` slot
    block_1 = build_empty_block_for_next_slot(spec, state)
    signed_block_1 = state_transition_and_sign_block(spec, state, block_1)
    add_block_to_store(spec, store, signed_block_1)

    # On receiving a block of next epoch
    block_2 = build_empty_block_for_next_slot(spec, state)
    signed_block_2 = state_transition_and_sign_block(spec, state, block_2)
    add_block_to_store(spec, store, signed_block_2)

    assert spec.get_head(store) == spec.hash_tree_root(block_2)


@with_all_phases
@spec_state_test
def test_split_tie_breaker_no_attestations(spec, state):
    genesis_state = state.copy()

    # Initialization
    store = spec.get_forkchoice_store(state)
    anchor_root = get_anchor_root(spec, state)
    assert spec.get_head(store) == anchor_root

    # block at slot 1
    block_1_state = genesis_state.copy()
    block_1 = build_empty_block_for_next_slot(spec, block_1_state)
    signed_block_1 = state_transition_and_sign_block(spec, block_1_state, block_1)
    add_block_to_store(spec, store, signed_block_1)

    # additional block at slot 1
    block_2_state = genesis_state.copy()
    block_2 = build_empty_block_for_next_slot(spec, block_2_state)
    block_2.body.graffiti = b'\x42' * 32
    signed_block_2 = state_transition_and_sign_block(spec, block_2_state, block_2)
    add_block_to_store(spec, store, signed_block_2)

    highest_root = max(spec.hash_tree_root(block_1), spec.hash_tree_root(block_2))

    assert spec.get_head(store) == highest_root


@with_all_phases
@spec_state_test
def test_shorter_chain_but_heavier_weight(spec, state):
    genesis_state = state.copy()

    # Initialization
    store = spec.get_forkchoice_store(state)
    anchor_root = get_anchor_root(spec, state)
    assert spec.get_head(store) == anchor_root

    # build longer tree
    long_state = genesis_state.copy()
    for i in range(3):
        long_block = build_empty_block_for_next_slot(spec, long_state)
        signed_long_block = state_transition_and_sign_block(spec, long_state, long_block)
        add_block_to_store(spec, store, signed_long_block)

    # build short tree
    short_state = genesis_state.copy()
    short_block = build_empty_block_for_next_slot(spec, short_state)
    short_block.body.graffiti = b'\x42' * 32
    signed_short_block = state_transition_and_sign_block(spec, short_state, short_block)
    add_block_to_store(spec, store, signed_short_block)

    short_attestation = get_valid_attestation(spec, short_state, short_block.slot, signed=True)
    add_attestation_to_store(spec, store, short_attestation)

    assert spec.get_head(store) == spec.hash_tree_root(short_block)


@with_all_phases
@spec_state_test
def test_filtered_block_tree(spec, state):
    # Initialization
    store = spec.get_forkchoice_store(state)
    anchor_root = get_anchor_root(spec, state)

    # transition state past initial couple of epochs
    next_epoch(spec, state)
    next_epoch(spec, state)

    assert spec.get_head(store) == anchor_root

    # fill in attestations for entire epoch, justifying the recent epoch
    prev_state, signed_blocks, state = next_epoch_with_attestations(spec, state, True, False)
    attestations = [
        attestation for signed_block in signed_blocks
        for attestation in signed_block.message.body.attestations
    ]
    assert state.current_justified_checkpoint.epoch > prev_state.current_justified_checkpoint.epoch

    # tick time forward and add blocks and attestations to store
    current_time = state.slot * spec.SECONDS_PER_SLOT + store.genesis_time
    spec.on_tick(store, current_time)
    for signed_block in signed_blocks:
        spec.on_block(store, signed_block)
    for attestation in attestations:
        spec.on_attestation(store, attestation)

    assert store.justified_checkpoint == state.current_justified_checkpoint

    # the last block in the branch should be the head
    expected_head_root = spec.hash_tree_root(signed_blocks[-1].message)
    assert spec.get_head(store) == expected_head_root

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
    current_time = (attestations[-1].data.slot + 1) * spec.SECONDS_PER_SLOT + store.genesis_time
    spec.on_tick(store, current_time)

    # include rogue block and associated attestations in the store
    spec.on_block(store, signed_rogue_block)
    for attestation in attestations:
        spec.on_attestation(store, attestation)

    # ensure that get_head still returns the head from the previous branch
    assert spec.get_head(store) == expected_head_root
