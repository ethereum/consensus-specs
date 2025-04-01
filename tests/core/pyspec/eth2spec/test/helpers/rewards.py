from random import Random
from lru import LRU

from eth2spec.phase0.mainnet import VALIDATOR_REGISTRY_LIMIT  # equal everywhere, fine to import
from eth2spec.test.helpers.forks import is_post_altair, is_post_bellatrix
from eth2spec.test.helpers.state import (
    next_epoch,
)
from eth2spec.test.helpers.random import (
    set_some_new_deposits, exit_random_validators, slash_random_validators,
    randomize_state,
)
from eth2spec.test.helpers.attestations import (
    cached_prepare_state_with_attestations,
)
from eth2spec.utils.ssz.ssz_typing import Container, uint64, List


class Deltas(Container):
    rewards: List[uint64, VALIDATOR_REGISTRY_LIMIT]
    penalties: List[uint64, VALIDATOR_REGISTRY_LIMIT]


def get_inactivity_penalty_quotient(spec):
    if is_post_bellatrix(spec):
        return spec.INACTIVITY_PENALTY_QUOTIENT_BELLATRIX
    elif is_post_altair(spec):
        return spec.INACTIVITY_PENALTY_QUOTIENT_ALTAIR
    else:
        return spec.INACTIVITY_PENALTY_QUOTIENT


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


def has_enough_for_leak_penalty(spec, state, index):
    """
    Check if effective_balance and state of leak is high enough for a leak penalty.

    At very low balances / leak values, it is possible for a validator have a positive effective_balance
    and be in a leak, but have zero leak penalty.
    """

    if is_post_altair(spec):
        return (
            state.validators[index].effective_balance * state.inactivity_scores[index]
            > spec.config.INACTIVITY_SCORE_BIAS * get_inactivity_penalty_quotient(spec)
        )
    else:
        return (
            state.validators[index].effective_balance * spec.get_finality_delay(state)
            > spec.INACTIVITY_PENALTY_QUOTIENT
        )


def run_deltas(spec, state):
    """
    Run all deltas functions yielding:
      - pre-state ('pre')
      - source deltas ('source_deltas')
      - target deltas ('target_deltas')
      - head deltas ('head_deltas')
      - not if is_post_altair(spec)
          - inclusion delay deltas ('inclusion_delay_deltas')
      - inactivity penalty deltas ('inactivity_penalty_deltas')
    """
    yield 'pre', state

    if is_post_altair(spec):
        def get_source_deltas(state):
            return spec.get_flag_index_deltas(state, spec.TIMELY_SOURCE_FLAG_INDEX)

        def get_head_deltas(state):
            return spec.get_flag_index_deltas(state, spec.TIMELY_HEAD_FLAG_INDEX)

        def get_target_deltas(state):
            return spec.get_flag_index_deltas(state, spec.TIMELY_TARGET_FLAG_INDEX)

    yield from run_attestation_component_deltas(
        spec,
        state,
        spec.get_source_deltas if not is_post_altair(spec) else get_source_deltas,
        spec.get_matching_source_attestations,
        'source_deltas',
    )
    yield from run_attestation_component_deltas(
        spec,
        state,
        spec.get_target_deltas if not is_post_altair(spec) else get_target_deltas,
        spec.get_matching_target_attestations,
        'target_deltas',
    )
    yield from run_attestation_component_deltas(
        spec,
        state,
        spec.get_head_deltas if not is_post_altair(spec) else get_head_deltas,
        spec.get_matching_head_attestations,
        'head_deltas',
    )
    if not is_post_altair(spec):
        yield from run_get_inclusion_delay_deltas(spec, state)
    yield from run_get_inactivity_penalty_deltas(spec, state)


def deltas_name_to_flag_index(spec, deltas_name):
    if 'source' in deltas_name:
        return spec.TIMELY_SOURCE_FLAG_INDEX
    elif 'head' in deltas_name:
        return spec.TIMELY_HEAD_FLAG_INDEX
    elif 'target' in deltas_name:
        return spec.TIMELY_TARGET_FLAG_INDEX
    raise ValueError("Wrong deltas_name %s" % deltas_name)


