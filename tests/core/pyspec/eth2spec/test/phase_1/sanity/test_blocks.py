from typing import Dict, Sequence

from eth2spec.test.context import (
    PHASE0,
    with_all_phases_except,
    spec_state_test,
    always_bls,
)
from eth2spec.test.helpers.block import build_empty_block
from eth2spec.test.helpers.shard_block import (
    build_attestation_with_shard_transition,
    build_shard_block,
    build_shard_transitions_till_slot,
)
from eth2spec.test.helpers.state import state_transition_and_sign_block, transition_to_valid_shard_slot


def run_beacon_block_with_shard_blocks(spec, state, shard_blocks, target_len_offset_slot, committee_index, valid=True):
    shard_transitions = build_shard_transitions_till_slot(
        spec, state, shard_blocks, on_time_slot=state.slot + target_len_offset_slot
    )
    attestations = [
        build_attestation_with_shard_transition(
            spec,
            state,
            on_time_slot=state.slot + target_len_offset_slot,
            index=committee_index,
            shard_transition=shard_transitions[shard],
        )
        for shard in shard_blocks.keys()
    ]

    # Propose beacon block at slot `x + 1`
    beacon_block = build_empty_block(spec, state, slot=state.slot + target_len_offset_slot)
    beacon_block.body.attestations = attestations
    beacon_block.body.shard_transitions = shard_transitions

    pre_shard_states = state.shard_states.copy()
    yield 'pre', state.copy()
    yield 'block', beacon_block
    state_transition_and_sign_block(spec, state, beacon_block)
    if valid:
        yield 'post', state
    else:
        yield 'post', None
        return

    for shard in range(spec.get_active_shard_count(state)):
        post_shard_state = state.shard_states[shard]
        if shard in shard_blocks:
            # Shard state has been changed to state_transition result
            assert post_shard_state == shard_transitions[shard].shard_states[
                len(shard_transitions[shard].shard_states) - 1
            ]
            assert beacon_block.slot == shard_transitions[shard].shard_states[0].slot + target_len_offset_slot
            assert post_shard_state.slot == state.slot - 1
            if len(shard_blocks[shard]) == 0:
                # `latest_block_root` is the same
                assert post_shard_state.latest_block_root == pre_shard_states[shard].latest_block_root


@with_all_phases_except([PHASE0])
@spec_state_test
@always_bls
def test_process_beacon_block_with_normal_shard_transition(spec, state):
    state = transition_to_valid_shard_slot(spec, state)

    target_len_offset_slot = 1
    committee_index = spec.CommitteeIndex(0)
    shard = spec.compute_shard_from_committee_index(state, committee_index, state.slot)
    assert state.shard_states[shard].slot == state.slot - 1

    pre_gasprice = state.shard_states[shard].gasprice

    # Create SignedShardBlock at slot `shard_state.slot + 1`
    body = b'\x56' * spec.MAX_SHARD_BLOCK_SIZE
    shard_block = build_shard_block(spec, state, shard, body=body, signed=True)
    shard_blocks: Dict[spec.Shard, Sequence[spec.SignedShardBlock]] = {shard: [shard_block]}

    yield from run_beacon_block_with_shard_blocks(spec, state, shard_blocks, target_len_offset_slot, committee_index)

    shard_state = state.shard_states[shard]

    if target_len_offset_slot == 1 and len(shard_blocks) > 0:
        assert shard_state.gasprice > pre_gasprice


@with_all_phases_except([PHASE0])
@spec_state_test
@always_bls
def test_process_beacon_block_with_empty_proposal_transition(spec, state):
    state = transition_to_valid_shard_slot(spec, state)

    target_len_offset_slot = 1
    committee_index = spec.CommitteeIndex(0)
    shard = spec.compute_shard_from_committee_index(state, committee_index, state.slot)
    assert state.shard_states[shard].slot == state.slot - 1

    # No new shard block
    shard_blocks = {}

    pre_gasprice = state.shard_states[shard].gasprice

    yield from run_beacon_block_with_shard_blocks(spec, state, shard_blocks, target_len_offset_slot, committee_index)

    if target_len_offset_slot == 1 and len(shard_blocks) > 0:
        assert state.shard_states[shard].gasprice > pre_gasprice
