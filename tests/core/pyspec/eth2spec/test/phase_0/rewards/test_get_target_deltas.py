from eth2spec.test.context import with_all_phases, spec_state_test
from eth2spec.test.helpers.rewards import run_attestation_component_deltas
import eth2spec.test.helpers.rewards as rewards_helpers


def run_get_target_deltas(spec, state):
    """
    Run ``get_target_deltas``, yielding:
      - pre-state ('pre')
      - rewards ('rewards')
      - penalties ('penalties')
    """

    yield from run_attestation_component_deltas(
        spec,
        state,
        spec.get_target_deltas,
        spec.get_matching_target_attestations,
    )


@with_all_phases
@spec_state_test
def test_empty(spec, state):
    yield from rewards_helpers.test_empty(spec, state, run_get_target_deltas)


@with_all_phases
@spec_state_test
def test_full_all_correct(spec, state):
    yield from rewards_helpers.test_full_all_correct(spec, state, run_get_target_deltas)


@with_all_phases
@spec_state_test
def test_half_full(spec, state):
    yield from rewards_helpers.test_half_full(spec, state, run_get_target_deltas)


@with_all_phases
@spec_state_test
def test_full_but_partial_participation(spec, state):
    yield from rewards_helpers.test_full_but_partial_participation(spec, state, run_get_target_deltas)


@with_all_phases
@spec_state_test
def test_one_attestation_one_correct(spec, state):
    yield from rewards_helpers.test_one_attestation_one_correct(spec, state, run_get_target_deltas)


@with_all_phases
@spec_state_test
def test_with_slashed_validators(spec, state):
    yield from rewards_helpers.test_with_slashed_validators(spec, state, run_get_target_deltas)


@with_all_phases
@spec_state_test
def test_some_very_low_effective_balances_that_attested(spec, state):
    yield from rewards_helpers.test_some_very_low_effective_balances_that_attested(spec, state, run_get_target_deltas)


@with_all_phases
@spec_state_test
def test_some_very_low_effective_balances_that_did_not_attest(spec, state):
    yield from rewards_helpers.test_some_very_low_effective_balances_that_did_not_attest(
        spec,
        state,
        run_get_target_deltas,
    )


@with_all_phases
@spec_state_test
def test_full_half_correct_target_incorrect_head(spec, state):
    yield from rewards_helpers.test_full_fraction_incorrect(
        spec, state,
        correct_target=True,
        correct_head=False,
        fraction_incorrect=0.5,
        runner=run_get_target_deltas
    )


@with_all_phases
@spec_state_test
def test_full_correct_target_incorrect_head(spec, state):
    yield from rewards_helpers.test_full_fraction_incorrect(
        spec, state,
        correct_target=True,
        correct_head=False,
        fraction_incorrect=1.0,
        runner=run_get_target_deltas
    )


@with_all_phases
@spec_state_test
def test_full_half_incorrect_target_incorrect_head(spec, state):
    yield from rewards_helpers.test_full_fraction_incorrect(
        spec, state,
        correct_target=False,
        correct_head=False,
        fraction_incorrect=0.5,
        runner=run_get_target_deltas
    )


@with_all_phases
@spec_state_test
def test_full_half_incorrect_target_correct_head(spec, state):
    yield from rewards_helpers.test_full_fraction_incorrect(
        spec, state,
        correct_target=False,
        correct_head=True,
        fraction_incorrect=0.5,
        runner=run_get_target_deltas
    )


@with_all_phases
@spec_state_test
def test_full_random(spec, state):
    yield from rewards_helpers.test_full_random(spec, state, run_get_target_deltas)
