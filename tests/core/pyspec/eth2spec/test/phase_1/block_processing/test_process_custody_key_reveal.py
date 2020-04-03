from eth2spec.test.helpers.custody import get_valid_custody_key_reveal
from eth2spec.test.context import (
    PHASE0,
    with_all_phases_except,
    spec_state_test,
    expect_assertion_error,
    always_bls,
)


def run_custody_key_reveal_processing(spec, state, custody_key_reveal, valid=True):
    """
    Run ``process_custody_key_reveal``, yielding:
      - pre-state ('pre')
      - custody_key_reveal ('custody_key_reveal')
      - post-state ('post').
    If ``valid == False``, run expecting ``AssertionError``
    """
    yield 'pre', state
    yield 'custody_key_reveal', custody_key_reveal

    if not valid:
        expect_assertion_error(lambda: spec.process_custody_key_reveal(state, custody_key_reveal))
        yield 'post', None
        return

    revealer_index = custody_key_reveal.revealer_index

    pre_next_custody_secret_to_reveal = \
        state.validators[revealer_index].next_custody_secret_to_reveal
    pre_reveal_lateness = state.validators[revealer_index].max_reveal_lateness

    spec.process_custody_key_reveal(state, custody_key_reveal)

    post_next_custody_secret_to_reveal = \
        state.validators[revealer_index].next_custody_secret_to_reveal
    post_reveal_lateness = state.validators[revealer_index].max_reveal_lateness

    assert post_next_custody_secret_to_reveal == pre_next_custody_secret_to_reveal + 1

    if spec.get_current_epoch(state) > spec.get_randao_epoch_for_custody_period(
        pre_next_custody_secret_to_reveal,
        revealer_index
    ) + spec.EPOCHS_PER_CUSTODY_PERIOD:
        assert post_reveal_lateness > 0
        if pre_reveal_lateness == 0:
            assert post_reveal_lateness == spec.get_current_epoch(state) - spec.get_randao_epoch_for_custody_period(
                pre_next_custody_secret_to_reveal,
                revealer_index
            ) - spec.EPOCHS_PER_CUSTODY_PERIOD
    else:
        if pre_reveal_lateness > 0:
            assert post_reveal_lateness < pre_reveal_lateness

    yield 'post', state


@with_all_phases_except([PHASE0])
@spec_state_test
@always_bls
def test_success(spec, state):
    state.slot += spec.EPOCHS_PER_CUSTODY_PERIOD * spec.SLOTS_PER_EPOCH
    custody_key_reveal = get_valid_custody_key_reveal(spec, state)

    yield from run_custody_key_reveal_processing(spec, state, custody_key_reveal)


@with_all_phases_except([PHASE0])
@spec_state_test
@always_bls
def test_reveal_too_early(spec, state):
    custody_key_reveal = get_valid_custody_key_reveal(spec, state)

    yield from run_custody_key_reveal_processing(spec, state, custody_key_reveal, False)


@with_all_phases_except([PHASE0])
@spec_state_test
@always_bls
def test_wrong_period(spec, state):
    custody_key_reveal = get_valid_custody_key_reveal(spec, state, period=5)

    yield from run_custody_key_reveal_processing(spec, state, custody_key_reveal, False)


@with_all_phases_except([PHASE0])
@spec_state_test
@always_bls
def test_late_reveal(spec, state):
    state.slot += spec.EPOCHS_PER_CUSTODY_PERIOD * spec.SLOTS_PER_EPOCH * 3 + 150
    custody_key_reveal = get_valid_custody_key_reveal(spec, state)

    yield from run_custody_key_reveal_processing(spec, state, custody_key_reveal)


@with_all_phases_except([PHASE0])
@spec_state_test
@always_bls
def test_double_reveal(spec, state):
    state.slot += spec.EPOCHS_PER_CUSTODY_PERIOD * spec.SLOTS_PER_EPOCH * 2
    custody_key_reveal = get_valid_custody_key_reveal(spec, state)

    _, _, _ = run_custody_key_reveal_processing(spec, state, custody_key_reveal)

    yield from run_custody_key_reveal_processing(spec, state, custody_key_reveal, False)


@with_all_phases_except([PHASE0])
@spec_state_test
@always_bls
def test_max_decrement(spec, state):
    state.slot += spec.EPOCHS_PER_CUSTODY_PERIOD * spec.SLOTS_PER_EPOCH * 3 + 150
    custody_key_reveal = get_valid_custody_key_reveal(spec, state)

    _, _, _ = run_custody_key_reveal_processing(spec, state, custody_key_reveal)

    custody_key_reveal2 = get_valid_custody_key_reveal(spec, state)

    yield from run_custody_key_reveal_processing(spec, state, custody_key_reveal2)
