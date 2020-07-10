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


def run_on_shard_block(spec, store, shard_store, signed_block, valid=True):
    if not valid:
        try:
            spec.on_shard_block(store, shard_store, signed_block)
        except AssertionError:
            return
        else:
            assert False

    spec.on_shard_block(store, shard_store, signed_block)
    assert shard_store.signed_blocks[hash_tree_root(signed_block.message)] == signed_block


def initialize_store(spec, state, shard):
    store = spec.get_forkchoice_store(state)
    anchor_root = get_anchor_root(spec, state)
    assert spec.get_head(store) == anchor_root

    shard_store = store.shard_stores[shard]
    shard_head_root = spec.get_shard_head(store, shard_store)
    assert shard_head_root == state.shard_states[shard].latest_block_root
    assert shard_store.block_states[shard_head_root].slot == 1
    assert shard_store.block_states[shard_head_root] == state.shard_states[shard]

    return store


def create_and_apply_shard_block(spec, store, shard_store, beacon_parent_state, shard_blocks_buffer):
    shard = shard_store.shard
    body = b'\x56' * 4
    shard_head_root = spec.get_shard_head(store, shard_store)
    shard_parent_state = shard_store.block_states[shard_head_root]
    assert shard_parent_state.slot != beacon_parent_state.slot
    shard_block = build_shard_block(
        spec, beacon_parent_state, shard,
        shard_parent_state=shard_parent_state, slot=beacon_parent_state.slot, body=body, signed=True
    )
    shard_blocks_buffer.append(shard_block)
    run_on_shard_block(spec, store, shard_store, shard_block)
    assert spec.get_shard_head(store, shard_store) == shard_block.message.hash_tree_root()


def check_pending_shard_blocks(spec, store, shard_store, shard_blocks_buffer):
    pending_shard_blocks = spec.get_pending_shard_blocks(store, shard_store)
    assert pending_shard_blocks == shard_blocks_buffer


def is_in_offset_sets(spec, beacon_head_state, shard):
    offset_slots = spec.compute_offset_slots(
        beacon_head_state.shard_states[shard].slot, beacon_head_state.slot + 1
    )
    return beacon_head_state.slot in offset_slots


def create_beacon_block_with_shard_transition(
        spec, state, store, shard, shard_blocks_buffer, is_checking_pending_shard_blocks=True):
    beacon_block = build_empty_block(spec, state, slot=state.slot + 1)
    shard_store = store.shard_stores[shard]
    committee_index = get_committee_index_of_shard(spec, state, state.slot, shard)
    has_shard_committee = committee_index is not None  # has committee of `shard` at this slot

    beacon_block = build_empty_block(spec, state, slot=state.slot + 1)

    # If next slot has committee of `shard`, add `shard_transtion` to the proposing beacon block
    if has_shard_committee and len(shard_blocks_buffer) > 0:
        # Sanity check `get_pending_shard_blocks`
        # Assert that the pending shard blocks set in the store equal to shard_blocks_buffer
        if is_checking_pending_shard_blocks:
            check_pending_shard_blocks(spec, store, shard_store, shard_blocks_buffer)
        # Use temporary next state to get ShardTransition of shard block
        shard_transitions = get_shard_transitions(spec, state, shard_block_dict={shard: shard_blocks_buffer})
        shard_transition = shard_transitions[shard]
        attestation = get_valid_on_time_attestation(
            spec,
            state,
            index=committee_index,
            shard_transition=shard_transition,
            signed=False,
        )
        assert attestation.data.shard == shard
        beacon_block.body.attestations = [attestation]
        beacon_block.body.shard_transitions = shard_transitions

        # Clear buffer
        shard_blocks_buffer.clear()

    return beacon_block


def apply_beacon_block_to_store(spec, state, store, beacon_block):
    signed_beacon_block = state_transition_and_sign_block(spec, state, beacon_block)  # transition!
    store.time = store.time + spec.SECONDS_PER_SLOT
    add_block_to_store(spec, store, signed_beacon_block)
    for attestation in signed_beacon_block.message.body.attestations:
        spec.on_attestation(store, attestation)


