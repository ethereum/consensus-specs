from eth2spec.utils.ssz.ssz_impl import hash_tree_root

from eth2spec.test.context import PHASE0, spec_state_test, with_all_phases_except, never_bls
from eth2spec.test.helpers.attestations import get_valid_on_time_attestation
from eth2spec.test.helpers.shard_block import (
    build_shard_block,
    get_shard_transitions,
    get_committee_index_of_shard,
)
from eth2spec.test.helpers.fork_choice import add_block_to_store, get_anchor_root
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


def apply_shard_block(spec, store, shard_store, beacon_parent_state, shard_blocks_buffer):
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


def apply_shard_and_beacon(spec, state, store, shard_store, shard_blocks_buffer):
    store.time = store.time + spec.SECONDS_PER_SLOT * spec.SLOTS_PER_EPOCH

    shard = shard_store.shard
    committee_index = get_committee_index_of_shard(spec, state, state.slot, shard)
    has_shard_committee = committee_index is not None  # has committee of `shard` at this slot

    beacon_block = build_empty_block(spec, state, slot=state.slot + 1)

    # If next slot has committee of `shard`, add `shard_transtion` to the proposing beacon block
    if has_shard_committee and len(shard_blocks_buffer) > 0:
        # Sanity check `get_pending_shard_blocks` function
        check_pending_shard_blocks(spec, store, shard_store, shard_blocks_buffer)
        # Use temporary next state to get ShardTransition of shard block
        shard_transitions = get_shard_transitions(
            spec,
            state,
            shard_block_dict={shard: shard_blocks_buffer},
        )
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

    signed_beacon_block = state_transition_and_sign_block(spec, state, beacon_block)  # transition!
    add_block_to_store(spec, store, signed_beacon_block)
    assert spec.get_head(store) == beacon_block.hash_tree_root()

    # On shard block at transitioned `state.slot`
    if is_in_offset_sets(spec, state, shard):
        # The created shard block would be appended to `shard_blocks_buffer`
        apply_shard_block(spec, store, shard_store, state, shard_blocks_buffer)

    return has_shard_committee


@with_all_phases_except([PHASE0])
@spec_state_test
@never_bls  # Set to never_bls for testing `check_pending_shard_blocks`
def test_basic(spec, state):
    spec.PHASE_1_GENESIS_SLOT = 0  # NOTE: mock genesis slot here
    state = spec.upgrade_to_phase1(state)
    shard = spec.Shard(1)

    # Initialization
    store = spec.get_forkchoice_store(state)
    anchor_root = get_anchor_root(spec, state)
    assert spec.get_head(store) == anchor_root

    shard_store = store.shard_stores[shard]
    shard_head_root = spec.get_shard_head(store, shard_store)
    assert shard_head_root == state.shard_states[shard].latest_block_root
    assert shard_store.block_states[shard_head_root].slot == 1
    assert shard_store.block_states[shard_head_root] == state.shard_states[shard]

    # For mainnet config, it's possible that only one committee of `shard` per epoch.
    # we set this counter to test more rounds.
    shard_committee_counter = 2
    shard_blocks_buffer = []
    while shard_committee_counter > 0:
        has_shard_committee = apply_shard_and_beacon(
            spec, state, store, shard_store, shard_blocks_buffer
        )
        if has_shard_committee:
            shard_committee_counter -= 1
