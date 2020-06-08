from eth2spec.test.context import (
    PHASE0,
    with_all_phases_except,
    spec_state_test,
)
from eth2spec.test.helpers.attestations import get_valid_on_time_attestation
from eth2spec.test.helpers.shard_transitions import run_shard_transitions_processing
from eth2spec.test.helpers.shard_block import (
    build_shard_block,
    get_shard_transitions,
)
from eth2spec.test.helpers.state import transition_to, transition_to_valid_shard_slot, next_slot


def run_basic_crosslink_tests(spec, state, target_len_offset_slot, valid=True):
    state = transition_to_valid_shard_slot(spec, state)
    committee_index = spec.CommitteeIndex(0)
    shard = spec.compute_shard_from_committee_index(state, committee_index, state.slot + target_len_offset_slot - 1)
    assert state.shard_states[shard].slot == state.slot - 1
    transition_to(spec, state, state.slot + target_len_offset_slot)
    assert state.shard_states[shard].slot == state.slot - target_len_offset_slot - 1

    # Create SignedShardBlock
    body = b'\x56' * spec.MAX_SHARD_BLOCK_SIZE
    shard_block = build_shard_block(spec, state, shard, body=body, slot=state.slot, signed=True)
    shard_blocks = [shard_block]
    shard_transitions = get_shard_transitions(
        spec,
        state,
        shard_blocks={shard: shard_blocks},
    )
    shard_transition = shard_transitions[shard]
    attestation = get_valid_on_time_attestation(
        spec,
        state,
        index=committee_index,
        shard_transition=shard_transition,
        signed=False,
    )
    next_slot(spec, state)
    pre_gasprice = state.shard_states[shard].gasprice
    pre_shard_state = state.shard_states[shard]
    yield from run_shard_transitions_processing(spec, state, shard_transitions, [attestation], valid=valid)

    if valid:
        shard_state = state.shard_states[shard]
        assert shard_state != pre_shard_state
        assert shard_state == shard_transition.shard_states[len(shard_transition.shard_states) - 1]
        assert shard_state.latest_block_root == shard_block.message.hash_tree_root()
        if target_len_offset_slot == 1:
            assert shard_state.gasprice > pre_gasprice


@with_all_phases_except([PHASE0])
@spec_state_test
def test_basic_crosslinks(spec, state):
    # NOTE: this test is only for full crosslink (minimal config), not for mainnet
    yield from run_basic_crosslink_tests(spec, state, target_len_offset_slot=1, valid=True)


@with_all_phases_except([PHASE0])
@spec_state_test
def test_multiple_offset_slots(spec, state):
    # NOTE: this test is only for full crosslink (minimal config), not for mainnet
    yield from run_basic_crosslink_tests(spec, state, target_len_offset_slot=2, valid=True)
