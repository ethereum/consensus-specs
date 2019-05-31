from eth2spec.test.helpers.custody import get_valid_early_derived_secret_reveal
from eth2spec.test.context import with_phase1, spec_state_test, expect_assertion_error


def run_early_derived_secret_reveal_processing(spec, state, randao_key_reveal, valid=True):
    """
    Run ``process_randao_key_reveal``, yielding:
      - pre-state ('pre')
      - randao_key_reveal ('randao_key_reveal')
      - post-state ('post').
    If ``valid == False``, run expecting ``AssertionError``
    """
    yield 'pre', state
    yield 'randao_key_reveal', randao_key_reveal

    if not valid:
        expect_assertion_error(lambda: spec.process_early_derived_secret_reveal(state, randao_key_reveal))
        yield 'post', None
        return

    spec.process_early_derived_secret_reveal(state, randao_key_reveal)

    slashed_validator = state.validator_registry[randao_key_reveal.revealed_index]

    if randao_key_reveal.epoch >= spec.get_current_epoch(state) + spec.CUSTODY_PERIOD_TO_RANDAO_PADDING:
        assert slashed_validator.slashed
        assert slashed_validator.exit_epoch < spec.FAR_FUTURE_EPOCH
        assert slashed_validator.withdrawable_epoch < spec.FAR_FUTURE_EPOCH
    # lost whistleblower reward
    # FIXME: Currently broken because get_base_reward in genesis epoch is 0
    # assert (
    #     state.balances[randao_key_reveal.revealed_index] <
    #     state.balances[randao_key_reveal.revealed_index]
    # )
    yield 'post', state


@with_phase1
@spec_state_test
def test_success(spec, state):
    randao_key_reveal = get_valid_early_derived_secret_reveal(spec, state)

    yield from run_early_derived_secret_reveal_processing(spec, state, randao_key_reveal)


@with_phase1
@spec_state_test
def test_reveal_from_current_epoch(spec, state):
    randao_key_reveal = get_valid_early_derived_secret_reveal(spec, state, spec.get_current_epoch(state))

    yield from run_early_derived_secret_reveal_processing(spec, state, randao_key_reveal, False)


# @with_phase1
# @spec_state_test
# def test_reveal_from_past_epoch(state):
#     randao_key_reveal = get_valid_early_derived_secret_reveal(spec, state, spec.get_current_epoch(state) - 1)
#     
#     yield from run_early_derived_secret_reveal_processing(spec, state, randao_key_reveal, False)


@with_phase1
@spec_state_test
def test_reveal_with_custody_padding(spec, state):
    randao_key_reveal = get_valid_early_derived_secret_reveal(
        spec,
        state,
        spec.get_current_epoch(state) + spec.CUSTODY_PERIOD_TO_RANDAO_PADDING,
    )
    yield from run_early_derived_secret_reveal_processing(spec, state, randao_key_reveal, True)


@with_phase1
@spec_state_test
def test_reveal_with_custody_padding_minus_one(spec, state):
    randao_key_reveal = get_valid_early_derived_secret_reveal(
        spec,
        state,
        spec.get_current_epoch(state) + spec.CUSTODY_PERIOD_TO_RANDAO_PADDING - 1,
    )
    yield from run_early_derived_secret_reveal_processing(spec, state, randao_key_reveal, True)


@with_phase1
@spec_state_test
def test_double_reveal(spec, state):
    randao_key_reveal1 = get_valid_early_derived_secret_reveal(
        spec,
        state,
        spec.get_current_epoch(state) + spec.RANDAO_PENALTY_EPOCHS + 1,
    )
    res = dict(run_early_derived_secret_reveal_processing(spec, state, randao_key_reveal1))
    pre_state = res['pre']
    yield 'pre', pre_state
    intermediate_state = res['post']

    randao_key_reveal2 = get_valid_early_derived_secret_reveal(
        spec,
        intermediate_state,
        spec.get_current_epoch(pre_state) + spec.RANDAO_PENALTY_EPOCHS + 1,
    )
    post_state = dict(run_early_derived_secret_reveal_processing(spec, intermediate_state, randao_key_reveal2, False))['post']
    yield 'randao_key_reveal', [randao_key_reveal1, randao_key_reveal2]
    yield 'post', post_state


@with_phase1
@spec_state_test
def test_revealer_is_slashed(spec, state):
    randao_key_reveal = get_valid_early_derived_secret_reveal(spec, state, spec.get_current_epoch(state))
    state.validator_registry[randao_key_reveal.revealed_index].slashed = True

    yield from run_early_derived_secret_reveal_processing(spec, state, randao_key_reveal, False)


@with_phase1
@spec_state_test
def test_far_future_epoch(spec, state):
    randao_key_reveal = get_valid_early_derived_secret_reveal(
        spec,
        state,
        spec.get_current_epoch(state) + spec.EARLY_DERIVED_SECRET_PENALTY_MAX_FUTURE_EPOCHS,
    )

    yield from run_early_derived_secret_reveal_processing(spec, state, randao_key_reveal, False)
