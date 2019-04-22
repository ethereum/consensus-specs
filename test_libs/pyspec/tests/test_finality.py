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


def next_epoch_with_attestations(state,
                                 fill_cur_epoch,
                                 fill_prev_epoch):
    post_state = deepcopy(state)
    blocks = []
    for slot in range(spec.SLOTS_PER_EPOCH):
        print("slot: %s", post_state.slot)
        block = build_empty_block_for_next_slot(post_state)
        if fill_prev_epoch:
            print("prev")
            slot_to_attest = post_state.slot - spec.SLOTS_PER_EPOCH + 1
            prev_attestation = get_valid_attestation(post_state, slot_to_attest)
            block.body.attestations.append(prev_attestation)

        if fill_cur_epoch:
            print("cur")
            slot_to_attest = post_state.slot - spec.MIN_ATTESTATION_INCLUSION_DELAY + 1
            if slot_to_attest >= get_epoch_start_slot(get_current_epoch(post_state)):
                cur_attestation = get_valid_attestation(post_state, slot_to_attest)
                fill_aggregate_attestation(post_state, cur_attestation)
                block.body.attestations.append(cur_attestation)

        state_transition(post_state, block)
        blocks.append(block)

        # if fill_prev_epoch:
            # assert len(post_state.previous_epoch_attestations) >= 0
        # else:
            # assert len(post_state.previous_epoch_attestations) == 0

        # if fill_cur_epoch:
            # assert len(post_state.current_epoch_attestations) >= 0
        # else:
            # assert len(post_state.current_epoch_attestations) == 0

    return state, blocks, post_state


def test_finality_from_genesis_rule_4(state):
    test_state = deepcopy(state)

    blocks = []
    for epoch in range(6):
        prev_state = deepcopy(test_state)
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
            check_finality(test_state, prev_state, False, False, False)
        elif epoch == 1:
            check_finality(test_state, prev_state, False, False, False)
        elif epoch == 2:
            check_finality(test_state, prev_state, True, False, False)
        elif epoch >= 3:
            # rule 4 of finaliy
            check_finality(test_state, prev_state, True, True, True)
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
        prev_state = deepcopy(test_state)
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
            check_finality(test_state, prev_state, True, False, False)
        elif epoch == 1:
            check_finality(test_state, prev_state, True, True, False)
        elif epoch == 2:
            # finalized by rule 1
            check_finality(test_state, prev_state, True, True, True)
            assert test_state.finalized_epoch == old_previous_justified_epoch
            assert test_state.finalized_root == old_previous_justified_root

    return state, blocks, test_state


def test_finality_rule_2(state):
    # get past first two epochs that finality does not run on
    next_epoch(state)
    next_epoch(state)

    test_state = deepcopy(state)

    blocks = []
    for epoch in range(3):
        old_previous_justified_epoch = test_state.previous_justified_epoch
        old_previous_justified_root = test_state.previous_justified_root
        if epoch == 0:
            prev_state, blocks, test_state = next_epoch_with_attestations(test_state, True, False)
            check_finality(test_state, prev_state, True, False, False)
        if epoch == 1:
            prev_state, blocks, test_state = next_epoch_with_attestations(test_state, False, False)
            check_finality(test_state, prev_state, False, True, False)
        if epoch == 2:
            prev_state, blocks, test_state = next_epoch_with_attestations(test_state, False, True)
            # finalized by rule 2
            check_finality(test_state, prev_state, True, False, True)
            assert test_state.finalized_epoch == old_previous_justified_epoch
            assert test_state.finalized_root == old_previous_justified_root
    return state, blocks, test_state


def test_finality_rule_3(state):
    # get past first two epochs that finality does not run on
    next_epoch(state)
    next_epoch(state)

    test_state = deepcopy(state)

    blocks = []
    for epoch in range(2):
        prev_state = deepcopy(test_state)
        for slot in range(spec.SLOTS_PER_EPOCH):
            slot_to_attest = test_state.slot - spec.MIN_ATTESTATION_INCLUSION_DELAY + 1
            attestation = get_valid_attestation(test_state, slot_to_attest)
            fill_aggregate_attestation(test_state, attestation)
            block = build_empty_block_for_next_slot(test_state)
            block.body.attestations.append(attestation)
            state_transition(test_state, block)

            blocks.append(block)
        if epoch == 0:
            check_finality(test_state, prev_state, True, False, False)
        if epoch == 1:
            check_finality(test_state, prev_state, True, True, True)

    prev_state = deepcopy(test_state)
    next_epoch(test_state)
    check_finality(test_state, prev_state, False, True, False)


    prev_state = deepcopy(test_state)
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
    check_finality(test_state, prev_state, True, False, True)


    prev_state = deepcopy(test_state)
    for slot in range(spec.SLOTS_PER_EPOCH):
        prev_slot_to_attest = test_state.slot - spec.SLOTS_PER_EPOCH + 1
        prev_attestation = get_valid_attestation(test_state, prev_slot_to_attest)
        fill_aggregate_attestation(test_state, prev_attestation)

        cur_slot_to_attest = test_state.slot - spec.MIN_ATTESTATION_INCLUSION_DELAY + 1
        cur_attestation = get_valid_attestation(test_state, cur_slot_to_attest)
        fill_aggregate_attestation(test_state, cur_attestation)

        block = build_empty_block_for_next_slot(test_state)
        block.body.attestations.append(prev_attestation)
        block.body.attestations.append(cur_attestation)

        state_transition(test_state, block)

        assert len(test_state.previous_epoch_attestations) >= 0
        assert len(test_state.current_epoch_attestations) >= 0

        blocks.append(block)
    check_finality(test_state, prev_state, True, True, True)

    return state, blocks, test_state