def run_attestation_component_deltas(spec, state, component_delta_fn, matching_att_fn, deltas_name):
    """
    Run ``component_delta_fn``, yielding:
      - deltas ('{``deltas_name``}')
    """
    rewards, penalties = component_delta_fn(state)

    yield deltas_name, Deltas(rewards=rewards, penalties=penalties)

    if not is_post_altair(spec):
        matching_attestations = matching_att_fn(state, spec.get_previous_epoch(state))
        matching_indices = spec.get_unslashed_attesting_indices(state, matching_attestations)
    else:
        matching_indices = spec.get_unslashed_participating_indices(
            state, deltas_name_to_flag_index(spec, deltas_name), spec.get_previous_epoch(state)
        )

    eligible_indices = spec.get_eligible_validator_indices(state)
    for index in range(len(state.validators)):
        if index not in eligible_indices:
            assert rewards[index] == 0
            assert penalties[index] == 0
            continue

        validator = state.validators[index]
        enough_for_reward = has_enough_for_reward(spec, state, index)
        if index in matching_indices and not validator.slashed:
            if is_post_altair(spec):
                if not spec.is_in_inactivity_leak(state) and enough_for_reward:
                    assert rewards[index] > 0
                else:
                    assert rewards[index] == 0
            else:
                if enough_for_reward:
                    assert rewards[index] > 0
                else:
                    assert rewards[index] == 0

            assert penalties[index] == 0
        else:
            assert rewards[index] == 0
            if is_post_altair(spec) and 'head' in deltas_name:
                assert penalties[index] == 0
            elif enough_for_reward:
                assert penalties[index] > 0
            else:
                assert penalties[index] == 0


def run_get_inclusion_delay_deltas(spec, state):
    """
    Run ``get_inclusion_delay_deltas``, yielding:
      - inclusion delay deltas ('inclusion_delay_deltas')
    """
    if is_post_altair(spec):
        # No inclusion_delay_deltas
        yield 'inclusion_delay_deltas', Deltas(rewards=[0] * len(state.validators),
                                               penalties=[0] * len(state.validators))
        return

    rewards, penalties = spec.get_inclusion_delay_deltas(state)

    yield 'inclusion_delay_deltas', Deltas(rewards=rewards, penalties=penalties)

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
                if index in spec.get_attesting_indices(state, a)
            ], key=lambda a: a.inclusion_delay)
            rewarded_proposer_indices.add(earliest_attestation.proposer_index)

    # Ensure all expected proposers have been rewarded
    # Track reward indices
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


def run_get_inactivity_penalty_deltas(spec, state):
    """
    Run ``get_inactivity_penalty_deltas``, yielding:
      - inactivity penalty deltas ('inactivity_penalty_deltas')
    """
    rewards, penalties = spec.get_inactivity_penalty_deltas(state)

    yield 'inactivity_penalty_deltas', Deltas(rewards=rewards, penalties=penalties)

    if not is_post_altair(spec):
        matching_attestations = spec.get_matching_target_attestations(state, spec.get_previous_epoch(state))
        matching_attesting_indices = spec.get_unslashed_attesting_indices(state, matching_attestations)
    else:
        matching_attesting_indices = spec.get_unslashed_participating_indices(
            state, spec.TIMELY_TARGET_FLAG_INDEX, spec.get_previous_epoch(state)
        )

    eligible_indices = spec.get_eligible_validator_indices(state)
    for index in range(len(state.validators)):
        assert rewards[index] == 0
        if index not in eligible_indices:
            assert penalties[index] == 0
            continue

        if spec.is_in_inactivity_leak(state):
            # Compute base_penalty
            base_reward = spec.get_base_reward(state, index)
            if not is_post_altair(spec):
                cancel_base_rewards_per_epoch = spec.BASE_REWARDS_PER_EPOCH
                base_penalty = cancel_base_rewards_per_epoch * base_reward - spec.get_proposer_reward(state, index)

            if not has_enough_for_reward(spec, state, index):
                assert penalties[index] == 0
            elif index in matching_attesting_indices or not has_enough_for_leak_penalty(spec, state, index):
                if is_post_altair(spec):
                    assert penalties[index] == 0
                else:
                    assert penalties[index] == base_penalty
            else:
                if is_post_altair(spec):
                    assert penalties[index] > 0
                else:
                    assert penalties[index] > base_penalty
        else:
            if not is_post_altair(spec):
                assert penalties[index] == 0
                continue
            else:
                # post altair, this penalty is derived from the inactivity score
                # regardless if the state is leaking or not...
                if index in matching_attesting_indices:
                    assert penalties[index] == 0
                else:
                    # copied from spec:
                    penalty_numerator = state.validators[index].effective_balance * state.inactivity_scores[index]
                    penalty_denominator = spec.config.INACTIVITY_SCORE_BIAS * get_inactivity_penalty_quotient(spec)
                    assert penalties[index] == penalty_numerator // penalty_denominator


