from eth2spec.test._deprecated.helpers.custody import get_valid_early_derived_secret_reveal
from eth2spec.test.helpers.state import next_epoch_via_block, get_balance
from eth2spec.test.context import (
    with_phases,
    spec_state_test,
    expect_assertion_error,
    always_bls,
    never_bls,
)
from eth2spec.test.helpers.typing import SpecForkName

CUSTODY_GAME = SpecForkName("custody_game")


def run_early_derived_secret_reveal_processing(spec, state, randao_key_reveal, valid=True):
    """
    Run ``process_randao_key_reveal``, yielding:
      - pre-state ('pre')
      - randao_key_reveal ('randao_key_reveal')
      - post-state ('post').
    If ``valid == False``, run expecting ``AssertionError``
    """
    yield "pre", state
    yield "randao_key_reveal", randao_key_reveal

    if not valid:
        expect_assertion_error(
            lambda: spec.process_early_derived_secret_reveal(state, randao_key_reveal)
        )
        yield "post", None
        return

    pre_slashed_balance = get_balance(state, randao_key_reveal.revealed_index)

    spec.process_early_derived_secret_reveal(state, randao_key_reveal)

    slashed_validator = state.validators[randao_key_reveal.revealed_index]

    if (
        randao_key_reveal.epoch
        >= spec.get_current_epoch(state) + spec.CUSTODY_PERIOD_TO_RANDAO_PADDING
    ):
        assert slashed_validator.slashed
        assert slashed_validator.exit_epoch < spec.FAR_FUTURE_EPOCH
        assert slashed_validator.withdrawable_epoch < spec.FAR_FUTURE_EPOCH

    assert get_balance(state, randao_key_reveal.revealed_index) < pre_slashed_balance
    yield "post", state


@with_phases([CUSTODY_GAME])
@spec_state_test
@always_bls
def test_success(spec, state):
    randao_key_reveal = get_valid_early_derived_secret_reveal(spec, state)

    yield from run_early_derived_secret_reveal_processing(spec, state, randao_key_reveal)


@with_phases([CUSTODY_GAME])
@spec_state_test
@never_bls
def test_reveal_from_current_epoch(spec, state):
    randao_key_reveal = get_valid_early_derived_secret_reveal(
        spec, state, spec.get_current_epoch(state)
    )

    yield from run_early_derived_secret_reveal_processing(spec, state, randao_key_reveal, False)


@with_phases([CUSTODY_GAME])
@spec_state_test
@never_bls
def test_reveal_from_past_epoch(spec, state):
    next_epoch_via_block(spec, state)
    randao_key_reveal = get_valid_early_derived_secret_reveal(
        spec, state, spec.get_current_epoch(state) - 1
    )

    yield from run_early_derived_secret_reveal_processing(spec, state, randao_key_reveal, False)


@with_phases([CUSTODY_GAME])
@spec_state_test
@always_bls
def test_reveal_with_custody_padding(spec, state):
    randao_key_reveal = get_valid_early_derived_secret_reveal(
        spec,
        state,
        spec.get_current_epoch(state) + spec.CUSTODY_PERIOD_TO_RANDAO_PADDING,
    )
    yield from run_early_derived_secret_reveal_processing(spec, state, randao_key_reveal, True)


@with_phases([CUSTODY_GAME])
@spec_state_test
@always_bls
def test_reveal_with_custody_padding_minus_one(spec, state):
    randao_key_reveal = get_valid_early_derived_secret_reveal(
        spec,
        state,
        spec.get_current_epoch(state) + spec.CUSTODY_PERIOD_TO_RANDAO_PADDING - 1,
    )
    yield from run_early_derived_secret_reveal_processing(spec, state, randao_key_reveal, True)


@with_phases([CUSTODY_GAME])
@spec_state_test
@never_bls
def test_double_reveal(spec, state):
    epoch = spec.get_current_epoch(state) + spec.RANDAO_PENALTY_EPOCHS
    randao_key_reveal1 = get_valid_early_derived_secret_reveal(
        spec,
        state,
        epoch,
    )
    _, _, _ = dict(run_early_derived_secret_reveal_processing(spec, state, randao_key_reveal1))

    randao_key_reveal2 = get_valid_early_derived_secret_reveal(
        spec,
        state,
        epoch,
    )

    yield from run_early_derived_secret_reveal_processing(spec, state, randao_key_reveal2, False)


@with_phases([CUSTODY_GAME])
@spec_state_test
@never_bls
def test_revealer_is_slashed(spec, state):
    randao_key_reveal = get_valid_early_derived_secret_reveal(
        spec, state, spec.get_current_epoch(state)
    )
    state.validators[randao_key_reveal.revealed_index].slashed = True

    yield from run_early_derived_secret_reveal_processing(spec, state, randao_key_reveal, False)


@with_phases([CUSTODY_GAME])
@spec_state_test
@never_bls
def test_far_future_epoch(spec, state):
    randao_key_reveal = get_valid_early_derived_secret_reveal(
        spec,
        state,
        spec.get_current_epoch(state) + spec.EARLY_DERIVED_SECRET_PENALTY_MAX_FUTURE_EPOCHS,
    )

    yield from run_early_derived_secret_reveal_processing(spec, state, randao_key_reveal, False)
