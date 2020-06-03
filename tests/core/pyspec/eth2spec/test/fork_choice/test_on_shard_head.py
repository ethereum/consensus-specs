from eth2spec.utils.ssz.ssz_impl import hash_tree_root

from eth2spec.test.context import spec_state_test, with_all_phases_except, PHASE0
from eth2spec.test.helpers.shard_block import (
    build_attestation_with_shard_transition,
    build_shard_block,
    build_shard_transitions_till_slot,
    get_committee_index_of_shard,
)
from eth2spec.test.helpers.fork_choice import add_block_to_store, get_anchor_root
from eth2spec.test.helpers.state import next_slot, state_transition_and_sign_block
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
    assert shard_store.blocks[hash_tree_root(signed_block.message)] == signed_block.message


def run_apply_shard_and_beacon(spec, state, store, shard_store, shard_blocks_buffer):
    shard = shard_store.shard
    committee_index = get_committee_index_of_shard(spec, state, state.slot, shard)
    has_shard_committee = committee_index is not None
    store.time = store.time + spec.SECONDS_PER_SLOT * spec.SLOTS_PER_EPOCH

    # Create SignedShardBlock
    # Check offsets
    temp_state = state.copy()
    next_slot(spec, temp_state)
    offset_slots = spec.get_offset_slots(temp_state, shard)
    if state.slot in offset_slots:
        # Build block
        body = b'\x56' * 4
        shard_head_root = spec.get_shard_head(store, shard_store)
        shard_parent_state = shard_store.block_states[shard_head_root]
        assert shard_parent_state.slot != state.slot
        shard_block = build_shard_block(
            spec, state, shard,
            shard_parent_state=shard_parent_state, slot=state.slot, body=body, signed=True
        )
        shard_blocks_buffer.append(shard_block)
        run_on_shard_block(spec, store, shard_store, shard_block)
        assert spec.get_shard_head(store, shard_store) == shard_block.message.hash_tree_root()

    beacon_block = build_empty_block(spec, state, slot=state.slot + 1)

    # Attester creates `attestation`
    if has_shard_committee and len(shard_blocks_buffer) > 0:
        # Use temporary next state to get ShardTransition of shard block
        shard_transitions = build_shard_transitions_till_slot(
            spec,
            state,
            shard_blocks={shard: shard_blocks_buffer},
            on_time_slot=state.slot + 1,
        )
        shard_transition = shard_transitions[shard]

        attestation = build_attestation_with_shard_transition(
            spec,
            state,
            index=committee_index,
            on_time_slot=state.slot + 1,
            shard_transition=shard_transition,
        )
        assert attestation.data.slot == state.slot
        assert spec.get_shard(state, attestation) == shard
        beacon_block.body.attestations = [attestation]
        beacon_block.body.shard_transitions = shard_transitions

    signed_beacon_block = state_transition_and_sign_block(spec, state, beacon_block)

    add_block_to_store(spec, store, signed_beacon_block)
    assert spec.get_head(store) == beacon_block.hash_tree_root()

    if has_shard_committee:
        shard_blocks_buffer = []  # clear buffer

    return has_shard_committee, shard_blocks_buffer


@with_all_phases_except([PHASE0])
@spec_state_test
def test_basic(spec, state):
    spec.PHASE_1_GENESIS_SLOT = 0  # FIXME: remove mocking
    state = spec.upgrade_to_phase1(state)

    # Initialization
    store = spec.get_forkchoice_store(state)
    anchor_root = get_anchor_root(spec, state)
    assert spec.get_head(store) == anchor_root

    shard = spec.Shard(1)
    shard_store = spec.get_forkchoice_shard_store(state, shard)
    shard_block_count = 2
    shard_blocks_buffer = []
    while shard_block_count > 0:
        has_shard_committee, shard_blocks_buffer = run_apply_shard_and_beacon(
            spec, state, store, shard_store, shard_blocks_buffer
        )
        if has_shard_committee:
            shard_block_count -= 1