def transition_state_to_leak(spec, state, epochs=None):
    if epochs is None:
        # +2 because finality delay is based on previous_epoch and must be more than `MIN_EPOCHS_TO_INACTIVITY_PENALTY`
        epochs = spec.MIN_EPOCHS_TO_INACTIVITY_PENALTY + 2
    assert epochs > spec.MIN_EPOCHS_TO_INACTIVITY_PENALTY

    for _ in range(epochs):
        next_epoch(spec, state)
    assert spec.is_in_inactivity_leak(state)


_cache_dict = LRU(size=10)


def leaking(epochs=None):
    def deco(fn):
        def entry(*args, spec, state, **kw):
            # If the pre-state is not already known in the LRU, then take it,
            # transition it to leak, and put it in the LRU.
            # The input state is likely already cached, so the hash-tree-root does not affect speed.
            key = (state.hash_tree_root(), spec.MIN_EPOCHS_TO_INACTIVITY_PENALTY, spec.SLOTS_PER_EPOCH, epochs)
            if key not in _cache_dict:
                transition_state_to_leak(spec, state, epochs=epochs)
                _cache_dict[key] = state.get_backing()  # cache the tree structure, not the view wrapping it.

            # Take an entry out of the LRU.
            # No copy is necessary, as we wrap the immutable backing with a new view.
            state = spec.BeaconState(backing=_cache_dict[key])
            return fn(*args, spec=spec, state=state, **kw)
        return entry
    return deco


def run_test_empty(spec, state):
    # Do not add any attestations to state

    yield from run_deltas(spec, state)


def run_test_full_all_correct(spec, state):
    cached_prepare_state_with_attestations(spec, state)

    yield from run_deltas(spec, state)


def run_test_full_but_partial_participation(spec, state, rng=Random(5522)):
    cached_prepare_state_with_attestations(spec, state)

    if not is_post_altair(spec):
        for a in state.previous_epoch_attestations:
            a.aggregation_bits = [rng.choice([True, False]) for _ in a.aggregation_bits]
    else:
        for index in range(len(state.validators)):
            if rng.choice([True, False]):
                state.previous_epoch_participation[index] = spec.ParticipationFlags(0b0000_0000)

    yield from run_deltas(spec, state)


def run_test_partial(spec, state, fraction_filled):
    cached_prepare_state_with_attestations(spec, state)

    # Remove portion of attestations
    if not is_post_altair(spec):
        num_attestations = int(len(state.previous_epoch_attestations) * fraction_filled)
        state.previous_epoch_attestations = state.previous_epoch_attestations[:num_attestations]
    else:
        for index in range(int(len(state.validators) * fraction_filled)):
            state.previous_epoch_participation[index] = spec.ParticipationFlags(0b0000_0000)

    yield from run_deltas(spec, state)


def run_test_half_full(spec, state):
    yield from run_test_partial(spec, state, 0.5)


def run_test_one_attestation_one_correct(spec, state):
    cached_prepare_state_with_attestations(spec, state)

    # Remove all attestations except for the first one
    state.previous_epoch_attestations = state.previous_epoch_attestations[:1]

    yield from run_deltas(spec, state)


def run_test_with_not_yet_activated_validators(spec, state, rng=Random(5555)):
    set_some_new_deposits(spec, state, rng)
    cached_prepare_state_with_attestations(spec, state)

    yield from run_deltas(spec, state)


