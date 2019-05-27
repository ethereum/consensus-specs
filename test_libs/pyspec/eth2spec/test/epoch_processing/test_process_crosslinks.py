from copy import deepcopy

import eth2spec.phase0.spec as spec

from eth2spec.phase0.spec import (
    process_slot,
    get_crosslink_deltas,
    process_crosslinks,
    state_transition,
)
from eth2spec.test.context import spec_state_test
from eth2spec.test.helpers.state import (
    next_epoch,
    next_slot
)
from eth2spec.test.helpers.block import apply_empty_block, sign_block
from eth2spec.test.helpers.attestations import (
    add_attestation_to_state,
    build_empty_block_for_next_slot,
    fill_aggregate_attestation,
    get_crosslink_committee,
    get_valid_attestation,
    sign_attestation,
)


def run_process_crosslinks(state, valid=True):
    """
    Run ``process_crosslinks``, yielding:
      - pre-state ('pre')
      - post-state ('post').
    If ``valid == False``, run expecting ``AssertionError``
    """
    # transition state to slot before state transition
    slot = state.slot + (spec.SLOTS_PER_EPOCH - state.slot % spec.SLOTS_PER_EPOCH) - 1
    block = build_empty_block_for_next_slot(state)
    block.slot = slot
    sign_block(state, block)
    state_transition(state, block)

    # cache state before epoch transition
    process_slot(state)

    yield 'pre', state
    process_crosslinks(state)
    yield 'post', state


@spec_state_test
def test_no_attestations(state):
    yield from run_process_crosslinks(state)

    for shard in range(spec.SHARD_COUNT):
        assert state.previous_crosslinks[shard] == state.current_crosslinks[shard]


@spec_state_test
def test_single_crosslink_update_from_current_epoch(state):
    next_epoch(state)

    attestation = get_valid_attestation(state, signed=True)

    fill_aggregate_attestation(state, attestation)
    add_attestation_to_state(state, attestation, state.slot + spec.MIN_ATTESTATION_INCLUSION_DELAY)

    assert len(state.current_epoch_attestations) == 1

    shard = attestation.data.crosslink.shard
    pre_crosslink = deepcopy(state.current_crosslinks[shard])

    yield from run_process_crosslinks(state)

    assert state.previous_crosslinks[shard] != state.current_crosslinks[shard]
    assert pre_crosslink != state.current_crosslinks[shard]


@spec_state_test
def test_single_crosslink_update_from_previous_epoch(state):
    next_epoch(state)

    attestation = get_valid_attestation(state, signed=True)

    fill_aggregate_attestation(state, attestation)
    add_attestation_to_state(state, attestation, state.slot + spec.SLOTS_PER_EPOCH)

    assert len(state.previous_epoch_attestations) == 1

    shard = attestation.data.crosslink.shard
    pre_crosslink = deepcopy(state.current_crosslinks[shard])

    crosslink_deltas = get_crosslink_deltas(state)

    yield from run_process_crosslinks(state)

    assert state.previous_crosslinks[shard] != state.current_crosslinks[shard]
    assert pre_crosslink != state.current_crosslinks[shard]

    # ensure rewarded
    for index in get_crosslink_committee(state, attestation.data.target_epoch, attestation.data.crosslink.shard):
        assert crosslink_deltas[0][index] > 0
        assert crosslink_deltas[1][index] == 0


@spec_state_test
def test_double_late_crosslink(state):
    if spec.get_epoch_committee_count(state, spec.get_current_epoch(state)) < spec.SHARD_COUNT:
        print("warning: ignoring test, test-assumptions are incompatible with configuration")
        return

    next_epoch(state)
    state.slot += 4

    attestation_1 = get_valid_attestation(state, signed=True)
    fill_aggregate_attestation(state, attestation_1)

    # add attestation_1 to next epoch
    next_epoch(state)
    add_attestation_to_state(state, attestation_1, state.slot + 1)

    for slot in range(spec.SLOTS_PER_EPOCH):
        attestation_2 = get_valid_attestation(state)
        if attestation_2.data.crosslink.shard == attestation_1.data.crosslink.shard:
            sign_attestation(state, attestation_2)
            break
        next_slot(state)
    apply_empty_block(state)

    fill_aggregate_attestation(state, attestation_2)

    # add attestation_2 in the next epoch after attestation_1 has
    # already updated the relevant crosslink
    next_epoch(state)
    add_attestation_to_state(state, attestation_2, state.slot + 1)

    assert len(state.previous_epoch_attestations) == 1
    assert len(state.current_epoch_attestations) == 0

    crosslink_deltas = get_crosslink_deltas(state)

    yield from run_process_crosslinks(state)

    shard = attestation_2.data.crosslink.shard

    # ensure that the current crosslinks were not updated by the second attestation
    assert state.previous_crosslinks[shard] == state.current_crosslinks[shard]
    # ensure no reward, only penalties for the failed crosslink
    for index in get_crosslink_committee(state, attestation_2.data.target_epoch, attestation_2.data.crosslink.shard):
        assert crosslink_deltas[0][index] == 0
        assert crosslink_deltas[1][index] > 0
