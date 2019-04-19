from copy import deepcopy

import pytest

import eth2spec.phase0.spec as spec

from eth2spec.phase0.state_transition import (
    state_transition,
)
from .helpers import (
    build_empty_block_for_next_slot,
    fill_aggregate_attestation,
    get_current_epoch,
    get_epoch_start_slot,
    get_valid_attestation,
    next_epoch,
)

# mark entire file as 'state'
pytestmark = pytest.mark.state


def check_finality(state,
                   prev_state,
                   current_justified_changed,
                   previous_justified_changed,
                   finalized_changed):
    if current_justified_changed:
        assert state.current_justified_epoch > prev_state.current_justified_epoch
        assert state.current_justified_root != prev_state.current_justified_root
    else:
        assert state.current_justified_epoch == prev_state.current_justified_epoch
        assert state.current_justified_root == prev_state.current_justified_root

    if previous_justified_changed:
        assert state.previous_justified_epoch > prev_state.previous_justified_epoch
        assert state.previous_justified_root != prev_state.previous_justified_root
    else:
        assert state.previous_justified_epoch == prev_state.previous_justified_epoch
        assert state.previous_justified_root == prev_state.previous_justified_root

    if finalized_changed:
        assert state.finalized_epoch > prev_state.finalized_epoch
        assert state.finalized_root != prev_state.finalized_root
    else:
        assert state.finalized_epoch == prev_state.finalized_epoch
        assert state.finalized_root == prev_state.finalized_root


def test_finality_from_genesis_rule_4(state):
    test_state = deepcopy(state)

    blocks = []
    for epoch in range(6):
        old_current_justified_epoch = test_state.current_justified_epoch
        old_current_justified_root = test_state.current_justified_root
        for slot in range(spec.SLOTS_PER_EPOCH):
            attestation = None
            slot_to_attest = test_state.slot - spec.MIN_ATTESTATION_INCLUSION_DELAY + 1
            if slot_to_attest >= spec.GENESIS_SLOT:
                attestation = get_valid_attestation(test_state, slot_to_attest)
                fill_aggregate_attestation(test_state, attestation)
            block = build_empty_block_for_next_slot(test_state)
            if attestation:
                block.body.attestations.append(attestation)
            state_transition(test_state, block)
            blocks.append(block)

        if epoch == 0:
            check_finality(test_state, state, False, False, False)
        elif epoch == 1:
            check_finality(test_state, state, False, False, False)
        elif epoch == 2:
            check_finality(test_state, state, True, False, False)
        elif epoch >= 3:
            # rule 4 of finaliy
            check_finality(test_state, state, True, True, True)
            assert test_state.finalized_epoch == old_current_justified_epoch
            assert test_state.finalized_root == old_current_justified_root

    return state, blocks, test_state


def test_finality_rule_1(state):
    # get past first two epochs that finality does not run on
    next_epoch(state)
    next_epoch(state)

    test_state = deepcopy(state)

    blocks = []
    for epoch in range(3):
        old_previous_justified_epoch = test_state.previous_justified_epoch
        old_previous_justified_root = test_state.previous_justified_root
        for slot in range(spec.SLOTS_PER_EPOCH):
            slot_to_attest = test_state.slot - spec.SLOTS_PER_EPOCH + 1
            attestation = get_valid_attestation(test_state, slot_to_attest)
            fill_aggregate_attestation(test_state, attestation)
            block = build_empty_block_for_next_slot(test_state)
            block.body.attestations.append(attestation)
            state_transition(test_state, block)

            assert len(test_state.previous_epoch_attestations) >= 0
            assert len(test_state.current_epoch_attestations) == 0

            blocks.append(block)

        if epoch == 0:
            check_finality(test_state, state, True, False, False)
        elif epoch == 1:
            check_finality(test_state, state, True, True, False)
        elif epoch == 2:
            # finalized by rule 1
            check_finality(test_state, state, True, True, True)
            assert test_state.finalized_epoch == old_previous_justified_epoch
            assert test_state.finalized_root == old_previous_justified_root


def test_finality_rule_2(state):
    # get past first two epochs that finality does not run on
    next_epoch(state)
    next_epoch(state)

    test_state = deepcopy(state)

    blocks = []
    for epoch in range(3):
        old_previous_justified_epoch = test_state.previous_justified_epoch
        old_previous_justified_root = test_state.previous_justified_root
        for slot in range(spec.SLOTS_PER_EPOCH):
            attestation = None
            if epoch == 0:
                slot_to_attest = test_state.slot - spec.MIN_ATTESTATION_INCLUSION_DELAY + 1
                if slot_to_attest >= get_epoch_start_slot(get_current_epoch(state)):
                    attestation = get_valid_attestation(test_state, slot_to_attest)
                    fill_aggregate_attestation(test_state, attestation)
            if epoch == 2:
                slot_to_attest = test_state.slot - spec.SLOTS_PER_EPOCH + 1
                attestation = get_valid_attestation(test_state, slot_to_attest)
                fill_aggregate_attestation(test_state, attestation)

            block = build_empty_block_for_next_slot(test_state)
            if attestation:
                block.body.attestations.append(attestation)
            state_transition(test_state, block)
            blocks.append(block)

        if epoch == 0:
            check_finality(test_state, state, True, False, False)
        elif epoch == 1:
            check_finality(test_state, state, True, True, False)
        elif epoch == 2:
            # finalized by rule 2
            check_finality(test_state, state, True, True, True)
            assert test_state.finalized_epoch == old_previous_justified_epoch
            assert test_state.finalized_root == old_previous_justified_root
