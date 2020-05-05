from random import Random

from eth2spec.test.helpers.attestations import prepare_state_with_full_attestations
from eth2spec.utils.ssz.ssz_typing import Container, uint64, List


# HACK to get the generators outputting correctly
class Deltas(Container):
    delta_list: List[uint64, 2**30]


def has_enough_for_reward(spec, state, index):
    """
    Check if base_reward will be non-zero.

    At very low balances, it is possible for a validator have a positive effective_balance
    but a zero base reward.
    """
    return (
        state.validators[index].effective_balance * spec.BASE_REWARD_FACTOR
        > spec.integer_squareroot(spec.get_total_active_balance(state)) // spec.BASE_REWARDS_PER_EPOCH
    )


def run_attestation_component_deltas(spec, state, component_delta_fn, matching_att_fn):
    """
    Run ``component_delta_fn``, yielding:
      - pre-state ('pre')
      - rewards ('rewards')
      - penalties ('penalties')
    """
    yield 'pre', state

    rewards, penalties = component_delta_fn(state)

    yield 'rewards', Deltas(delta_list=rewards)
    yield 'penalties', Deltas(delta_list=penalties)

    matching_attestations = matching_att_fn(state, spec.get_previous_epoch(state))
    matching_indices = spec.get_unslashed_attesting_indices(state, matching_attestations)
    eligible_indices = spec.get_eligible_validator_indices(state)
    for index in range(len(state.validators)):
        if index not in eligible_indices:
            assert rewards[index] == 0
            assert penalties[index] == 0
            continue

        validator = state.validators[index]
        enough_for_reward = has_enough_for_reward(spec, state, index)
        if index in matching_indices and not validator.slashed:
            if enough_for_reward:
                assert rewards[index] > 0
            else:
                assert rewards[index] == 0
            assert penalties[index] == 0
        else:
            assert rewards[index] == 0
            if enough_for_reward:
                assert penalties[index] > 0
            else:
                assert penalties[index] == 0


def run_test_empty(spec, state, runner):
    # Do not add any attestations to state

    yield from runner(spec, state)


def run_test_full_all_correct(spec, state, runner):
    prepare_state_with_full_attestations(spec, state)

    yield from runner(spec, state)


def run_test_full_but_partial_participation(spec, state, runner, rng=Random(5522)):
    prepare_state_with_full_attestations(spec, state)

    for a in state.previous_epoch_attestations:
        a.aggregation_bits = [rng.choice([True, False]) for _ in a.aggregation_bits]

    yield from runner(spec, state)


def run_test_partial(spec, state, fraction_filled, runner):
    prepare_state_with_full_attestations(spec, state)

    # Remove portion of attestations
    num_attestations = int(len(state.previous_epoch_attestations) * fraction_filled)
    state.previous_epoch_attestations = state.previous_epoch_attestations[:num_attestations]

    yield from runner(spec, state)


def run_test_half_full(spec, state, runner):
    yield from run_test_partial(spec, state, 0.5, runner)


def run_test_one_attestation_one_correct(spec, state, runner):
    prepare_state_with_full_attestations(spec, state)

    # Remove all attestations except for the first one
    state.previous_epoch_attestations = state.previous_epoch_attestations[:1]

    yield from runner(spec, state)


def run_test_with_slashed_validators(spec, state, runner):
    prepare_state_with_full_attestations(spec, state)

    # Slash half of validators
    for validator in state.validators[:len(state.validators) // 2]:
        validator.slashed = True

    yield from runner(spec, state)


def run_test_some_very_low_effective_balances_that_attested(spec, state, runner):
    state.balances
    prepare_state_with_full_attestations(spec, state)

    # Set some balances to be very low (including 0)
    assert len(state.validators) >= 5
    for i, index in enumerate(range(5)):
        state.validators[index].effective_balance = i

    yield from runner(spec, state)


def run_test_some_very_low_effective_balances_that_did_not_attest(spec, state, runner):
    prepare_state_with_full_attestations(spec, state)

    # Remove attestation
    attestation = state.previous_epoch_attestations[0]
    state.previous_epoch_attestations = state.previous_epoch_attestations[1:]
    # Set removed indices effective balance to very low amount
    indices = spec.get_unslashed_attesting_indices(state, [attestation])
    for i, index in enumerate(indices):
        state.validators[index].effective_balance = i

    yield from runner(spec, state)


def run_test_full_fraction_incorrect(spec, state, correct_target, correct_head, fraction_incorrect, runner):
    prepare_state_with_full_attestations(spec, state)

    # Make fraction_incorrect of pending attestations have bad target/head as specified
    num_incorrect = int(fraction_incorrect * len(state.previous_epoch_attestations))
    for pending_attestation in state.previous_epoch_attestations[:num_incorrect]:
        if not correct_target:
            pending_attestation.data.target.root = b'\x55' * 32
        if not correct_head:
            pending_attestation.data.beacon_block_root = b'\x66' * 32

    yield from runner(spec, state)


def run_test_full_random(spec, state, runner, rng=Random(8020)):
    prepare_state_with_full_attestations(spec, state)

    for pending_attestation in state.previous_epoch_attestations:
        # ~1/3 have bad target
        if rng.randint(0, 2) == 0:
            pending_attestation.data.target.root = b'\x55' * 32
        # ~1/3 have bad head
        if rng.randint(0, 2) == 0:
            pending_attestation.data.beacon_block_root = b'\x66' * 32
        # ~50% participation
        pending_attestation.aggregation_bits = [rng.choice([True, False]) for _ in pending_attestation.aggregation_bits]
        # Random inclusion delay
        pending_attestation.inclusion_delay = rng.randint(1, spec.SLOTS_PER_EPOCH)

    yield from runner(spec, state)
