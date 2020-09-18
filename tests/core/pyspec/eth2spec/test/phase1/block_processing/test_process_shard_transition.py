from eth2spec.test.context import (
    PHASE0,
    with_all_phases_except,
    only_full_crosslink,
    spec_state_test,
)
from eth2spec.test.helpers.attestations import (
    get_valid_attestation,
    get_valid_on_time_attestation,
    run_attestation_processing,
)
from eth2spec.test.helpers.shard_transitions import (
    run_shard_transitions_processing,
)
from eth2spec.test.helpers.shard_block import (
    build_shard_block,
    get_shard_transitions,
    get_sample_shard_block_body,
    get_committee_index_of_shard,
)
from eth2spec.test.helpers.state import transition_to, transition_to_valid_shard_slot, next_slot


def get_initial_env(spec, state, target_len_offset_slot):
    transition_to_valid_shard_slot(spec, state)
    committee_index = spec.CommitteeIndex(0)
    target_shard_slot = state.slot + target_len_offset_slot - 1
    shard = spec.compute_shard_from_committee_index(state, committee_index, target_shard_slot)
    assert state.shard_states[shard].slot == state.slot - 1
    return state, shard, target_shard_slot


def get_attestations_and_shard_transitions(spec, state, shard_block_dict):
    shard_transitions = get_shard_transitions(spec, state, shard_block_dict)
    attestations = [
        get_valid_on_time_attestation(
            spec, state,
            index=get_committee_index_of_shard(spec, state, state.slot, shard),
            shard_transition=shard_transition,
            signed=True,
        )
        for shard, shard_transition in enumerate(shard_transitions)
        if shard_transition != spec.ShardTransition()
    ]
    return attestations, shard_transitions


def run_successful_crosslink_tests(spec, state, target_len_offset_slot):
    state, shard, target_shard_slot = get_initial_env(spec, state, target_len_offset_slot)
    init_slot = state.slot

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

    for attestation in attestations:
        _, _, _ = run_attestation_processing(spec, state, attestation)

    _, winning_roots = spec.get_shard_winning_roots(state, attestations)
    assert len(winning_roots) == 1
    shard_transition = shard_transitions[shard]
    assert winning_roots[0] == shard_transition.hash_tree_root()

    pre_gasprice = state.shard_states[shard].gasprice
    pre_shard_states = state.shard_states.copy()
    yield from run_shard_transitions_processing(spec, state, shard_transitions, attestations)

    for index, shard_state in enumerate(state.shard_states):
        if index == shard:
            assert shard_state != pre_shard_states[index]
            assert shard_state == shard_transition.shard_states[len(shard_transition.shard_states) - 1]
            assert shard_state.latest_block_root == shard_block.message.hash_tree_root()
            if target_len_offset_slot == 1:
                assert shard_state.gasprice > pre_gasprice
        else:
            assert shard_state == pre_shard_states[index]

    for pending_attestation in state.current_epoch_attestations:
        assert bool(pending_attestation.crosslink_success) is True


@with_all_phases_except([PHASE0])
@spec_state_test
@only_full_crosslink
def test_basic_crosslinks(spec, state):
    yield from run_successful_crosslink_tests(spec, state, target_len_offset_slot=1)


@with_all_phases_except([PHASE0])
@spec_state_test
@only_full_crosslink
def test_multiple_offset_slots(spec, state):
    yield from run_successful_crosslink_tests(spec, state, target_len_offset_slot=2)


@with_all_phases_except([PHASE0])
@spec_state_test
@only_full_crosslink
def test_no_winning_root(spec, state):
    state, shard, target_shard_slot = get_initial_env(spec, state, target_len_offset_slot=1)
    init_slot = state.slot

    # Create SignedShardBlock at init_slot
    shard_block = build_shard_block(
        spec, state, shard,
        slot=init_slot, body=get_sample_shard_block_body(spec, is_max=True), signed=True
    )

    # Transition state to target shard slot
    transition_to(spec, state, target_shard_slot)

    # Create a shard_transitions that would be included at beacon block `target_shard_slot + 1`
    shard_transitions = get_shard_transitions(spec, state, {shard: [shard_block]})
    shard_transition = shard_transitions[shard]
    committee_index = get_committee_index_of_shard(spec, state, state.slot, shard)
    attestation = get_valid_attestation(
        spec, state,
        index=committee_index,
        shard_transition=shard_transition,
        # Decrease attested participants to 1/3 committee
        filter_participant_set=lambda committee: set(list(committee)[:len(committee) // 3]),
        signed=True,
        on_time=True,
    )

    next_slot(spec, state)

    _, _, _ = run_attestation_processing(spec, state, attestation)

    _, winning_roots = spec.get_shard_winning_roots(state, [attestation])
    assert len(winning_roots) == 0

    # No winning root, shard_transitions[shard] is empty
    shard_transitions = [spec.ShardTransition()] * spec.MAX_SHARDS
    pre_shard_states = state.shard_states.copy()
    yield from run_shard_transitions_processing(spec, state, shard_transitions, [attestation])

    for pending_attestation in state.current_epoch_attestations:
        assert bool(pending_attestation.crosslink_success) is False

    assert state.shard_states == pre_shard_states


@with_all_phases_except([PHASE0])
@spec_state_test
@only_full_crosslink
def test_wrong_shard_transition_root(spec, state):
    state, shard, target_shard_slot = get_initial_env(spec, state, target_len_offset_slot=1)
    init_slot = state.slot

    # Create SignedShardBlock at init_slot
    shard_block = build_shard_block(
        spec, state, shard,
        slot=init_slot, body=get_sample_shard_block_body(spec, is_max=True), signed=True
    )

    # Transition state to target shard slot
    transition_to(spec, state, target_shard_slot)

    # Create a shard_transitions that would be included at beacon block `target_shard_slot + 1`
    shard_transitions = get_shard_transitions(spec, state, {shard: [shard_block]})
    shard_transition = shard_transitions[shard]
    wrong_shard_transition = shard_transition.copy()
    wrong_shard_transition.shard_states[shard].gasprice = shard_transition.shard_states[shard].gasprice + 1
    committee_index = get_committee_index_of_shard(spec, state, state.slot, shard)
    attestation = get_valid_attestation(
        spec, state,
        index=committee_index,
        shard_transition=wrong_shard_transition,
        signed=True,
        on_time=True,
    )
    attestations = [attestation]

    next_slot(spec, state)

    run_attestation_processing(spec, state, attestation)

    # Check if winning root != shard_transition.hash_tree_root()
    _, winning_roots = spec.get_shard_winning_roots(state, attestations)
    assert len(winning_roots) == 1
    shard_transition = shard_transitions[shard]
    assert winning_roots[0] != shard_transition.hash_tree_root()

    yield from run_shard_transitions_processing(spec, state, shard_transitions, attestations, valid=False)
