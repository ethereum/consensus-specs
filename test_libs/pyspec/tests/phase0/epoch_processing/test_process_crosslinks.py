from copy import deepcopy
import pytest


# mark entire file as 'crosslinks'
pytestmark = pytest.mark.crosslinks


def run_process_crosslinks(state, valid=True):
    # transition state to slot before state transition
    slot = state.slot + (spec.SLOTS_PER_EPOCH - state.slot % spec.SLOTS_PER_EPOCH) - 1
    block = helpers.build_empty_block_for_next_slot(state)
    block.slot = slot
    spec.state_transition(state, block)

    # cache state before epoch transition
    spec.process_slot(state)

    post_state = deepcopy(state)
    spec.process_crosslinks(post_state)

    return state, post_state


def test_no_attestations(state):
    pre_state, post_state = run_process_crosslinks(state)

    for shard in range(spec.SHARD_COUNT):
        assert post_state.previous_crosslinks[shard] == post_state.current_crosslinks[shard]

    return pre_state, post_state


def test_single_crosslink_update_from_current_epoch(state):
    helpers.next_epoch(state)

    attestation = helpers.get_valid_attestation(state)

    helpers.fill_aggregate_attestation(state, attestation)
    helpers.add_attestation_to_state(state, attestation, state.slot + spec.MIN_ATTESTATION_INCLUSION_DELAY)

    assert len(state.current_epoch_attestations) == 1

    pre_state, post_state = run_process_crosslinks(state)

    shard = attestation.data.crosslink.shard
    assert post_state.previous_crosslinks[shard] != post_state.current_crosslinks[shard]
    assert pre_state.current_crosslinks[shard] != post_state.current_crosslinks[shard]

    return pre_state, post_state


def test_single_crosslink_update_from_previous_epoch(state):
    helpers.next_epoch(state)

    attestation = helpers.get_valid_attestation(state)

    helpers.fill_aggregate_attestation(state, attestation)
    helpers.add_attestation_to_state(state, attestation, state.slot + spec.SLOTS_PER_EPOCH)

    assert len(state.previous_epoch_attestations) == 1

    pre_state, post_state = run_process_crosslinks(state)
    crosslink_deltas = spec.get_crosslink_deltas(state)

    shard = attestation.data.crosslink.shard
    assert post_state.previous_crosslinks[shard] != post_state.current_crosslinks[shard]
    assert pre_state.current_crosslinks[shard] != post_state.current_crosslinks[shard]
    # ensure rewarded
    for index in spec.get_crosslink_committee(state, attestation.data.target_epoch, attestation.data.crosslink.shard):
        assert crosslink_deltas[0][index] > 0
        assert crosslink_deltas[1][index] == 0

    return pre_state, post_state


def test_double_late_crosslink(state):
    helpers.next_epoch(state)
    state.slot += 4

    attestation_1 = helpers.get_valid_attestation(state)
    helpers.fill_aggregate_attestation(state, attestation_1)

    # add attestation_1 in the next epoch
    helpers.next_epoch(state)
    helpers.add_attestation_to_state(state, attestation_1, state.slot + 1)

    for slot in range(spec.SLOTS_PER_EPOCH):
        attestation_2 = helpers.get_valid_attestation(state)
        if attestation_2.data.crosslink.shard == attestation_1.data.crosslink.shard:
            break
        helpers.next_slot(state)
    helpers.fill_aggregate_attestation(state, attestation_2)

    # add attestation_2 in the next epoch after attestation_1 has
    # already updated the relevant crosslink
    helpers.next_epoch(state)
    helpers.add_attestation_to_state(state, attestation_2, state.slot + 1)

    assert len(state.previous_epoch_attestations) == 1
    assert len(state.current_epoch_attestations) == 0

    pre_state, post_state = run_process_crosslinks(state)
    crosslink_deltas = spec.get_crosslink_deltas(state)

    shard = attestation_2.data.crosslink.shard

    # ensure that the current crosslinks were not updated by the second attestation
    assert post_state.previous_crosslinks[shard] == post_state.current_crosslinks[shard]
    # ensure no reward, only penalties for the failed crosslink
    for index in spec.get_crosslink_committee(
            state,
            attestation_2.data.target_epoch,
            attestation_2.data.crosslink.shard):
        assert crosslink_deltas[0][index] == 0
        assert crosslink_deltas[1][index] > 0

    return pre_state, post_state
