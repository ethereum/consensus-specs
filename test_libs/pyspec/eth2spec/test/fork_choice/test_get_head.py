from eth2spec.test.context import with_all_phases, spec_state_test
from eth2spec.test.helpers.attestations import get_valid_attestation
from eth2spec.test.helpers.block import build_empty_block_for_next_slot
from eth2spec.test.helpers.state import state_transition_and_sign_block


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
