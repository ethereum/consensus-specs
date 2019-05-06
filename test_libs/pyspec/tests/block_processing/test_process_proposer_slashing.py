import pytest

import eth2spec.phase0.spec as spec
from eth2spec.phase0.spec import (
    get_current_epoch,
    process_proposer_slashing,
)
from tests.helpers import (
    get_balance,
    get_valid_proposer_slashing,
)

from .block_test_helpers import spec_state_test


def run_proposer_slashing_processing(state, proposer_slashing, valid=True):
    """
    Run ``process_proposer_slashing``, yielding:
      - pre-state ('pre')
      - proposer_slashing ('proposer_slashing')
      - post-state ('post').
    If ``valid == False``, run expecting ``AssertionError``
    """
    pre_proposer_balance = get_balance(state, proposer_slashing.proposer_index)

    yield 'pre', state
    yield 'proposer_slashing', proposer_slashing

    if not valid:
        with pytest.raises(AssertionError):
            process_proposer_slashing(state, proposer_slashing)
        yield 'post', None
        return

    process_proposer_slashing(state, proposer_slashing)
    yield 'post', state

    # check if slashed
    slashed_validator = state.validator_registry[proposer_slashing.proposer_index]
    assert slashed_validator.slashed
    assert slashed_validator.exit_epoch < spec.FAR_FUTURE_EPOCH
    assert slashed_validator.withdrawable_epoch < spec.FAR_FUTURE_EPOCH

    # lost whistleblower reward
    assert (
        get_balance(state, proposer_slashing.proposer_index) <
        pre_proposer_balance
    )


@spec_state_test
def test_success(state):
    proposer_slashing = get_valid_proposer_slashing(state)

    yield from run_proposer_slashing_processing(state, proposer_slashing)


@spec_state_test
def test_epochs_are_different(state):
    proposer_slashing = get_valid_proposer_slashing(state)

    # set slots to be in different epochs
    proposer_slashing.header_2.slot += spec.SLOTS_PER_EPOCH

    yield from run_proposer_slashing_processing(state, proposer_slashing, False)


@spec_state_test
def test_headers_are_same(state):
    proposer_slashing = get_valid_proposer_slashing(state)

    # set headers to be the same
    proposer_slashing.header_2 = proposer_slashing.header_1

    yield from run_proposer_slashing_processing(state, proposer_slashing, False)


@spec_state_test
def test_proposer_is_slashed(state):
    proposer_slashing = get_valid_proposer_slashing(state)

    # set proposer to slashed
    state.validator_registry[proposer_slashing.proposer_index].slashed = True

    yield from run_proposer_slashing_processing(state, proposer_slashing, False)


@spec_state_test
def test_proposer_is_withdrawn(state):
    proposer_slashing = get_valid_proposer_slashing(state)

    # set proposer withdrawable_epoch in past
    current_epoch = get_current_epoch(state)
    proposer_index = proposer_slashing.proposer_index
    state.validator_registry[proposer_index].withdrawable_epoch = current_epoch - 1

    yield from run_proposer_slashing_processing(state, proposer_slashing, False)
