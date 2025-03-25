from eth2spec.test.context import with_all_phases, with_phases, spec_state_test
from eth2spec.test.helpers.constants import PHASE0
import eth2spec.test.helpers.rewards as rewards_helpers


@with_all_phases
@spec_state_test
def test_empty(spec, state):
    yield from rewards_helpers.run_test_empty(spec, state)


@with_all_phases
@spec_state_test
def test_full_all_correct(spec, state):
    yield from rewards_helpers.run_test_full_all_correct(spec, state)


@with_all_phases
@spec_state_test
def test_half_full(spec, state):
    yield from rewards_helpers.run_test_half_full(spec, state)


@with_all_phases
@spec_state_test
def test_quarter_full(spec, state):
    yield from rewards_helpers.run_test_partial(spec, state, 0.25)


@with_all_phases
@spec_state_test
def test_full_but_partial_participation(spec, state):
    yield from rewards_helpers.run_test_full_but_partial_participation(spec, state)


@with_phases([PHASE0])
@spec_state_test
def test_one_attestation_one_correct(spec, state):
    yield from rewards_helpers.run_test_one_attestation_one_correct(spec, state)


@with_all_phases
@spec_state_test
def test_with_not_yet_activated_validators(spec, state):
    yield from rewards_helpers.run_test_with_not_yet_activated_validators(spec, state)


@with_all_phases
@spec_state_test
def test_with_exited_validators(spec, state):
    yield from rewards_helpers.run_test_with_exited_validators(spec, state)


@with_all_phases
@spec_state_test
def test_with_slashed_validators(spec, state):
    yield from rewards_helpers.run_test_with_slashed_validators(spec, state)


@with_all_phases
@spec_state_test
def test_some_very_low_effective_balances_that_attested(spec, state):
    yield from rewards_helpers.run_test_some_very_low_effective_balances_that_attested(
        spec, state
    )


@with_all_phases
@spec_state_test
def test_some_very_low_effective_balances_that_did_not_attest(spec, state):
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
def test_full_half_correct_target_incorrect_head(spec, state):
    yield from rewards_helpers.run_test_full_fraction_incorrect(
        spec,
        state,
        correct_target=True,
        correct_head=False,
        fraction_incorrect=0.5,
    )


@with_phases([PHASE0])
@spec_state_test
def test_full_correct_target_incorrect_head(spec, state):
    yield from rewards_helpers.run_test_full_fraction_incorrect(
        spec,
        state,
        correct_target=True,
        correct_head=False,
        fraction_incorrect=1.0,
    )


@with_phases([PHASE0])
@spec_state_test
def test_full_half_incorrect_target_incorrect_head(spec, state):
    yield from rewards_helpers.run_test_full_fraction_incorrect(
        spec,
        state,
        correct_target=False,
        correct_head=False,
        fraction_incorrect=0.5,
    )


@with_phases([PHASE0])
@spec_state_test
def test_full_half_incorrect_target_correct_head(spec, state):
    yield from rewards_helpers.run_test_full_fraction_incorrect(
        spec,
        state,
        correct_target=False,
        correct_head=True,
        fraction_incorrect=0.5,
    )


@with_phases([PHASE0])
@spec_state_test
def test_full_delay_one_slot(spec, state):
    yield from rewards_helpers.run_test_full_delay_one_slot(spec, state)


@with_phases([PHASE0])
@spec_state_test
def test_full_delay_max_slots(spec, state):
    yield from rewards_helpers.run_test_full_delay_max_slots(spec, state)


@with_phases([PHASE0])
@spec_state_test
def test_full_mixed_delay(spec, state):
    yield from rewards_helpers.run_test_full_mixed_delay(spec, state)


@with_phases([PHASE0])
@spec_state_test
def test_proposer_not_in_attestations(spec, state):
    yield from rewards_helpers.run_test_proposer_not_in_attestations(spec, state)


@with_phases([PHASE0])
@spec_state_test
def test_duplicate_attestations_at_later_slots(spec, state):
    yield from rewards_helpers.run_test_duplicate_attestations_at_later_slots(
        spec, state
    )


@with_all_phases
@spec_state_test
def test_all_balances_too_low_for_reward(spec, state):
    yield from rewards_helpers.run_test_all_balances_too_low_for_reward(spec, state)
