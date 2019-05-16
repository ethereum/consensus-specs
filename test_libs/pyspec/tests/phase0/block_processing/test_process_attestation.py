from copy import deepcopy
import pytest


# mark entire file as 'attestations'
pytestmark = pytest.mark.attestations


def run_attestation_processing(spec, helpers, state, attestation, valid=True):
    """
    Run ``spec.process_attestation`` returning the pre and post state.
    If ``valid == False``, run expecting ``AssertionError``
    """
    post_state = deepcopy(state)

    if not valid:
        with pytest.raises(AssertionError):
            spec.process_attestation(post_state, attestation)
        return state, None

    spec.process_attestation(post_state, attestation)

    current_epoch = spec.get_current_epoch(state)
    if attestation.data.target_epoch == current_epoch:
        assert len(post_state.current_epoch_attestations) == len(state.current_epoch_attestations) + 1
    else:
        assert len(post_state.previous_epoch_attestations) == len(state.previous_epoch_attestations) + 1

    return state, post_state


def test_success(spec, helpers, state):
    attestation = helpers.get_valid_attestation(state)
    state.slot += spec.MIN_ATTESTATION_INCLUSION_DELAY

    pre_state, post_state = run_attestation_processing(spec, helpers, state, attestation)

    return pre_state, attestation, post_state


def test_success_prevous_epoch(spec, helpers, state):
    attestation = helpers.get_valid_attestation(state)
    block = helpers.build_empty_block_for_next_slot(state)
    block.slot = state.slot + spec.SLOTS_PER_EPOCH
    spec.state_transition(state, block)

    pre_state, post_state = run_attestation_processing(spec, helpers, state, attestation)

    return pre_state, attestation, post_state


def test_before_inclusion_delay(spec, helpers, state):
    attestation = helpers.get_valid_attestation(state)
    # do not increment slot to allow for inclusion delay

    pre_state, post_state = run_attestation_processing(spec, helpers, state, attestation, False)

    return pre_state, attestation, post_state


def test_after_epoch_slots(spec, helpers, state):
    attestation = helpers.get_valid_attestation(state)
    block = helpers.build_empty_block_for_next_slot(state)
    # increment past latest inclusion slot
    block.slot = state.slot + spec.SLOTS_PER_EPOCH + 1
    spec.state_transition(state, block)

    pre_state, post_state = run_attestation_processing(spec, helpers, state, attestation, False)

    return pre_state, attestation, post_state


def test_bad_source_epoch(spec, helpers, state):
    attestation = helpers.get_valid_attestation(state)
    state.slot += spec.MIN_ATTESTATION_INCLUSION_DELAY

    attestation.data.source_epoch += 10

    pre_state, post_state = run_attestation_processing(spec, helpers, state, attestation, False)

    return pre_state, attestation, post_state


def test_bad_source_root(spec, helpers, state):
    attestation = helpers.get_valid_attestation(state)
    state.slot += spec.MIN_ATTESTATION_INCLUSION_DELAY

    attestation.data.source_root = b'\x42' * 32

    pre_state, post_state = run_attestation_processing(spec, helpers, state, attestation, False)

    return pre_state, attestation, post_state


def test_non_zero_crosslink_data_root(spec, helpers, state):
    attestation = helpers.get_valid_attestation(state)
    state.slot += spec.MIN_ATTESTATION_INCLUSION_DELAY

    attestation.data.crosslink.data_root = b'\x42' * 32

    pre_state, post_state = run_attestation_processing(spec, helpers, state, attestation, False)

    return pre_state, attestation, post_state


def test_bad_previous_crosslink(spec, helpers, state):
    helpers.next_epoch(state)
    attestation = helpers.get_valid_attestation(state)
    for _ in range(spec.MIN_ATTESTATION_INCLUSION_DELAY):
        helpers.next_slot(state)

    state.current_crosslinks[attestation.data.crosslink.shard].epoch += 10

    pre_state, post_state = run_attestation_processing(spec, helpers, state, attestation, False)

    return pre_state, attestation, post_state


def test_non_empty_custody_bitfield(spec, helpers, state):
    attestation = helpers.get_valid_attestation(state)
    state.slot += spec.MIN_ATTESTATION_INCLUSION_DELAY

    attestation.custody_bitfield = deepcopy(attestation.aggregation_bitfield)

    pre_state, post_state = run_attestation_processing(spec, helpers, state, attestation, False)

    return pre_state, attestation, post_state


def test_empty_aggregation_bitfield(spec, helpers, state):
    attestation = helpers.get_valid_attestation(state)
    state.slot += spec.MIN_ATTESTATION_INCLUSION_DELAY

    attestation.aggregation_bitfield = b'\x00' * len(attestation.aggregation_bitfield)

    pre_state, post_state = run_attestation_processing(spec, helpers, state, attestation)

    return pre_state, attestation, post_state
