from copy import deepcopy
import pytest

import build.phase0.spec as spec

from build.phase0.state_transition import (
    state_transition,
)
from build.phase0.spec import (
    ZERO_HASH,
    cache_state,
    get_crosslink_committee_for_attestation,
    get_current_epoch,
    process_crosslinks,
    slot_to_epoch,
)
from tests.phase0.helpers import (
    add_attestation_to_state,
    build_empty_block_for_next_slot,
    fill_aggregate_attestation,
    get_valid_attestation,
    next_epoch,
    set_bitfield_bit,
)


# mark entire file as 'crosslinks'
pytestmark = pytest.mark.crosslinks


def run_process_crosslinks(state, valid=True):
    # transition state to slot before state transition
    slot = state.slot + (spec.SLOTS_PER_EPOCH - state.slot % spec.SLOTS_PER_EPOCH) - 1
    block = build_empty_block_for_next_slot(state)
    block.slot = slot
    state_transition(state, block)

    # cache state before epoch transition
    cache_state(state)

    post_state = deepcopy(state)
    process_crosslinks(post_state)

    return state, post_state


def test_no_attestations(state):
    pre_state, post_state = run_process_crosslinks(state)

    for shard in range(spec.SHARD_COUNT):
        assert post_state.previous_crosslinks[shard] == post_state.current_crosslinks[shard]

    return pre_state, post_state


def test_single_crosslink_update_from_current_epoch(state):
    next_epoch(state)

    attestation = get_valid_attestation(state)

    fill_aggregate_attestation(state, attestation)
    add_attestation_to_state(state, attestation, state.slot + spec.MIN_ATTESTATION_INCLUSION_DELAY)

    assert len(state.current_epoch_attestations) == 1

    pre_state, post_state = run_process_crosslinks(state)

    shard = attestation.data.shard
    assert post_state.previous_crosslinks[shard] != post_state.current_crosslinks[shard]
    assert pre_state.current_crosslinks[shard] != post_state.current_crosslinks[shard]

    return pre_state, post_state


def test_single_crosslink_update_from_previous_epoch(state):
    next_epoch(state)

    attestation = get_valid_attestation(state)

    fill_aggregate_attestation(state, attestation)
    add_attestation_to_state(state, attestation, state.slot + spec.SLOTS_PER_EPOCH)

    assert len(state.previous_epoch_attestations) == 1

    pre_state, post_state = run_process_crosslinks(state)

    shard = attestation.data.shard
    assert post_state.previous_crosslinks[shard] != post_state.current_crosslinks[shard]
    assert pre_state.current_crosslinks[shard] != post_state.current_crosslinks[shard]

    return pre_state, post_state


def test_double_late_crosslink(state):
    next_epoch(state)
    state.slot += 4

    attestation_1 = get_valid_attestation(state)
    fill_aggregate_attestation(state, attestation_1)

    # add attestation_1 in the next epoch
    next_epoch(state)
    add_attestation_to_state(state, attestation_1, state.slot + 1)

    state.slot = attestation_1.data.slot + spec.SLOTS_PER_EPOCH
    attestation_2 = get_valid_attestation(state)
    fill_aggregate_attestation(state, attestation_2)

    # add attestation_2 in the next epoch after attestation_1 has
    # already updated the relevant crosslink
    next_epoch(state)
    add_attestation_to_state(state, attestation_2, state.slot + 1)

    assert len(state.previous_epoch_attestations) == 1
    assert len(state.current_epoch_attestations) == 0

    pre_state, post_state = run_process_crosslinks(state)

    shard_1 = attestation_1.data.shard
    shard_2 = attestation_2.data.shard
    assert shard_1 == shard_2
    shard = shard_1

    # ensure that the current crosslinks were not updated by the second attestation
    assert post_state.previous_crosslinks[shard] == post_state.current_crosslinks[shard]

    return pre_state, post_state
