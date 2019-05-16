from copy import deepcopy
import pytest


# mark entire file as 'proposer_slashings'
pytestmark = pytest.mark.proposer_slashings


def run_proposer_slashing_processing(spec, helpers, state, proposer_slashing, valid=True):
    """
    Run ``spec.process_proposer_slashing`` returning the pre and post state.
    If ``valid == False``, run expecting ``AssertionError``
    """
    post_state = deepcopy(state)

    if not valid:
        with pytest.raises(AssertionError):
            spec.process_proposer_slashing(post_state, proposer_slashing)
        return state, None

    spec.process_proposer_slashing(post_state, proposer_slashing)

    slashed_validator = post_state.validator_registry[proposer_slashing.proposer_index]
    assert slashed_validator.slashed
    assert slashed_validator.exit_epoch < spec.FAR_FUTURE_EPOCH
    assert slashed_validator.withdrawable_epoch < spec.FAR_FUTURE_EPOCH
    # lost whistleblower reward
    assert (
        helpers.get_balance(post_state, proposer_slashing.proposer_index) <
        helpers.get_balance(state, proposer_slashing.proposer_index)
    )

    return state, post_state


def test_success(spec, helpers, state):
    proposer_slashing = helpers.get_valid_proposer_slashing(state)

    pre_state, post_state = run_proposer_slashing_processing(spec, helpers, state, proposer_slashing)

    return pre_state, proposer_slashing, post_state


def test_epochs_are_different(spec, helpers, state):
    proposer_slashing = helpers.get_valid_proposer_slashing(state)

    # set slots to be in different epochs
    proposer_slashing.header_2.slot += spec.SLOTS_PER_EPOCH

    pre_state, post_state = run_proposer_slashing_processing(spec, helpers, state, proposer_slashing, False)

    return pre_state, proposer_slashing, post_state


def test_headers_are_same(spec, helpers, state):
    proposer_slashing = helpers.get_valid_proposer_slashing(state)

    # set headers to be the same
    proposer_slashing.header_2 = proposer_slashing.header_1

    pre_state, post_state = run_proposer_slashing_processing(spec, helpers, state, proposer_slashing, False)

    return pre_state, proposer_slashing, post_state


def test_proposer_is_slashed(spec, helpers, state):
    proposer_slashing = helpers.get_valid_proposer_slashing(state)

    # set proposer to slashed
    state.validator_registry[proposer_slashing.proposer_index].slashed = True

    pre_state, post_state = run_proposer_slashing_processing(spec, helpers, state, proposer_slashing, False)

    return pre_state, proposer_slashing, post_state


def test_proposer_is_withdrawn(spec, helpers, state):
    proposer_slashing = helpers.get_valid_proposer_slashing(state)

    # set proposer withdrawable_epoch in past
    current_epoch = spec.get_current_epoch(state)
    proposer_index = proposer_slashing.proposer_index
    state.validator_registry[proposer_index].withdrawable_epoch = current_epoch - 1

    pre_state, post_state = run_proposer_slashing_processing(spec, helpers, state, proposer_slashing, False)

    return pre_state, proposer_slashing, post_state
