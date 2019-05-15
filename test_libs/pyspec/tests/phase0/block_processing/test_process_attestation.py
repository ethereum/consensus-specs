from copy import deepcopy
import pytest

import eth2spec.phase0.spec as spec

from eth2spec.phase0.spec import (
    get_current_epoch,
    process_attestation,
    slot_to_epoch,
    state_transition,
)
from tests.phase0.helpers import (
    build_empty_block_for_next_slot,
    get_valid_attestation,
    next_epoch,
    next_slot,
)


# mark entire file as 'attestations'
pytestmark = pytest.mark.attestations


def run_attestation_processing(state, attestation, valid=True):
    """
    Run ``process_attestation`` returning the pre and post state.
    If ``valid == False``, run expecting ``AssertionError``
    """
    post_state = deepcopy(state)

    if not valid:
        with pytest.raises(AssertionError):
            process_attestation(post_state, attestation)
        return state, None

    process_attestation(post_state, attestation)

    current_epoch = get_current_epoch(state)
    if attestation.data.target_epoch == current_epoch:
        assert len(post_state.current_epoch_attestations) == len(state.current_epoch_attestations) + 1
    else:
        assert len(post_state.previous_epoch_attestations) == len(state.previous_epoch_attestations) + 1

    return state, post_state


def test_success(state):
    attestation = get_valid_attestation(state)
    state.slot += spec.MIN_ATTESTATION_INCLUSION_DELAY

    pre_state, post_state = run_attestation_processing(state, attestation)

    return pre_state, attestation, post_state


def test_success_prevous_epoch(state):
    attestation = get_valid_attestation(state)
    block = build_empty_block_for_next_slot(state)
    block.slot = state.slot + spec.SLOTS_PER_EPOCH
    state_transition(state, block)

    pre_state, post_state = run_attestation_processing(state, attestation)

    return pre_state, attestation, post_state


def test_before_inclusion_delay(state):
    attestation = get_valid_attestation(state)
    # do not increment slot to allow for inclusion delay

    pre_state, post_state = run_attestation_processing(state, attestation, False)

    return pre_state, attestation, post_state


def test_after_epoch_slots(state):
    attestation = get_valid_attestation(state)
    block = build_empty_block_for_next_slot(state)
    # increment past latest inclusion slot
    block.slot = state.slot + spec.SLOTS_PER_EPOCH + 1
    state_transition(state, block)

    pre_state, post_state = run_attestation_processing(state, attestation, False)

    return pre_state, attestation, post_state


def test_bad_source_epoch(state):
    attestation = get_valid_attestation(state)
    state.slot += spec.MIN_ATTESTATION_INCLUSION_DELAY

    attestation.data.source_epoch += 10

    pre_state, post_state = run_attestation_processing(state, attestation, False)

    return pre_state, attestation, post_state


def test_bad_source_root(state):
    attestation = get_valid_attestation(state)
    state.slot += spec.MIN_ATTESTATION_INCLUSION_DELAY

    attestation.data.source_root = b'\x42' * 32

    pre_state, post_state = run_attestation_processing(state, attestation, False)

    return pre_state, attestation, post_state


def test_non_zero_crosslink_data_root(state):
    attestation = get_valid_attestation(state)
    state.slot += spec.MIN_ATTESTATION_INCLUSION_DELAY

    attestation.data.crosslink.data_root = b'\x42' * 32

    pre_state, post_state = run_attestation_processing(state, attestation, False)

    return pre_state, attestation, post_state


def test_bad_previous_crosslink(state):
    next_epoch(state)
    attestation = get_valid_attestation(state)
    for _ in range(spec.MIN_ATTESTATION_INCLUSION_DELAY):
        next_slot(state)

    state.current_crosslinks[attestation.data.crosslink.shard].epoch += 10

    pre_state, post_state = run_attestation_processing(state, attestation, False)

    return pre_state, attestation, post_state


def test_non_empty_custody_bitfield(state):
    attestation = get_valid_attestation(state)
    state.slot += spec.MIN_ATTESTATION_INCLUSION_DELAY

    attestation.custody_bitfield = deepcopy(attestation.aggregation_bitfield)

    pre_state, post_state = run_attestation_processing(state, attestation, False)

    return pre_state, attestation, post_state


def test_empty_aggregation_bitfield(state):
    attestation = get_valid_attestation(state)
    state.slot += spec.MIN_ATTESTATION_INCLUSION_DELAY

    attestation.aggregation_bitfield = b'\x00' * len(attestation.aggregation_bitfield)

    pre_state, post_state = run_attestation_processing(state, attestation)

    return pre_state, attestation, post_state
