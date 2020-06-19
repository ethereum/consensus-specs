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
    get_sample_shard_block_body,
    get_committee_index_of_shard,
)
from eth2spec.test.helpers.state import transition_to, transition_to_valid_shard_slot, next_slot


def get_initial_env(spec, state, target_len_offset_slot):
    state = transition_to_valid_shard_slot(spec, state)
    committee_index = spec.CommitteeIndex(0)
    target_shard_slot = state.slot + target_len_offset_slot - 1
    shard = spec.compute_shard_from_committee_index(state, committee_index, target_shard_slot)
    return state, shard, target_shard_slot


def get_attestations_and_shard_transitions(spec, state, shard_block_dict):
    shard_transitions = get_shard_transitions(spec, state, shard_block_dict)
    attestations = [
        get_valid_on_time_attestation(
            spec, state,
            index=get_committee_index_of_shard(spec, state, state.slot, shard),
            shard_transition=shard_transition,
            signed=False,
        )
        for shard, shard_transition in enumerate(shard_transitions)
        if shard_transition != spec.ShardTransition()
    ]
    return attestations, shard_transitions


def run_basic_crosslink_tests(spec, state, target_len_offset_slot, valid=True):
    state, shard, target_shard_slot = get_initial_env(spec, state, target_len_offset_slot)
    init_slot = state.slot
    assert state.shard_states[shard].slot == init_slot - 1

    # Create SignedShardBlock at init_slot
    shard_block = build_shard_block(
        spec, state, shard,
        slot=init_slot, body=get_sample_shard_block_body(spec, is_max=True), signed=True
    )

    # Transition state to target shard slot
    transition_to(spec, state, target_shard_slot)

    # Create a shard_transitions that would be included at beacon block `target_shard_slot + 1`
    shard_block_dict = {shard: [shard_block]}
    attestations, shard_transitions = get_attestations_and_shard_transitions(spec, state, shard_block_dict)

    next_slot(spec, state)
    pre_gasprice = state.shard_states[shard].gasprice

    pre_shard_state = state.shard_states[shard]
    yield from run_shard_transitions_processing(spec, state, shard_transitions, attestations, valid=valid)

    if valid:
        shard_state = state.shard_states[shard]
        assert shard_state != pre_shard_state
        assert shard_state == shard_transitions[shard].shard_states[len(shard_transitions[shard].shard_states) - 1]
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


@with_all_phases_except([PHASE0])
@spec_state_test
def test_no_winning_root(spec, state):
    # NOTE: this test is only for full crosslink (minimal config), not for mainnet
    yield from run_basic_crosslink_tests(spec, state, target_len_offset_slot=1, valid=True)
