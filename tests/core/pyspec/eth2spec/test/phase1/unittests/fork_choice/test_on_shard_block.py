from eth2spec.utils.ssz.ssz_impl import hash_tree_root

from eth2spec.test.context import PHASE0, spec_state_test, with_all_phases_except, never_bls
from eth2spec.test.helpers.attestations import get_valid_on_time_attestation
from eth2spec.test.helpers.shard_block import (
    build_shard_block,
    get_shard_transitions,
    get_committee_index_of_shard,
)
from eth2spec.test.helpers.fork_choice import add_block_to_store, get_anchor_root
from eth2spec.test.helpers.shard_transitions import is_full_crosslink
from eth2spec.test.helpers.state import state_transition_and_sign_block
from eth2spec.test.helpers.block import build_empty_block


def run_on_shard_block(spec, store, signed_block, valid=True):
    shard = signed_block.message.shard
    if not valid:
        try:
            spec.on_shard_block(store, signed_block)
        except AssertionError:
            return
        else:
            assert False

    spec.on_shard_block(store, signed_block)
    shard_store = store.shard_stores[shard]
    assert shard_store.signed_blocks[hash_tree_root(signed_block.message)] == signed_block


def initialize_store(spec, state, shards):
    store = spec.get_forkchoice_store(state)
    anchor_root = get_anchor_root(spec, state)
    assert spec.get_head(store) == anchor_root

    for shard in shards:
        shard_head_root = spec.get_shard_head(store, shard)
        assert shard_head_root == state.shard_states[shard].latest_block_root
        shard_store = store.shard_stores[shard]
        assert shard_store.block_states[shard_head_root].slot == 0
        assert shard_store.block_states[shard_head_root] == state.shard_states[shard]

    return store


def create_and_apply_shard_block(spec, store, shard, beacon_parent_state, shard_blocks_buffer):
    body = b'\x56' * 4
    shard_head_root = spec.get_shard_head(store, shard)
    shard_store = store.shard_stores[shard]
    shard_parent_state = shard_store.block_states[shard_head_root]
    assert shard_parent_state.slot != beacon_parent_state.slot
    shard_block = build_shard_block(
        spec, beacon_parent_state, shard,
        shard_parent_state=shard_parent_state, slot=beacon_parent_state.slot, body=body, signed=True
    )
    shard_blocks_buffer.append(shard_block)
    run_on_shard_block(spec, store, shard_block)
    assert spec.get_shard_head(store, shard) == shard_block.message.hash_tree_root()


def check_pending_shard_blocks(spec, store, shard, shard_blocks_buffer):
    pending_shard_blocks = spec.get_pending_shard_blocks(store, shard)
    assert pending_shard_blocks == shard_blocks_buffer


def is_in_offset_sets(spec, beacon_head_state, shard):
    offset_slots = spec.compute_offset_slots(
        beacon_head_state.shard_states[shard].slot, beacon_head_state.slot + 1
    )
    return beacon_head_state.slot in offset_slots


def create_attestation_for_shard_blocks(spec, beacon_parent_state, shard, committee_index, blocks,
                                        filter_participant_set=None):
    shard_transition = spec.get_shard_transition(beacon_parent_state, shard, blocks)
    attestation = get_valid_on_time_attestation(
        spec,
        beacon_parent_state,
        index=committee_index,
        shard_transition=shard_transition,
        signed=True,
    )
    return attestation


def create_beacon_block_with_shard_transition(
        spec, state, store, shard, shard_blocks_buffer, is_checking_pending_shard_blocks=True):
    beacon_block = build_empty_block(spec, state, slot=state.slot + 1)
    committee_index = get_committee_index_of_shard(spec, state, state.slot, shard)
    has_shard_committee = committee_index is not None  # has committee of `shard` at this slot

    beacon_block = build_empty_block(spec, state, slot=state.slot + 1)

    # If next slot has committee of `shard`, add `shard_transtion` to the proposing beacon block
    if has_shard_committee and len(shard_blocks_buffer) > 0:
        # Sanity check `get_pending_shard_blocks`
        # Assert that the pending shard blocks set in the store equal to shard_blocks_buffer
        if is_checking_pending_shard_blocks:
            check_pending_shard_blocks(spec, store, shard, shard_blocks_buffer)
        # Use temporary next state to get ShardTransition of shard block
        shard_transitions = get_shard_transitions(spec, state, shard_block_dict={shard: shard_blocks_buffer})
        shard_transition = shard_transitions[shard]
        attestation = get_valid_on_time_attestation(
            spec,
            state,
            index=committee_index,
            shard_transition=shard_transition,
            signed=True,
        )
        assert attestation.data.shard == shard
        beacon_block.body.attestations = [attestation]
        beacon_block.body.shard_transitions = shard_transitions

        # Clear buffer
        shard_blocks_buffer.clear()

    return beacon_block


def apply_all_attestation_to_store(spec, store, attestations):
    for attestation in attestations:
        spec.on_attestation(store, attestation)


def apply_beacon_block_to_store(spec, state, store, beacon_block):
    signed_beacon_block = state_transition_and_sign_block(spec, state, beacon_block)  # transition!
    store.time = store.time + spec.SECONDS_PER_SLOT
    add_block_to_store(spec, store, signed_beacon_block)
    apply_all_attestation_to_store(spec, store, signed_beacon_block.message.body.attestations)


