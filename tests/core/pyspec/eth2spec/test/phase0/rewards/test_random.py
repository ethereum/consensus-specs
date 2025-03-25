from random import Random

from eth2spec.test.context import (
    with_all_phases,
    spec_test,
    spec_state_test,
    with_custom_state,
    single_phase,
    low_balances,
    misc_balances,
)
import eth2spec.test.helpers.rewards as rewards_helpers
from eth2spec.test.helpers.random import (
    randomize_state,
    patch_state_to_non_leaking,
    randomize_attestation_participation,
)
from eth2spec.test.helpers.state import has_active_balance_differential, next_epoch
from eth2spec.test.helpers.voluntary_exits import get_unslashed_exited_validators


@with_all_phases
@spec_state_test
def test_full_random_0(spec, state):
    yield from rewards_helpers.run_test_full_random(spec, state, rng=Random(1010))


@with_all_phases
@spec_state_test
def test_full_random_1(spec, state):
    yield from rewards_helpers.run_test_full_random(spec, state, rng=Random(2020))


@with_all_phases
@spec_state_test
def test_full_random_2(spec, state):
    yield from rewards_helpers.run_test_full_random(spec, state, rng=Random(3030))


@with_all_phases
@spec_state_test
def test_full_random_3(spec, state):
    yield from rewards_helpers.run_test_full_random(spec, state, rng=Random(4040))


@with_all_phases
@spec_state_test
def test_full_random_4(spec, state):
    """
    Ensure a rewards test with some exited (but not slashed) validators.
    """
    rng = Random(5050)
    randomize_state(spec, state, rng)
    assert spec.is_in_inactivity_leak(state)
    target_validators = get_unslashed_exited_validators(spec, state)
    assert len(target_validators) != 0
    assert has_active_balance_differential(spec, state)
    yield from rewards_helpers.run_deltas(spec, state)


@with_all_phases
@with_custom_state(balances_fn=low_balances, threshold_fn=lambda spec: spec.config.EJECTION_BALANCE)
@spec_test
@single_phase
def test_full_random_low_balances_0(spec, state):
    yield from rewards_helpers.run_test_full_random(spec, state, rng=Random(5050))


@with_all_phases
@with_custom_state(balances_fn=low_balances, threshold_fn=lambda spec: spec.config.EJECTION_BALANCE)
@spec_test
@single_phase
def test_full_random_low_balances_1(spec, state):
    yield from rewards_helpers.run_test_full_random(spec, state, rng=Random(6060))


@with_all_phases
@with_custom_state(
    balances_fn=misc_balances, threshold_fn=lambda spec: spec.config.EJECTION_BALANCE
)
@spec_test
@single_phase
def test_full_random_misc_balances(spec, state):
    yield from rewards_helpers.run_test_full_random(spec, state, rng=Random(7070))


@with_all_phases
@spec_state_test
def test_full_random_without_leak_0(spec, state):
    rng = Random(1010)
    randomize_state(spec, state, rng)
    assert spec.is_in_inactivity_leak(state)
    patch_state_to_non_leaking(spec, state)
    assert not spec.is_in_inactivity_leak(state)
    target_validators = get_unslashed_exited_validators(spec, state)
    assert len(target_validators) != 0
    assert has_active_balance_differential(spec, state)
    yield from rewards_helpers.run_deltas(spec, state)


@with_all_phases
@spec_state_test
def test_full_random_without_leak_and_current_exit_0(spec, state):
    """
    This test specifically ensures a validator exits in the current epoch
    to ensure rewards are handled properly in this case.
    """
    rng = Random(1011)
    randomize_state(spec, state, rng)
    assert spec.is_in_inactivity_leak(state)
    patch_state_to_non_leaking(spec, state)
    assert not spec.is_in_inactivity_leak(state)
    target_validators = get_unslashed_exited_validators(spec, state)
    assert len(target_validators) != 0

    # move forward some epochs to process attestations added
    # by ``randomize_state`` before we exit validators in
    # what will be the current epoch
    for _ in range(2):
        next_epoch(spec, state)

    current_epoch = spec.get_current_epoch(state)
    for index in target_validators:
        # patch exited validators to exit in the current epoch
        validator = state.validators[index]
        validator.exit_epoch = current_epoch
        validator.withdrawable_epoch = (
            current_epoch + spec.config.MIN_VALIDATOR_WITHDRAWABILITY_DELAY
        )

    # re-randomize attestation participation for the current epoch
    randomize_attestation_participation(spec, state, rng)

    assert has_active_balance_differential(spec, state)
    yield from rewards_helpers.run_deltas(spec, state)