def create_and_apply_beacon_and_shard_blocks(spec, state, store, shard, shard_blocks_buffer):
    shard_store = store.shard_stores[shard]
    beacon_block = create_beacon_block_with_shard_transition(spec, state, store, shard, shard_blocks_buffer)
    apply_beacon_block_to_store(spec, state, store, beacon_block)

    # On shard block at the transitioned `state.slot`
    if is_in_offset_sets(spec, state, shard):
        # The created shard block would be appended to `shard_blocks_buffer`
        create_and_apply_shard_block(spec, store, shard_store, state, shard_blocks_buffer)

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
    store = initialize_store(spec, state, shard)

    # For mainnet config, it's possible that only one committee of `shard` per epoch.
    # we set this counter to test more rounds.
    shard_committee_counter = 2
    shard_blocks_buffer = []  # the accumulated shard blocks that haven't been crosslinked yet
    while shard_committee_counter > 0:
        has_shard_committee = create_and_apply_beacon_and_shard_blocks(
            spec, state, store, shard, shard_blocks_buffer
        )
        if has_shard_committee:
            shard_committee_counter -= 1


def create_simple_fork(spec, state, store, shard):
    # Beacon block
    assert state.slot == 1
    beacon_block = create_beacon_block_with_shard_transition(spec, state, store, shard, [])
    apply_beacon_block_to_store(spec, state, store, beacon_block)

    shard_store = store.shard_stores[shard]
    beacon_head_root = spec.get_head(store)
    assert beacon_head_root == beacon_block.hash_tree_root()
    beacon_parent_state = store.block_states[beacon_head_root]
    shard_parent_state = shard_store.block_states[spec.get_shard_head(store, shard_store)]

    # Shard block A on slot 2
    body = b'\x56' * 4
    shard_block_a = build_shard_block(
        spec, beacon_parent_state, shard,
        shard_parent_state=shard_parent_state, slot=beacon_parent_state.slot, body=body, signed=True
    )
    run_on_shard_block(spec, store, shard_store, shard_block_a)

    # Shard block A on slot 2
    body = b'\x78' * 4  # different body
    shard_block_b = build_shard_block(
        spec, beacon_parent_state, shard,
        shard_parent_state=shard_parent_state, slot=beacon_parent_state.slot, body=body, signed=True
    )
    run_on_shard_block(spec, store, shard_store, shard_block_b)

    # Set forking_block
    current_head = spec.get_shard_head(store, shard_store)
    if current_head == shard_block_a.message.hash_tree_root():
        head_block = shard_block_a
        forking_block = shard_block_b
    else:
        assert current_head == shard_block_b.message.hash_tree_root()
        head_block = shard_block_b
        forking_block = shard_block_a

    return head_block, forking_block


@with_all_phases_except([PHASE0])
@spec_state_test
@never_bls  # Set to never_bls for testing `check_pending_shard_blocks`
def test_shard_simple_fork(spec, state):
    if not is_full_crosslink(spec, state):
        # skip
        return

    spec.PHASE_1_GENESIS_SLOT = 0  # NOTE: mock genesis slot here
    state = spec.upgrade_to_phase1(state)
    shard = spec.Shard(1)

    # Initialization
    store = initialize_store(spec, state, shard)

    # Create fork
    _, forking_block = create_simple_fork(spec, state, store, shard)

    # Vote for forking_block
    state = store.block_states[spec.get_head(store)].copy()
    beacon_block = create_beacon_block_with_shard_transition(spec, state, store, shard, [forking_block],
                                                             is_checking_pending_shard_blocks=False)
    apply_beacon_block_to_store(spec, state, store, beacon_block)

    # Head block is changed
    shard_store = store.shard_stores[shard]
    assert spec.get_shard_head(store, shard_store) == forking_block.message.hash_tree_root()