def create_and_apply_beacon_and_shard_blocks(spec, state, store, shard, shard_blocks_buffer,
                                             is_checking_pending_shard_blocks=True):
    beacon_block = create_beacon_block_with_shard_transition(
        spec, state, store, shard, shard_blocks_buffer,
        is_checking_pending_shard_blocks=is_checking_pending_shard_blocks
    )
    apply_beacon_block_to_store(spec, state, store, beacon_block)

    # On shard block at the transitioned `state.slot`
    if is_in_offset_sets(spec, state, shard):
        # The created shard block would be appended to `shard_blocks_buffer`
        create_and_apply_shard_block(spec, store, shard, state, shard_blocks_buffer)

    has_shard_committee = get_committee_index_of_shard(spec, state, state.slot, shard) is not None
    return has_shard_committee


@with_all_phases_except([PHASE0])
@spec_state_test
@never_bls  # Set to never_bls for testing `check_pending_shard_blocks`
def test_basic(spec, state):
    spec.PHASE_1_GENESIS_SLOT = 0  # NOTE: mock genesis slot here
    state = spec.upgrade_to_phase1(state)
    shard = spec.Shard(1)

    # Initialization
    store = initialize_store(spec, state, [shard])

    # For mainnet config, it's possible that only one committee of `shard` per epoch.
    # we set this counter to test more rounds.
    shard_committee_counter = 2
    shard_blocks_buffer = []  # the accumulated shard blocks that haven't been crosslinked yet
    while shard_committee_counter > 0:
        has_shard_committee = create_and_apply_beacon_and_shard_blocks(spec, state, store, shard, shard_blocks_buffer)
        if has_shard_committee:
            shard_committee_counter -= 1


def create_simple_fork(spec, state, store, shard):
    # Beacon block
    beacon_block = create_beacon_block_with_shard_transition(spec, state, store, shard, [])
    apply_beacon_block_to_store(spec, state, store, beacon_block)

    beacon_head_root = spec.get_head(store)
    assert beacon_head_root == beacon_block.hash_tree_root()
    beacon_parent_state = store.block_states[beacon_head_root]
    shard_store = store.shard_stores[shard]
    shard_parent_state = shard_store.block_states[spec.get_shard_head(store, shard)]

    # Shard block A
    body = b'\x56' * 4
    forking_block_child = build_shard_block(
        spec, beacon_parent_state, shard,
        shard_parent_state=shard_parent_state, slot=beacon_parent_state.slot, body=body, signed=True
    )
    run_on_shard_block(spec, store, forking_block_child)

    # Shard block B
    body = b'\x78' * 4  # different body
    shard_block_b = build_shard_block(
        spec, beacon_parent_state, shard,
        shard_parent_state=shard_parent_state, slot=beacon_parent_state.slot, body=body, signed=True
    )
    run_on_shard_block(spec, store, shard_block_b)

    # Set forking_block
    current_head = spec.get_shard_head(store, shard)
    if current_head == forking_block_child.message.hash_tree_root():
        head_block = forking_block_child
        forking_block = shard_block_b
    else:
        assert current_head == shard_block_b.message.hash_tree_root()
        head_block = shard_block_b
        forking_block = forking_block_child

    return head_block, forking_block


@with_all_phases_except([PHASE0])
@spec_state_test
def test_shard_simple_fork(spec, state):
    if not is_full_crosslink(spec, state):
        # skip
        return

    spec.PHASE_1_GENESIS_SLOT = 0  # NOTE: mock genesis slot here
    state = spec.upgrade_to_phase1(state)
    shard = spec.Shard(1)

    # Initialization
    store = initialize_store(spec, state, [shard])

    # Create fork
    _, forking_block = create_simple_fork(spec, state, store, shard)

    # Vote for forking_block
    state = store.block_states[spec.get_head(store)].copy()
    beacon_block = create_beacon_block_with_shard_transition(spec, state, store, shard, [forking_block],
                                                             is_checking_pending_shard_blocks=False)
    store.time = store.time + spec.SECONDS_PER_SLOT
    apply_all_attestation_to_store(spec, store, beacon_block.body.attestations)

    # Head block has been changed
    assert spec.get_shard_head(store, shard) == forking_block.message.hash_tree_root()


@with_all_phases_except([PHASE0])
@spec_state_test
def test_shard_latest_messages_for_different_shards(spec, state):
    if not is_full_crosslink(spec, state):
        # skip
        return

    spec.PHASE_1_GENESIS_SLOT = 0  # NOTE: mock genesis slot here
    state = spec.upgrade_to_phase1(state)
    shard_0 = spec.Shard(0)
    shard_1 = spec.Shard(1)

    # Initialization
    store = initialize_store(spec, state, [shard_0, shard_1])

    # Shard 0 ----------------------------------
    # Create fork on shard 0
    _, forking_block = create_simple_fork(spec, state, store, shard_0)

    # Vote for forking_block on shard 0
    state = store.block_states[spec.get_head(store)].copy()
    beacon_block = create_beacon_block_with_shard_transition(spec, state, store, shard_0, [forking_block],
                                                             is_checking_pending_shard_blocks=False)
    store.time = store.time + spec.SECONDS_PER_SLOT
    apply_all_attestation_to_store(spec, store, beacon_block.body.attestations)

    # Head block of shard 0 has been changed due to the shard latest messages
    assert spec.get_shard_head(store, shard_0) == forking_block.message.hash_tree_root()

    # Shard 1 ----------------------------------
    # Run shard 1 after 1~2 epochs
    shard_committee_counter = 2
    shard_blocks_buffer = []  # the accumulated shard blocks that haven't been crosslinked yet
    while shard_committee_counter > 0:
        has_shard_committee = create_and_apply_beacon_and_shard_blocks(
            spec, state, store, shard_1, shard_blocks_buffer
        )
        if has_shard_committee:
            shard_committee_counter -= 1

    # Go back to see shard 0 ----------------------------------
    # The head block of shard 0 should be unchanged.
    assert spec.get_shard_head(store, shard_0) == forking_block.message.hash_tree_root()
