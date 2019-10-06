from copy import deepcopy

from eth2spec.test.context import spec_state_test, spec_state_misc_balances_test, with_all_phases
from eth2spec.test.helpers.state import (
    next_epoch,
    next_slot,
)
from eth2spec.test.helpers.attestations import (
    add_attestations_to_state,
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
    for slot in range(spec.SLOTS_PER_EPOCH - 1):
        # create an attestation for each slot
        if slot < spec.SLOTS_PER_EPOCH:
            attestation = get_valid_attestation(spec, state, signed=True)
            attestations.append(attestation)
        # fill each created slot in state after inclusion delay
        if slot - spec.MIN_ATTESTATION_INCLUSION_DELAY >= 0:
            include_att = attestations[slot - spec.MIN_ATTESTATION_INCLUSION_DELAY]
            add_attestations_to_state(spec, state, [include_att], state.slot)
        next_slot(spec, state)

    # ensure has not cross the epoch boundary
    assert spec.compute_epoch_of_slot(state.slot) == spec.GENESIS_EPOCH

    pre_state = deepcopy(state)

    yield from run_process_rewards_and_penalties(spec, state)

    for index in range(len(pre_state.validators)):
        assert state.balances[index] == pre_state.balances[index]


@with_all_phases
@spec_state_test
def test_full_attestations(spec, state):
    attestations = []
    for slot in range(spec.SLOTS_PER_EPOCH + spec.MIN_ATTESTATION_INCLUSION_DELAY):
        # create an attestation for each slot in epoch
        if slot < spec.SLOTS_PER_EPOCH:
            attestation = get_valid_attestation(spec, state, signed=True)
            attestations.append(attestation)
        # fill each created slot in state after inclusion delay
        if slot - spec.MIN_ATTESTATION_INCLUSION_DELAY >= 0:
            include_att = attestations[slot - spec.MIN_ATTESTATION_INCLUSION_DELAY]
            add_attestations_to_state(spec, state, [include_att], state.slot)
        next_slot(spec, state)

    assert spec.compute_epoch_of_slot(state.slot) == spec.GENESIS_EPOCH + 1
    assert len(state.previous_epoch_attestations) == spec.SLOTS_PER_EPOCH

    pre_state = deepcopy(state)

    yield from run_process_rewards_and_penalties(spec, state)

    attesting_indices = spec.get_unslashed_attesting_indices(state, attestations)
    assert len(attesting_indices) > 0
    for index in range(len(pre_state.validators)):
        if index in attesting_indices:
            assert state.balances[index] > pre_state.balances[index]
        else:
            assert state.balances[index] < pre_state.balances[index]


@with_all_phases
@spec_state_misc_balances_test
def test_full_attestations_misc_balances(spec, state):
    attestations = []
    for slot in range(spec.SLOTS_PER_EPOCH + spec.MIN_ATTESTATION_INCLUSION_DELAY):
        # create an attestation for each slot in epoch
        if slot < spec.SLOTS_PER_EPOCH:
            attestation = get_valid_attestation(spec, state, signed=True)
            attestations.append(attestation)
        # fill each created slot in state after inclusion delay
        if slot - spec.MIN_ATTESTATION_INCLUSION_DELAY >= 0:
            include_att = attestations[slot - spec.MIN_ATTESTATION_INCLUSION_DELAY]
            add_attestations_to_state(spec, state, [include_att], state.slot)
        next_slot(spec, state)

    assert spec.compute_epoch_of_slot(state.slot) == spec.GENESIS_EPOCH + 1
    assert len(state.previous_epoch_attestations) == spec.SLOTS_PER_EPOCH

    pre_state = deepcopy(state)

    yield from run_process_rewards_and_penalties(spec, state)

    attesting_indices = spec.get_unslashed_attesting_indices(state, attestations)
    assert len(attesting_indices) > 0
    assert len(attesting_indices) != len(pre_state.validators)
    for index in range(len(pre_state.validators)):
        if index in attesting_indices:
            assert state.balances[index] > pre_state.balances[index]
        elif spec.is_active_validator(pre_state.validators[index], spec.compute_epoch_of_slot(state.slot)):
            assert state.balances[index] < pre_state.balances[index]
        else:
            assert state.balances[index] == pre_state.balances[index]


@with_all_phases
@spec_state_test
def test_no_attestations_all_penalties(spec, state):
    next_epoch(spec, state)
    pre_state = deepcopy(state)

    assert spec.compute_epoch_of_slot(state.slot) == spec.GENESIS_EPOCH + 1

    yield from run_process_rewards_and_penalties(spec, state)

    for index in range(len(pre_state.validators)):
        assert state.balances[index] < pre_state.balances[index]


@with_all_phases
@spec_state_test
def test_duplicate_attestation(spec, state):
    """
    Although duplicate attestations can be included on-chain, they should only
    be rewarded for once.
    This test addresses this issue found at Interop
    https://github.com/djrtwo/interop-test-cases/tree/master/tests/prysm_16_duplicate_attestation_rewards
    """
    attestation = get_valid_attestation(spec, state, signed=True)

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
    for _ in run_process_rewards_and_penalties(spec, single_state):
        pass

    # Output duplicate inclusion to test vectors
    yield from run_process_rewards_and_penalties(spec, dup_state)

    for index in participants:
        assert state.balances[index] < single_state.balances[index]
        assert single_state.balances[index] == dup_state.balances[index]
