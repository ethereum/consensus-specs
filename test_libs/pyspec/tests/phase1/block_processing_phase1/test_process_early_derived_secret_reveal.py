from copy import deepcopy
import pytest

# mark entire file as 'randao_key_reveals'
pytestmark = pytest.mark.randao_key_reveals


def run_early_derived_secret_reveal_processing(state, randao_key_reveal, valid=True):
    """
    Run ``process_randao_key_reveal`` returning the pre and post state.
    If ``valid == False``, run expecting ``AssertionError``
    """
    post_state = deepcopy(state)

    if not valid:
        with pytest.raises(AssertionError):
            spec.process_early_derived_secret_reveal(post_state, randao_key_reveal)
        return state, None

    spec.process_early_derived_secret_reveal(post_state, randao_key_reveal)

    slashed_validator = post_state.validator_registry[randao_key_reveal.revealed_index]

    if randao_key_reveal.epoch >= spec.get_current_epoch(state) + spec.CUSTODY_PERIOD_TO_RANDAO_PADDING:
        assert slashed_validator.slashed
        assert slashed_validator.exit_epoch < spec.FAR_FUTURE_EPOCH
        assert slashed_validator.withdrawable_epoch < spec.FAR_FUTURE_EPOCH
    # lost whistleblower reward
    # FIXME: Currently broken because get_base_reward in genesis epoch is 0
    assert (
        post_state.balances[randao_key_reveal.revealed_index] <
        state.balances[randao_key_reveal.revealed_index]
    )

    return state, post_state


def test_success(state):
    randao_key_reveal = helpers.get_valid_early_derived_secret_reveal(state)

    pre_state, post_state = run_early_derived_secret_reveal_processing(state, randao_key_reveal)

    return pre_state, randao_key_reveal, post_state


def test_reveal_from_current_epoch(state):
    randao_key_reveal = helpers.get_valid_early_derived_secret_reveal(state, spec.get_current_epoch(state))

    pre_state, post_state = run_early_derived_secret_reveal_processing(state, randao_key_reveal, False)

    return pre_state, randao_key_reveal, post_state


@pytest.mark.skip(reason="Not currently possible as we are testing at epoch 0")
def test_reveal_from_past_epoch(state):
    randao_key_reveal = helpers.get_valid_early_derived_secret_reveal(state, spec.get_current_epoch(state) - 1)

    pre_state, post_state = run_early_derived_secret_reveal_processing(state, randao_key_reveal, False)

    return pre_state, randao_key_reveal, post_state


def test_reveal_with_custody_padding(state):
    randao_key_reveal = helpers.get_valid_early_derived_secret_reveal(
        state,
        spec.get_current_epoch(state) + spec.CUSTODY_PERIOD_TO_RANDAO_PADDING,
    )
    pre_state, post_state = run_early_derived_secret_reveal_processing(state, randao_key_reveal, True)

    return pre_state, randao_key_reveal, post_state


def test_reveal_with_custody_padding_minus_one(state):
    randao_key_reveal = helpers.get_valid_early_derived_secret_reveal(
        state,
        spec.get_current_epoch(state) + spec.CUSTODY_PERIOD_TO_RANDAO_PADDING - 1,
    )
    pre_state, post_state = run_early_derived_secret_reveal_processing(state, randao_key_reveal, True)

    return pre_state, randao_key_reveal, post_state


def test_double_reveal(state):
    randao_key_reveal1 = helpers.get_valid_early_derived_secret_reveal(
        state,
        spec.get_current_epoch(state) + spec.RANDAO_PENALTY_EPOCHS + 1,
    )
    pre_state, intermediate_state = run_early_derived_secret_reveal_processing(state, randao_key_reveal1)

    randao_key_reveal2 = helpers.get_valid_early_derived_secret_reveal(
        intermediate_state,
        spec.get_current_epoch(pre_state) + spec.RANDAO_PENALTY_EPOCHS + 1,
    )
    _, post_state = run_early_derived_secret_reveal_processing(intermediate_state, randao_key_reveal2, False)

    return pre_state, [randao_key_reveal1, randao_key_reveal2], post_state


def test_revealer_is_slashed(state):
    randao_key_reveal = helpers.get_valid_early_derived_secret_reveal(state, spec.get_current_epoch(state))
    state.validator_registry[randao_key_reveal.revealed_index].slashed = True

    pre_state, post_state = run_early_derived_secret_reveal_processing(state, randao_key_reveal, False)

    return pre_state, randao_key_reveal, post_state


def test_far_future_epoch(state):
    randao_key_reveal = helpers.get_valid_early_derived_secret_reveal(
        state,
        spec.get_current_epoch(state) + spec.EARLY_DERIVED_SECRET_PENALTY_MAX_FUTURE_EPOCHS,
    )

    pre_state, post_state = run_early_derived_secret_reveal_processing(state, randao_key_reveal, False)

    return pre_state, randao_key_reveal, post_state
