from eth2spec.test.context import with_all_phases, spec_state_test
from eth2spec.test.helpers.attestations import get_valid_attestation
from eth2spec.test.helpers.block import build_empty_block_for_next_slot
from eth2spec.test.helpers.state import (
    next_epoch,
    next_epoch_with_attestations,
    state_transition_and_sign_block,
)
from eth2spec.utils.ssz.ssz_impl import signing_root


def add_block_to_store(spec, store, block):
    pre_state = store.block_states[block.parent_root]
    block_time = pre_state.genesis_time + block.slot * spec.SECONDS_PER_SLOT

    if store.time < block_time:
        spec.on_tick(store, block_time)

    spec.on_block(store, block)


def add_attestation_to_store(spec, store, attestation):
    parent_block = store.blocks[attestation.data.beacon_block_root]
    pre_state = store.block_states[spec.signing_root(parent_block)]
    block_time = pre_state.genesis_time + parent_block.slot * spec.SECONDS_PER_SLOT
    next_epoch_time = block_time + spec.SLOTS_PER_EPOCH * spec.SECONDS_PER_SLOT

    if store.time < next_epoch_time:
        spec.on_tick(store, next_epoch_time)

    spec.on_attestation(store, attestation)


@with_all_phases
@spec_state_test
def test_genesis(spec, state):
    # Initialization
    store = spec.get_genesis_store(state)
    genesis_block = spec.BeaconBlock(state_root=state.hash_tree_root())
    assert spec.get_head(store) == spec.signing_root(genesis_block)


@with_all_phases
@spec_state_test
def test_chain_no_attestations(spec, state):
    # Initialization
    store = spec.get_genesis_store(state)
    genesis_block = spec.BeaconBlock(state_root=state.hash_tree_root())
    assert spec.get_head(store) == spec.signing_root(genesis_block)

    # On receiving a block of `GENESIS_SLOT + 1` slot
    block_1 = build_empty_block_for_next_slot(spec, state)
    state_transition_and_sign_block(spec, state, block_1)
    add_block_to_store(spec, store, block_1)

    # On receiving a block of next epoch
    block_2 = build_empty_block_for_next_slot(spec, state)
    state_transition_and_sign_block(spec, state, block_2)
    add_block_to_store(spec, store, block_2)

    assert spec.get_head(store) == spec.signing_root(block_2)


@with_all_phases
@spec_state_test
def test_split_tie_breaker_no_attestations(spec, state):
    genesis_state = state.copy()

    # Initialization
    store = spec.get_genesis_store(state)
    genesis_block = spec.BeaconBlock(state_root=state.hash_tree_root())
    assert spec.get_head(store) == spec.signing_root(genesis_block)

    # block at slot 1
    block_1_state = genesis_state.copy()
    block_1 = build_empty_block_for_next_slot(spec, block_1_state)
    state_transition_and_sign_block(spec, block_1_state, block_1)
    add_block_to_store(spec, store, block_1)

    # additional block at slot 1
    block_2_state = genesis_state.copy()
    block_2 = build_empty_block_for_next_slot(spec, block_2_state)
    block_2.body.graffiti = b'\x42' * 32
    state_transition_and_sign_block(spec, block_2_state, block_2)
    add_block_to_store(spec, store, block_2)

    highest_root = max(spec.signing_root(block_1), spec.signing_root(block_2))

    assert spec.get_head(store) == highest_root


@with_all_phases
@spec_state_test
def test_shorter_chain_but_heavier_weight(spec, state):
    genesis_state = state.copy()

    # Initialization
    store = spec.get_genesis_store(state)
    genesis_block = spec.BeaconBlock(state_root=state.hash_tree_root())
    assert spec.get_head(store) == spec.signing_root(genesis_block)

    # build longer tree
    long_state = genesis_state.copy()
    for i in range(3):
        long_block = build_empty_block_for_next_slot(spec, long_state)
        state_transition_and_sign_block(spec, long_state, long_block)
        add_block_to_store(spec, store, long_block)

    # build short tree
    short_state = genesis_state.copy()
    short_block = build_empty_block_for_next_slot(spec, short_state)
    short_block.body.graffiti = b'\x42' * 32
    state_transition_and_sign_block(spec, short_state, short_block)
    add_block_to_store(spec, store, short_block)

    short_attestation = get_valid_attestation(spec, short_state, short_block.slot, signed=True)
    add_attestation_to_store(spec, store, short_attestation)

    assert spec.get_head(store) == spec.signing_root(short_block)


@with_all_phases
@spec_state_test
def test_filtered_block_tree(spec, state):
    # Initialization
    genesis_state_root = state.hash_tree_root()
    store = spec.get_genesis_store(state)
    genesis_block = spec.BeaconBlock(state_root=genesis_state_root)

    # transition state past initial couple of epochs
    next_epoch(spec, state)
    next_epoch(spec, state)

    assert spec.get_head(store) == spec.signing_root(genesis_block)

    # fill in attestations for entire epoch, justifying the recent epoch
    prev_state, blocks, state = next_epoch_with_attestations(spec, state, True, False)
    attestations = [attestation for block in blocks for attestation in block.body.attestations]
    assert state.current_justified_checkpoint.epoch > prev_state.current_justified_checkpoint.epoch

    # tick time forward and add blocks and attestations to store
    current_time = state.slot * spec.SECONDS_PER_SLOT + store.genesis_time
    spec.on_tick(store, current_time)
    for block in blocks:
        spec.on_block(store, block)
    for attestation in attestations:
        spec.on_attestation(store, attestation)

    assert store.justified_checkpoint == state.current_justified_checkpoint

    # the last block in the branch should be the head
    expected_head_root = signing_root(blocks[-1])
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
    rogue_block = build_empty_block_for_next_slot(spec, non_viable_state, True)
    state_transition_and_sign_block(spec, non_viable_state, rogue_block)

    # create an epoch's worth of attestations for the rogue block
    next_epoch(spec, non_viable_state)
    attestations = []
    for i in range(spec.SLOTS_PER_EPOCH):
        slot = rogue_block.slot + i
        for index in range(spec.get_committee_count_at_slot(non_viable_state, slot)):
            attestation = get_valid_attestation(spec, non_viable_state, rogue_block.slot + i, index)
            attestations.append(attestation)

    # tick time forward to be able to include up to the latest attestation
    current_time = (attestations[-1].data.slot + 1) * spec.SECONDS_PER_SLOT + store.genesis_time
    spec.on_tick(store, current_time)

    # include rogue block and associated attestations in the store
    spec.on_block(store, rogue_block)
    for attestation in attestations:
        spec.on_attestation(store, attestation)

    # ensure that get_head still returns the head from the previous branch
    assert spec.get_head(store) == expected_head_root
