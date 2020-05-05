from eth2spec.test.context import with_all_phases, spec_state_test
from eth2spec.test.helpers.rewards import has_enough_for_reward
from eth2spec.test.helpers.state import next_epoch
import eth2spec.test.helpers.rewards as rewards_helpers
from eth2spec.utils.ssz.ssz_typing import Container, uint64, List


# HACK to get the generators outputting correctly
class Deltas(Container):
    delta_list: List[uint64, 2**30]


def run_get_inactivity_penalty_deltas(spec, state):
    """
    Run ``get_inactivity_penalty_deltas``, yielding:
      - pre-state ('pre')
      - rewards ('rewards')
      - penalties ('penalties')
    """

    yield 'pre', state

    rewards, penalties = spec.get_inactivity_penalty_deltas(state)

    yield 'rewards', Deltas(delta_list=rewards)
    yield 'penalties', Deltas(delta_list=penalties)

    matching_attestations = spec.get_matching_target_attestations(state, spec.get_previous_epoch(state))
    matching_attesting_indices = spec.get_unslashed_attesting_indices(state, matching_attestations)

    finality_delay = spec.get_previous_epoch(state) - state.finalized_checkpoint.epoch
    eligible_indices = spec.get_eligible_validator_indices(state)
    for index in range(len(state.validators)):
        assert rewards[index] == 0
        if index not in eligible_indices:
            assert penalties[index] == 0
            continue

        if finality_delay > spec.MIN_EPOCHS_TO_INACTIVITY_PENALTY:
            base_penalty = spec.BASE_REWARDS_PER_EPOCH * spec.get_base_reward(state, index)
            if not has_enough_for_reward(spec, state, index):
                assert penalties[index] == 0
            elif index in matching_attesting_indices:
                assert penalties[index] == base_penalty
            else:
                assert penalties[index] > base_penalty
        else:
            assert penalties[index] == 0


def transition_state_to_leak(spec, state, epochs=None):
    if epochs is None:
        epochs = spec.MIN_EPOCHS_TO_INACTIVITY_PENALTY
    assert epochs >= spec.MIN_EPOCHS_TO_INACTIVITY_PENALTY

    for _ in range(epochs):
        next_epoch(spec, state)


@with_all_phases
@spec_state_test
def test_empty_no_leak(spec, state):
    yield from rewards_helpers.run_test_empty(spec, state, run_get_inactivity_penalty_deltas)


@with_all_phases
@spec_state_test
def test_empty_leak(spec, state):
    transition_state_to_leak(spec, state)
    yield from rewards_helpers.run_test_empty(spec, state, run_get_inactivity_penalty_deltas)


@with_all_phases
@spec_state_test
def test_full_no_leak(spec, state):
    yield from rewards_helpers.run_test_full_all_correct(spec, state, run_get_inactivity_penalty_deltas)


@with_all_phases
@spec_state_test
def test_full_leak(spec, state):
    transition_state_to_leak(spec, state)
    yield from rewards_helpers.run_test_full_all_correct(spec, state, run_get_inactivity_penalty_deltas)


@with_all_phases
@spec_state_test
def test_half_full_no_leak(spec, state):
    yield from rewards_helpers.run_test_half_full(spec, state, run_get_inactivity_penalty_deltas)


@with_all_phases
@spec_state_test
def test_half_full_leak(spec, state):
    transition_state_to_leak(spec, state)
    yield from rewards_helpers.run_test_half_full(spec, state, run_get_inactivity_penalty_deltas)


@with_all_phases
@spec_state_test
def test_quarter_full_no_leak(spec, state):
    yield from rewards_helpers.run_test_partial(spec, state, 0.25, run_get_inactivity_penalty_deltas)


@with_all_phases
@spec_state_test
def test_quarter_full_leak(spec, state):
    transition_state_to_leak(spec, state)
    yield from rewards_helpers.run_test_partial(spec, state, 0.25, run_get_inactivity_penalty_deltas)


@with_all_phases
@spec_state_test
def test_full_but_partial_participation_no_leak(spec, state):
    yield from rewards_helpers.run_test_full_but_partial_participation(spec, state, run_get_inactivity_penalty_deltas)


@with_all_phases
@spec_state_test
def test_full_but_partial_participation_leak(spec, state):
    transition_state_to_leak(spec, state)
    yield from rewards_helpers.run_test_full_but_partial_participation(spec, state, run_get_inactivity_penalty_deltas)


@with_all_phases
@spec_state_test
def test_with_slashed_validators_no_leak(spec, state):
    yield from rewards_helpers.run_test_with_slashed_validators(spec, state, run_get_inactivity_penalty_deltas)


@with_all_phases
@spec_state_test
def test_with_slashed_validators_leak(spec, state):
    transition_state_to_leak(spec, state)
    yield from rewards_helpers.run_test_with_slashed_validators(spec, state, run_get_inactivity_penalty_deltas)


@with_all_phases
@spec_state_test
def test_some_very_low_effective_balances_that_attested_no_leak(spec, state):
    yield from rewards_helpers.run_test_some_very_low_effective_balances_that_attested(
        spec,
        state,
        run_get_inactivity_penalty_deltas,
    )


@with_all_phases
@spec_state_test
def test_some_very_low_effective_balances_that_attested_leak(spec, state):
    transition_state_to_leak(spec, state)
    yield from rewards_helpers.run_test_some_very_low_effective_balances_that_attested(
        spec,
        state,
        run_get_inactivity_penalty_deltas,
    )


@with_all_phases
@spec_state_test
def test_some_very_low_effective_balances_that_did_not_attest_no_leak(spec, state):
    yield from rewards_helpers.run_test_some_very_low_effective_balances_that_did_not_attest(
        spec,
        state,
        run_get_inactivity_penalty_deltas,
    )


@with_all_phases
@spec_state_test
def test_some_very_low_effective_balances_that_did_not_attest_leak(spec, state):
    transition_state_to_leak(spec, state)
    yield from rewards_helpers.run_test_some_very_low_effective_balances_that_did_not_attest(
        spec,
        state,
        run_get_inactivity_penalty_deltas,
    )


@with_all_phases
@spec_state_test
def test_full_random_no_leak(spec, state):
    yield from rewards_helpers.run_test_full_random(spec, state, run_get_inactivity_penalty_deltas)


@with_all_phases
@spec_state_test
def test_full_random_leak(spec, state):
    transition_state_to_leak(spec, state)
    yield from rewards_helpers.run_test_full_random(spec, state, run_get_inactivity_penalty_deltas)


@with_all_phases
@spec_state_test
def test_full_random_five_epoch_leak(spec, state):
    transition_state_to_leak(spec, state, epochs=5)
    yield from rewards_helpers.run_test_full_random(spec, state, run_get_inactivity_penalty_deltas)


@with_all_phases
@spec_state_test
def test_full_random_ten_epoch_leak(spec, state):
    transition_state_to_leak(spec, state, epochs=10)
    yield from rewards_helpers.run_test_full_random(spec, state, run_get_inactivity_penalty_deltas)
