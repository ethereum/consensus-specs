from copy import deepcopy

from eth2spec.test.context import spec_state_test, with_all_phases
from eth2spec.test.helpers.state import (
    next_epoch,
    next_slot,
)
from eth2spec.test.helpers.attestations import (
    add_attestations_to_state,
    fill_aggregate_attestation,
    get_valid_attestation,
)
from eth2spec.test.phase_0.epoch_processing.run_epoch_process_base import run_epoch_processing_with


def run_process_rewards_and_penalties(spec, state):
    yield from run_epoch_processing_with(spec, state, 'process_rewards_and_penalties')


@with_all_phases
@spec_state_test
def test_genesis_epoch_no_attestations_no_penalties(spec, state):
    pre_state = deepcopy(state)

    assert spec.compute_epoch_of_slot(state.slot) == spec.GENESIS_EPOCH

    yield from run_process_rewards_and_penalties(spec, state)

    for index in range(len(pre_state.validators)):
        assert state.balances[index] == pre_state.balances[index]


@with_all_phases
@spec_state_test
def test_genesis_epoch_full_attestations_no_rewards(spec, state):
    attestations = []
    for slot in range(spec.SLOTS_PER_EPOCH - spec.MIN_ATTESTATION_INCLUSION_DELAY - 1):
        attestation = get_valid_attestation(spec, state)
        fill_aggregate_attestation(spec, state, attestation, signed=True)
        attestations.append(attestation)
        next_slot(spec, state)
    add_attestations_to_state(spec, state, attestations, state.slot + spec.MIN_ATTESTATION_INCLUSION_DELAY)

    assert spec.compute_epoch_of_slot(state.slot) == spec.GENESIS_EPOCH

    pre_state = deepcopy(state)

    yield from run_process_rewards_and_penalties(spec, state)

    for index in range(len(pre_state.validators)):
        assert state.balances[index] == pre_state.balances[index]


@with_all_phases
@spec_state_test
def test_no_attestations_all_penalties(spec, state):
    next_epoch(spec, state)
    pre_state = deepcopy(state)

    yield from run_process_rewards_and_penalties(spec, state)

    for index in range(len(pre_state.validators)):
        assert state.balances[index] < pre_state.balances[index]


@with_all_phases
@spec_state_test
def test_duplicate_attestation(spec, state):
    attestation = get_valid_attestation(spec, state)
    fill_aggregate_attestation(spec, state, attestation, signed=True)

    indexed_attestation = spec.get_indexed_attestation(state, attestation)
    participants = indexed_attestation.custody_bit_0_indices + indexed_attestation.custody_bit_1_indices

    assert len(participants) > 0

    single_state = deepcopy(state)
    dup_state = deepcopy(state)

    inclusion_slot = state.slot + spec.MIN_ATTESTATION_INCLUSION_DELAY
    add_attestations_to_state(spec, single_state, [attestation], inclusion_slot)
    add_attestations_to_state(spec, dup_state, [attestation, attestation], inclusion_slot)

    next_epoch(spec, single_state)
    next_epoch(spec, dup_state)

    # Run non-duplicate inclusion rewards for comparision. Do not yield test vectors
    pre, post = run_process_rewards_and_penalties(spec, single_state)

    # Output duplicate inclusion to test vectors
    yield from run_process_rewards_and_penalties(spec, dup_state)

    for index in participants:
        assert state.balances[index] < single_state.balances[index]
        assert single_state.balances[index] == dup_state.balances[index]
