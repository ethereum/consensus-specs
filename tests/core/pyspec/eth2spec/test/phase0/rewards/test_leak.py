import eth2spec.test.helpers.rewards as rewards_helpers
from eth2spec.test.context import spec_state_test, with_all_phases, with_phases
from eth2spec.test.helpers.constants import PHASE0
from eth2spec.test.helpers.rewards import leaking


@with_all_phases
@spec_state_test
@leaking()
def test_empty_leak(spec, state):
    yield from rewards_helpers.run_test_empty(spec, state)


@with_all_phases
@spec_state_test
@leaking()
def test_full_leak(spec, state):
    yield from rewards_helpers.run_test_full_all_correct(spec, state)


@with_all_phases
@spec_state_test
@leaking()
def test_half_full_leak(spec, state):
    yield from rewards_helpers.run_test_half_full(spec, state)


@with_all_phases
@spec_state_test
@leaking()
def test_quarter_full_leak(spec, state):
    yield from rewards_helpers.run_test_partial(spec, state, 0.25)


@with_all_phases
@spec_state_test
@leaking()
def test_full_but_partial_participation_leak(spec, state):
    yield from rewards_helpers.run_test_full_but_partial_participation(spec, state)


@with_phases([PHASE0])
@spec_state_test
@leaking()
def test_one_attestation_one_correct_leak(spec, state):
    yield from rewards_helpers.run_test_one_attestation_one_correct(spec, state)


@with_all_phases
@spec_state_test
@leaking()
def test_with_not_yet_activated_validators_leak(spec, state):
    yield from rewards_helpers.run_test_with_not_yet_activated_validators(spec, state)


@with_all_phases
@spec_state_test
@leaking()
def test_with_exited_validators_leak(spec, state):
    yield from rewards_helpers.run_test_with_exited_validators(spec, state)


@with_all_phases
@spec_state_test
@leaking()
def test_with_slashed_validators_leak(spec, state):
    yield from rewards_helpers.run_test_with_slashed_validators(spec, state)


@with_all_phases
@spec_state_test
@leaking()
def test_some_very_low_effective_balances_that_attested_leak(spec, state):
    yield from rewards_helpers.run_test_some_very_low_effective_balances_that_attested(spec, state)


@with_all_phases
@spec_state_test
@leaking()
def test_some_very_low_effective_balances_that_did_not_attest_leak(spec, state):
    yield from rewards_helpers.run_test_some_very_low_effective_balances_that_did_not_attest(
        spec, state
    )


#
# NOTE: No source incorrect tests
# All PendingAttestations in state have source validated
# We choose to keep this invariant in these tests to not force clients to test with degenerate states
#


@with_phases([PHASE0])
@spec_state_test
@leaking()
def test_full_half_correct_target_incorrect_head_leak(spec, state):
    yield from rewards_helpers.run_test_full_fraction_incorrect(
        spec,
        state,
        correct_target=True,
        correct_head=False,
        fraction_incorrect=0.5,
    )


@with_phases([PHASE0])
@spec_state_test
@leaking()
def test_full_correct_target_incorrect_head_leak(spec, state):
    yield from rewards_helpers.run_test_full_fraction_incorrect(
        spec,
        state,
        correct_target=True,
        correct_head=False,
        fraction_incorrect=1.0,
    )


@with_phases([PHASE0])
@spec_state_test
@leaking()
def test_full_half_incorrect_target_incorrect_head_leak(spec, state):
    yield from rewards_helpers.run_test_full_fraction_incorrect(
        spec,
        state,
        correct_target=False,
        correct_head=False,
        fraction_incorrect=0.5,
    )


@with_phases([PHASE0])
@spec_state_test
@leaking()
def test_full_half_incorrect_target_correct_head_leak(spec, state):
    yield from rewards_helpers.run_test_full_fraction_incorrect(
        spec,
        state,
        correct_target=False,
        correct_head=True,
        fraction_incorrect=0.5,
    )


@with_all_phases
@spec_state_test
@leaking()
def test_full_random_leak(spec, state):
    yield from rewards_helpers.run_test_full_random(spec, state)


@with_all_phases
@spec_state_test
@leaking(epochs=7)
def test_full_random_seven_epoch_leak(spec, state):
    yield from rewards_helpers.run_test_full_random(spec, state)


@with_all_phases
@spec_state_test
@leaking(epochs=10)
def test_full_random_ten_epoch_leak(spec, state):
    yield from rewards_helpers.run_test_full_random(spec, state)
