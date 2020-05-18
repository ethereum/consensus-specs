from random import Random

from eth2spec.test.context import with_all_phases, spec_state_test
from eth2spec.test.helpers.attestations import prepare_state_with_attestations
from eth2spec.test.helpers.rewards import Deltas, has_enough_for_reward
import eth2spec.test.helpers.rewards as rewards_helpers


def run_get_inclusion_delay_deltas(spec, state):
    """
    Run ``get_inclusion_delay_deltas``, yielding:
      - pre-state ('pre')
      - deltas ('deltas')
    """

    yield 'pre', state

    rewards, penalties = spec.get_inclusion_delay_deltas(state)

    yield 'deltas', Deltas(rewards=rewards, penalties=penalties)

    eligible_attestations = spec.get_matching_source_attestations(state, spec.get_previous_epoch(state))
    attesting_indices = spec.get_unslashed_attesting_indices(state, eligible_attestations)

    rewarded_indices = set()
    rewarded_proposer_indices = set()
    # Ensure attesters with enough balance are rewarded for attestations
    # Track those that are rewarded and track proposers that should be rewarded
    for index in range(len(state.validators)):
        if index in attesting_indices and has_enough_for_reward(spec, state, index):
            assert rewards[index] > 0
            rewarded_indices.add(index)

            # Track proposer of earliest included attestation for the validator defined by index
            earliest_attestation = min([
                a for a in eligible_attestations
                if index in spec.get_attesting_indices(state, a.data, a.aggregation_bits)
            ], key=lambda a: a.inclusion_delay)
            rewarded_proposer_indices.add(earliest_attestation.proposer_index)

    # Ensure all expected proposers have been rewarded
    # Track rewarde indices
    proposing_indices = [a.proposer_index for a in eligible_attestations]
    for index in proposing_indices:
        if index in rewarded_proposer_indices:
            assert rewards[index] > 0
            rewarded_indices.add(index)

    # Ensure all expected non-rewarded indices received no reward
    for index in range(len(state.validators)):
        assert penalties[index] == 0
        if index not in rewarded_indices:
            assert rewards[index] == 0


@with_all_phases
@spec_state_test
def test_empty(spec, state):
    yield from rewards_helpers.run_test_empty(spec, state, run_get_inclusion_delay_deltas)


@with_all_phases
@spec_state_test
def test_full(spec, state):
    yield from rewards_helpers.run_test_full_all_correct(spec, state, run_get_inclusion_delay_deltas)


@with_all_phases
@spec_state_test
def test_half_full(spec, state):
    yield from rewards_helpers.run_test_half_full(spec, state, run_get_inclusion_delay_deltas)


@with_all_phases
@spec_state_test
def test_quarter_full(spec, state):
    yield from rewards_helpers.run_test_partial(spec, state, 0.25, run_get_inclusion_delay_deltas)


@with_all_phases
@spec_state_test
def test_full_but_partial_participation(spec, state):
    yield from rewards_helpers.run_test_full_but_partial_participation(spec, state, run_get_inclusion_delay_deltas)


@with_all_phases
@spec_state_test
def test_with_not_yet_activated_validators(spec, state):
    yield from rewards_helpers.run_test_with_not_yet_activated_validators(spec, state, run_get_inclusion_delay_deltas)


@with_all_phases
@spec_state_test
def test_with_exited_validators(spec, state):
    yield from rewards_helpers.run_test_with_exited_validators(spec, state, run_get_inclusion_delay_deltas)


@with_all_phases
@spec_state_test
def test_with_slashed_validators(spec, state):
    yield from rewards_helpers.run_test_with_slashed_validators(spec, state, run_get_inclusion_delay_deltas)


@with_all_phases
@spec_state_test
def test_some_very_low_effective_balances_that_attested(spec, state):
    yield from rewards_helpers.run_test_some_very_low_effective_balances_that_attested(
        spec,
        state,
        run_get_inclusion_delay_deltas
    )


@with_all_phases
@spec_state_test
def test_full_random(spec, state):
    yield from rewards_helpers.run_test_full_random(spec, state, run_get_inclusion_delay_deltas)


@with_all_phases
@spec_state_test
def test_full_delay_one_slot(spec, state):
    prepare_state_with_attestations(spec, state)
    for a in state.previous_epoch_attestations:
        a.inclusion_delay += 1

    yield from run_get_inclusion_delay_deltas(spec, state)


@with_all_phases
@spec_state_test
def test_full_delay_max_slots(spec, state):
    prepare_state_with_attestations(spec, state)
    for a in state.previous_epoch_attestations:
        a.inclusion_delay += spec.SLOTS_PER_EPOCH

    yield from run_get_inclusion_delay_deltas(spec, state)


@with_all_phases
@spec_state_test
def test_full_mixed_delay(spec, state):
    rng = Random(1234)

    prepare_state_with_attestations(spec, state)
    for a in state.previous_epoch_attestations:
        a.inclusion_delay = rng.randint(1, spec.SLOTS_PER_EPOCH)

    yield from run_get_inclusion_delay_deltas(spec, state)


@with_all_phases
@spec_state_test
def test_proposer_not_in_attestations(spec, state):
    prepare_state_with_attestations(spec, state)

    # Get an attestation where the proposer is not in the committee
    non_proposer_attestations = []
    for a in state.previous_epoch_attestations:
        if a.proposer_index not in spec.get_unslashed_attesting_indices(state, [a]):
            non_proposer_attestations.append(a)

    assert any(non_proposer_attestations)
    state.previous_epoch_attestations = non_proposer_attestations

    yield from run_get_inclusion_delay_deltas(spec, state)


@with_all_phases
@spec_state_test
def test_duplicate_attestations_at_later_slots(spec, state):
    prepare_state_with_attestations(spec, state)

    # Remove 2/3 of attestations to make it more interesting
    num_attestations = int(len(state.previous_epoch_attestations) * 0.33)
    state.previous_epoch_attestations = state.previous_epoch_attestations[:num_attestations]

    # Get map of the proposer at each slot to make valid-looking duplicate attestations
    per_slot_proposers = {
        (a.data.slot + a.inclusion_delay): a.proposer_index
        for a in state.previous_epoch_attestations
    }
    max_slot = max([a.data.slot + a.inclusion_delay for a in state.previous_epoch_attestations])
    later_attestations = []
    for a in state.previous_epoch_attestations:
        # Only have proposers for previous epoch so do not create later
        # duplicate if slot exceeds the max slot in previous_epoch_attestations
        if a.data.slot + a.inclusion_delay >= max_slot:
            continue
        later_a = a.copy()
        later_a.inclusion_delay += 1
        later_a.proposer_index = per_slot_proposers[later_a.data.slot + later_a.inclusion_delay]
        later_attestations.append(later_a)

    assert any(later_attestations)

    state.previous_epoch_attestations = sorted(
        state.previous_epoch_attestations + later_attestations,
        key=lambda a: a.data.slot + a.inclusion_delay
    )

    yield from run_get_inclusion_delay_deltas(spec, state)


@with_all_phases
@spec_state_test
def test_all_balances_too_low_for_reward(spec, state):
    prepare_state_with_attestations(spec, state)

    for index in range(len(state.validators)):
        state.validators[index].effective_balance = 10

    yield from run_get_inclusion_delay_deltas(spec, state)
