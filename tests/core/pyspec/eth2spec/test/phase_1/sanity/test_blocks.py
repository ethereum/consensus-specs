from typing import Dict, Sequence

from eth2spec.test.context import (
    PHASE0,
    with_all_phases_except,
    spec_state_test,
)
from eth2spec.test.helpers.attestations import get_valid_on_time_attestation
from eth2spec.test.helpers.block import build_empty_block
from eth2spec.test.helpers.shard_block import (
    build_shard_block,
    get_shard_transitions,
)
from eth2spec.test.helpers.state import state_transition_and_sign_block, transition_to_valid_shard_slot, transition_to


def run_beacon_block_with_shard_blocks(spec, state, target_len_offset_slot, committee_index, shard, valid=True):
    transition_to(spec, state, state.slot + target_len_offset_slot)

    body = b'\x56' * spec.MAX_SHARD_BLOCK_SIZE
    shard_block = build_shard_block(spec, state, shard, body=body, slot=state.slot, signed=True)
    shard_blocks: Dict[spec.Shard, Sequence[spec.SignedShardBlock]] = {shard: [shard_block]}

    shard_transitions = get_shard_transitions(spec, state, shard_blocks)
    attestations = [
        get_valid_on_time_attestation(
            spec,
            state,
            index=committee_index,
            shard_transition=shard_transitions[shard],
            signed=True,
        )
        for shard in shard_blocks.keys()
    ]

    beacon_block = build_empty_block(spec, state, slot=state.slot + 1)
    beacon_block.body.attestations = attestations
    beacon_block.body.shard_transitions = shard_transitions

    pre_gasprice = state.shard_states[shard].gasprice
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
            assert post_shard_state.slot == state.slot - 1
            if len(shard_blocks[shard]) == 0:
                # `latest_block_root` is the same
                assert post_shard_state.latest_block_root == pre_shard_states[shard].latest_block_root
            if target_len_offset_slot == 1 and len(shard_blocks) > 0:
                assert post_shard_state.gasprice > pre_gasprice


@with_all_phases_except([PHASE0])
@spec_state_test
def test_process_beacon_block_with_normal_shard_transition(spec, state):
    # NOTE: this test is only for full crosslink (minimal config), not for mainnet
    state = transition_to_valid_shard_slot(spec, state)

    target_len_offset_slot = 1
    committee_index = spec.CommitteeIndex(0)
    shard = spec.compute_shard_from_committee_index(state, committee_index, state.slot + target_len_offset_slot - 1)
    assert state.shard_states[shard].slot == state.slot - 1

    yield from run_beacon_block_with_shard_blocks(spec, state, target_len_offset_slot, committee_index, shard)


@with_all_phases_except([PHASE0])
@spec_state_test
def test_process_beacon_block_with_empty_proposal_transition(spec, state):
    # NOTE: this test is only for full crosslink (minimal config), not for mainnet
    state = transition_to_valid_shard_slot(spec, state)

    target_len_offset_slot = 1
    committee_index = spec.CommitteeIndex(0)
    shard = spec.compute_shard_from_committee_index(state, committee_index, state.slot + target_len_offset_slot - 1)
    assert state.shard_states[shard].slot == state.slot - 1

    yield from run_beacon_block_with_shard_blocks(spec, state, target_len_offset_slot, committee_index, shard)
