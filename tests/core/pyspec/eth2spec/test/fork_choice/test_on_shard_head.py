from eth2spec.utils.ssz.ssz_impl import hash_tree_root

from eth2spec.test.context import spec_state_test, with_all_phases_except, PHASE0
from eth2spec.test.helpers.shard_block import (
    build_attestation_with_shard_transition,
    build_shard_block,
    build_shard_transitions_till_slot,
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


def run_apply_shard_and_beacon(spec, state, store, shard_store, committee_index):
    shard = shard_store.shard
    store.time = store.time + spec.SECONDS_PER_SLOT * spec.SLOTS_PER_EPOCH

    # Create SignedShardBlock
    body = b'\x56' * spec.MAX_SHARD_BLOCK_SIZE
    target_len_offset_slot = 1
    shard_block = build_shard_block(spec, state, shard, body=body, signed=True)
    shard_blocks = [shard_block]

    # Attester creates `attestation`
    # Use temporary next state to get ShardTransition of shard block
    shard_transitions = build_shard_transitions_till_slot(
        spec,
        state,
        shard_blocks={shard: shard_blocks},
        on_time_slot=state.slot + target_len_offset_slot,
    )
    shard_transition = shard_transitions[shard]
    attestation = build_attestation_with_shard_transition(
        spec,
        state,
        index=committee_index,
        on_time_slot=state.slot + target_len_offset_slot,
        shard_transition=shard_transition,
    )

    # Propose beacon block at slot
    beacon_block = build_empty_block(spec, state, slot=state.slot + 1)
    beacon_block.body.attestations = [attestation]
    beacon_block.body.shard_transitions = shard_transitions
    signed_beacon_block = state_transition_and_sign_block(spec, state, beacon_block)

    run_on_shard_block(spec, store, shard_store, shard_block)
    add_block_to_store(spec, store, signed_beacon_block)

    assert spec.get_head(store) == beacon_block.hash_tree_root()
    assert spec.get_shard_head(store, shard_store) == shard_block.message.hash_tree_root()


@with_all_phases_except([PHASE0])
@spec_state_test
def test_basic(spec, state):
    spec.PHASE_1_GENESIS_SLOT = 0  # FIXME: remove mocking
    state = spec.upgrade_to_phase1(state)
    next_slot(spec, state)

    # Initialization
    store = spec.get_forkchoice_store(state)
    anchor_root = get_anchor_root(spec, state)
    assert spec.get_head(store) == anchor_root

    committee_index = spec.CommitteeIndex(0)
    shard = spec.compute_shard_from_committee_index(state, committee_index, state.slot)
    shard_store = spec.get_forkchoice_shard_store(state, shard)

    run_apply_shard_and_beacon(spec, state, store, shard_store, committee_index)
    run_apply_shard_and_beacon(spec, state, store, shard_store, committee_index)
