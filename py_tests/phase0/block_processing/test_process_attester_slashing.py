from copy import deepcopy
import pytest

import eth2spec.phase0.spec as spec
from eth2spec.phase0.spec import (
    get_balance,
    get_beacon_proposer_index,
    process_attester_slashing,
)
from phase0.helpers import (
    get_valid_attester_slashing,
)

# mark entire file as 'attester_slashing'
pytestmark = pytest.mark.attester_slashings


def run_attester_slashing_processing(state, attester_slashing, valid=True):
    """
    Run ``process_attester_slashing`` returning the pre and post state.
    If ``valid == False``, run expecting ``AssertionError``
    """
    post_state = deepcopy(state)

    if not valid:
        with pytest.raises(AssertionError):
            process_attester_slashing(post_state, attester_slashing)
        return state, None

    process_attester_slashing(post_state, attester_slashing)

    slashed_index = attester_slashing.attestation_1.custody_bit_0_indices[0]
    slashed_validator = post_state.validator_registry[slashed_index]
    assert not slashed_validator.initiated_exit
    assert slashed_validator.slashed
    assert slashed_validator.exit_epoch < spec.FAR_FUTURE_EPOCH
    assert slashed_validator.withdrawable_epoch < spec.FAR_FUTURE_EPOCH
    # lost whistleblower reward
    assert (
        get_balance(post_state, slashed_index) <
        get_balance(state, slashed_index)
    )
    proposer_index = get_beacon_proposer_index(state, state.slot)
    # gained whistleblower reward
    assert (
        get_balance(post_state, proposer_index) >
        get_balance(state, proposer_index)
    )

    return state, post_state


def test_success_double(state):
    attester_slashing = get_valid_attester_slashing(state)

    pre_state, post_state = run_attester_slashing_processing(state, attester_slashing)

    return pre_state, attester_slashing, post_state


def test_success_surround(state):
    attester_slashing = get_valid_attester_slashing(state)

    # set attestion1 to surround attestation 2
    attester_slashing.attestation_1.data.source_epoch = attester_slashing.attestation_2.data.source_epoch - 1
    attester_slashing.attestation_1.data.slot = attester_slashing.attestation_2.data.slot + spec.SLOTS_PER_EPOCH

    pre_state, post_state = run_attester_slashing_processing(state, attester_slashing)

    return pre_state, attester_slashing, post_state


def test_same_data(state):
    attester_slashing = get_valid_attester_slashing(state)

    attester_slashing.attestation_1.data = attester_slashing.attestation_2.data

    pre_state, post_state = run_attester_slashing_processing(state, attester_slashing, False)

    return pre_state, attester_slashing, post_state


def test_no_double_or_surround(state):
    attester_slashing = get_valid_attester_slashing(state)

    attester_slashing.attestation_1.data.slot += spec.SLOTS_PER_EPOCH

    pre_state, post_state = run_attester_slashing_processing(state, attester_slashing, False)

    return pre_state, attester_slashing, post_state


def test_participants_already_slashed(state):
    attester_slashing = get_valid_attester_slashing(state)

    # set all indices to slashed
    attestation_1 = attester_slashing.attestation_1
    validator_indices = attestation_1.custody_bit_0_indices + attestation_1.custody_bit_1_indices
    for index in validator_indices:
        state.validator_registry[index].slashed = True

    pre_state, post_state = run_attester_slashing_processing(state, attester_slashing, False)

    return pre_state, attester_slashing, post_state


def test_custody_bit_0_and_1(state):
    attester_slashing = get_valid_attester_slashing(state)

    attester_slashing.attestation_1.custody_bit_1_indices = (
        attester_slashing.attestation_1.custody_bit_0_indices
    )
    pre_state, post_state = run_attester_slashing_processing(state, attester_slashing, False)

    return pre_state, attester_slashing, post_state
