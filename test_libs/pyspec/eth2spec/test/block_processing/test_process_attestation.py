from copy import deepcopy

import eth2spec.phase0.spec as spec

from eth2spec.phase0.state_transition import (
    state_transition,
)
from eth2spec.phase0.spec import (
    get_current_epoch,
    process_attestation
)
from eth2spec.test.helpers import (
    build_empty_block_for_next_slot,
    get_valid_attestation,
    next_epoch,
    next_slot,
)

from eth2spec.test.context import spec_state_test, expect_assertion_error


def run_attestation_processing(state, attestation, valid=True):
    """
    Run ``process_attestation``, yielding:
      - pre-state ('pre')
      - attestation ('attestation')
      - post-state ('post').
    If ``valid == False``, run expecting ``AssertionError``
    """
    # yield pre-state
    yield 'pre', state

    yield 'attestation', attestation

    # If the attestation is invalid, processing is aborted, and there is no post-state.
    if not valid:
        expect_assertion_error(lambda: process_attestation(state, attestation))
        yield 'post', None
        return

    current_epoch_count = len(state.current_epoch_attestations)
    previous_epoch_count = len(state.previous_epoch_attestations)

    # process attestation
    process_attestation(state, attestation)

    # Make sure the attestation has been processed
    if attestation.data.target_epoch == get_current_epoch(state):
        assert len(state.current_epoch_attestations) == current_epoch_count + 1
    else:
        assert len(state.previous_epoch_attestations) == previous_epoch_count + 1

    # yield post-state
    yield 'post', state


@spec_state_test
def test_success(state):
    attestation = get_valid_attestation(state)
    state.slot += spec.MIN_ATTESTATION_INCLUSION_DELAY

    yield from run_attestation_processing(state, attestation)


@spec_state_test
def test_success_previous_epoch(state):
    attestation = get_valid_attestation(state)
    block = build_empty_block_for_next_slot(state)
    block.slot = state.slot + spec.SLOTS_PER_EPOCH
    state_transition(state, block)

    yield from run_attestation_processing(state, attestation)


@spec_state_test
def test_before_inclusion_delay(state):
    attestation = get_valid_attestation(state)
    # do not increment slot to allow for inclusion delay

    yield from run_attestation_processing(state, attestation, False)


@spec_state_test
def test_after_epoch_slots(state):
    attestation = get_valid_attestation(state)
    block = build_empty_block_for_next_slot(state)
    # increment past latest inclusion slot
    block.slot = state.slot + spec.SLOTS_PER_EPOCH + 1
    state_transition(state, block)

    yield from run_attestation_processing(state, attestation, False)


@spec_state_test
def test_old_source_epoch(state):
    state.slot = spec.SLOTS_PER_EPOCH * 5
    state.finalized_epoch = 2
    state.previous_justified_epoch = 3
    state.current_justified_epoch = 4
    attestation = get_valid_attestation(state, slot=(spec.SLOTS_PER_EPOCH * 3) + 1)

    # test logic sanity check: make sure the attestation is pointing to oldest known source epoch
    assert attestation.data.source_epoch == state.previous_justified_epoch

    # Now go beyond that, it will be invalid
    attestation.data.source_epoch -= 1

    yield from run_attestation_processing(state, attestation, False)


@spec_state_test
def test_wrong_shard(state):
    attestation = get_valid_attestation(state)
    state.slot += spec.MIN_ATTESTATION_INCLUSION_DELAY

    attestation.data.shard += 1

    yield from run_attestation_processing(state, attestation, False)


@spec_state_test
def test_new_source_epoch(state):
    attestation = get_valid_attestation(state)
    state.slot += spec.MIN_ATTESTATION_INCLUSION_DELAY

    attestation.data.source_epoch += 1

    yield from run_attestation_processing(state, attestation, False)


@spec_state_test
def test_source_root_is_target_root(state):
    attestation = get_valid_attestation(state)
    state.slot += spec.MIN_ATTESTATION_INCLUSION_DELAY

    attestation.data.source_root = attestation.data.target_root

    yield from run_attestation_processing(state, attestation, False)


@spec_state_test
def test_invalid_current_source_root(state):
    state.slot = spec.SLOTS_PER_EPOCH * 5
    state.finalized_epoch = 2

    state.previous_justified_epoch = 3
    state.previous_justified_root = b'\x01' * 32

    state.current_justified_epoch = 4
    state.current_justified_root = b'\xff' * 32

    attestation = get_valid_attestation(state, slot=(spec.SLOTS_PER_EPOCH * 3) + 1)
    state.slot += spec.MIN_ATTESTATION_INCLUSION_DELAY

    # Test logic sanity checks:
    assert state.current_justified_root != state.previous_justified_root
    assert attestation.data.source_root == state.previous_justified_root

    # Make attestation source root invalid: should be previous justified, not current one
    attestation.data.source_root = state.current_justified_root

    yield from run_attestation_processing(state, attestation, False)


@spec_state_test
def test_bad_source_root(state):
    attestation = get_valid_attestation(state)
    state.slot += spec.MIN_ATTESTATION_INCLUSION_DELAY

    attestation.data.source_root = b'\x42' * 32

    yield from run_attestation_processing(state, attestation, False)


@spec_state_test
def test_non_zero_crosslink_data_root(state):
    attestation = get_valid_attestation(state)
    state.slot += spec.MIN_ATTESTATION_INCLUSION_DELAY

    attestation.data.crosslink_data_root = b'\x42' * 32

    yield from run_attestation_processing(state, attestation, False)


@spec_state_test
def test_bad_previous_crosslink(state):
    next_epoch(state)
    attestation = get_valid_attestation(state)
    for _ in range(spec.MIN_ATTESTATION_INCLUSION_DELAY):
        next_slot(state)

    state.current_crosslinks[attestation.data.shard].epoch += 10

    yield from run_attestation_processing(state, attestation, False)


@spec_state_test
def test_non_empty_custody_bitfield(state):
    attestation = get_valid_attestation(state)
    state.slot += spec.MIN_ATTESTATION_INCLUSION_DELAY

    attestation.custody_bitfield = deepcopy(attestation.aggregation_bitfield)

    yield from run_attestation_processing(state, attestation, False)


@spec_state_test
def test_empty_aggregation_bitfield(state):
    attestation = get_valid_attestation(state)
    state.slot += spec.MIN_ATTESTATION_INCLUSION_DELAY

    attestation.aggregation_bitfield = b'\x00' * len(attestation.aggregation_bitfield)

    yield from run_attestation_processing(state, attestation, False)