def run_test_with_exited_validators(spec, state, rng=Random(1337)):
    exit_random_validators(spec, state, rng)
    cached_prepare_state_with_attestations(spec, state)

    yield from run_deltas(spec, state)


def run_test_with_slashed_validators(spec, state, rng=Random(3322)):
    exit_random_validators(spec, state, rng)
    slash_random_validators(spec, state, rng)

    cached_prepare_state_with_attestations(spec, state)

    yield from run_deltas(spec, state)


def run_test_some_very_low_effective_balances_that_attested(spec, state):
    cached_prepare_state_with_attestations(spec, state)

    # Set some balances to be very low (including 0)
    assert len(state.validators) >= 5
    for i, index in enumerate(range(5)):
        state.validators[index].effective_balance = i

    yield from run_deltas(spec, state)


def run_test_some_very_low_effective_balances_that_did_not_attest(spec, state):
    cached_prepare_state_with_attestations(spec, state)

    if not is_post_altair(spec):
        # Remove attestation
        attestation = state.previous_epoch_attestations[0]
        state.previous_epoch_attestations = state.previous_epoch_attestations[1:]
        # Set removed indices effective balance to very low amount
        indices = spec.get_unslashed_attesting_indices(state, [attestation])
        for i, index in enumerate(indices):
            state.validators[index].effective_balance = i
    else:
        index = 0
        state.validators[index].effective_balance = 1
        state.previous_epoch_participation[index] = spec.ParticipationFlags(0b0000_0000)

    yield from run_deltas(spec, state)


def run_test_full_fraction_incorrect(spec, state, correct_target, correct_head, fraction_incorrect):
    cached_prepare_state_with_attestations(spec, state)

    # Make fraction_incorrect of pending attestations have bad target/head as specified
    num_incorrect = int(fraction_incorrect * len(state.previous_epoch_attestations))
    for pending_attestation in state.previous_epoch_attestations[:num_incorrect]:
        if not correct_target:
            pending_attestation.data.target.root = b'\x55' * 32
        if not correct_head:
            pending_attestation.data.beacon_block_root = b'\x66' * 32

    yield from run_deltas(spec, state)


def run_test_full_delay_one_slot(spec, state):
    cached_prepare_state_with_attestations(spec, state)
    for a in state.previous_epoch_attestations:
        a.inclusion_delay += 1

    yield from run_deltas(spec, state)


def run_test_full_delay_max_slots(spec, state):
    cached_prepare_state_with_attestations(spec, state)
    for a in state.previous_epoch_attestations:
        a.inclusion_delay += spec.SLOTS_PER_EPOCH

    yield from run_deltas(spec, state)


def run_test_full_mixed_delay(spec, state, rng=Random(1234)):
    cached_prepare_state_with_attestations(spec, state)
    for a in state.previous_epoch_attestations:
        a.inclusion_delay = rng.randint(1, spec.SLOTS_PER_EPOCH)

    yield from run_deltas(spec, state)


def run_test_proposer_not_in_attestations(spec, state):
    cached_prepare_state_with_attestations(spec, state)

    # Get an attestation where the proposer is not in the committee
    non_proposer_attestations = []
    for a in state.previous_epoch_attestations:
        if a.proposer_index not in spec.get_unslashed_attesting_indices(state, [a]):
            non_proposer_attestations.append(a)

    assert any(non_proposer_attestations)
    state.previous_epoch_attestations = non_proposer_attestations

    yield from run_deltas(spec, state)


def run_test_duplicate_attestations_at_later_slots(spec, state):
    cached_prepare_state_with_attestations(spec, state)

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

    yield from run_deltas(spec, state)


def run_test_all_balances_too_low_for_reward(spec, state):
    cached_prepare_state_with_attestations(spec, state)

    for index in range(len(state.validators)):
        state.validators[index].effective_balance = 10

    yield from run_deltas(spec, state)


def run_test_full_random(spec, state, rng=Random(8020)):
    randomize_state(spec, state, rng)
    yield from run_deltas(spec, state)
