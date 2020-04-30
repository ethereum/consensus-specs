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


def run_on_shard_block(spec, store, shard, signed_block, valid=True):
    if not valid:
        try:
            spec.on_shard_block(store, shard, signed_block)
        except AssertionError:
            return
        else:
            assert False

    spec.on_shard_block(store, shard, signed_block)
    assert store.shards[shard].blocks[hash_tree_root(signed_block.message)] == signed_block.message


def run_apply_shard_and_beacon(spec, state, store, shard, committee_index):
    store.time = store.time + spec.SECONDS_PER_SLOT * spec.SLOTS_PER_EPOCH

    # Create SignedShardBlock
    body = b'\x56' * spec.MAX_SHARD_BLOCK_SIZE
    shard_block = build_shard_block(spec, state, shard, body=body, signed=True)
    shard_blocks = [shard_block]

    # Attester creates `attestation`
    # Use temporary next state to get ShardTransition of shard block
    shard_transitions = build_shard_transitions_till_slot(
        spec,
        state,
        shards=[shard, ],
        shard_blocks={shard: shard_blocks},
        target_len_offset_slot=1,
    )
    shard_transition = shard_transitions[shard]
    attestation = build_attestation_with_shard_transition(
        spec,
        state,
        slot=state.slot,
        index=committee_index,
        target_len_offset_slot=1,
        shard_transition=shard_transition,
    )

    # Propose beacon block at slot
    beacon_block = build_empty_block(spec, state, slot=state.slot + 1)
    beacon_block.body.attestations = [attestation]
    beacon_block.body.shard_transitions = shard_transitions
    signed_beacon_block = state_transition_and_sign_block(spec, state, beacon_block)

    run_on_shard_block(spec, store, shard, shard_block)
    add_block_to_store(spec, store, signed_beacon_block)

    assert spec.get_head(store) == beacon_block.hash_tree_root()
    assert spec.get_shard_head(store, shard) == shard_block.message.hash_tree_root()


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

    run_apply_shard_and_beacon(spec, state, store, shard, committee_index)
    run_apply_shard_and_beacon(spec, state, store, shard, committee_index)
