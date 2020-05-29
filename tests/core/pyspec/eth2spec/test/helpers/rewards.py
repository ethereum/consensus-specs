from random import Random
from lru import LRU

from eth2spec.phase0 import spec as spec_phase0
from eth2spec.test.helpers.attestations import cached_prepare_state_with_attestations
from eth2spec.test.helpers.deposits import mock_deposit
from eth2spec.test.helpers.state import next_epoch
from eth2spec.utils.ssz.ssz_typing import Container, uint64, List


class Deltas(Container):
    rewards: List[uint64, spec_phase0.VALIDATOR_REGISTRY_LIMIT]
    penalties: List[uint64, spec_phase0.VALIDATOR_REGISTRY_LIMIT]


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


def run_deltas(spec, state):
    """
    Run all deltas functions yielding:
      - pre-state ('pre')
      - source deltas ('source_deltas')
      - target deltas ('target_deltas')
      - head deltas ('head_deltas')
      - inclusion delay deltas ('inclusion_delay_deltas')
      - inactivity penalty deltas ('inactivity_penalty_deltas')
    """
    yield 'pre', state
    yield from run_attestation_component_deltas(
        spec,
        state,
        spec.get_source_deltas,
        spec.get_matching_source_attestations,
        'source_deltas',
    )
    yield from run_attestation_component_deltas(
        spec,
        state,
        spec.get_target_deltas,
        spec.get_matching_target_attestations,
        'target_deltas',
    )
    yield from run_attestation_component_deltas(
        spec,
        state,
        spec.get_head_deltas,
        spec.get_matching_head_attestations,
        'head_deltas',
    )
    yield from run_get_inclusion_delay_deltas(spec, state)
    yield from run_get_inactivity_penalty_deltas(spec, state)


def run_attestation_component_deltas(spec, state, component_delta_fn, matching_att_fn, deltas_name):
    """
    Run ``component_delta_fn``, yielding:
      - deltas ('{``deltas_name``}')
    """
    rewards, penalties = component_delta_fn(state)

    yield deltas_name, Deltas(rewards=rewards, penalties=penalties)

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


def run_get_inclusion_delay_deltas(spec, state):
    """
    Run ``get_inclusion_delay_deltas``, yielding:
      - inclusion delay deltas ('inclusion_delay_deltas')
    """
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


def run_get_inactivity_penalty_deltas(spec, state):
    """
    Run ``get_inactivity_penalty_deltas``, yielding:
      - inactivity penalty deltas ('inactivity_penalty_deltas')
    """
    rewards, penalties = spec.get_inactivity_penalty_deltas(state)

    yield 'inactivity_penalty_deltas', Deltas(rewards=rewards, penalties=penalties)

    matching_attestations = spec.get_matching_target_attestations(state, spec.get_previous_epoch(state))
    matching_attesting_indices = spec.get_unslashed_attesting_indices(state, matching_attestations)

    eligible_indices = spec.get_eligible_validator_indices(state)
    for index in range(len(state.validators)):
        assert rewards[index] == 0
        if index not in eligible_indices:
            assert penalties[index] == 0
            continue

        if spec.is_in_inactivity_leak(state):
            base_reward = spec.get_base_reward(state, index)
            base_penalty = spec.BASE_REWARDS_PER_EPOCH * base_reward - spec.get_proposer_reward(state, index)
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


_cache_dict = LRU(size=10)


def leaking(epochs=None):

    def deco(fn):
        def entry(*args, spec, state, **kw):
            # If the pre-state is not already known in the LRU, then take it,
            # transition it to leak, and put it in the LRU.
            # The input state is likely already cached, so the hash-tree-root does not affect speed.
            key = (state.hash_tree_root(), spec.MIN_EPOCHS_TO_INACTIVITY_PENALTY, spec.SLOTS_PER_EPOCH, epochs)
            global _cache_dict
            if key not in _cache_dict:
                transition_state_to_leak(spec, state, epochs=epochs)
                _cache_dict[key] = state.get_backing()  # cache the tree structure, not the view wrapping it.

            # Take an entry out of the LRU.
            # No copy is necessary, as we wrap the immutable backing with a new view.
            state = spec.BeaconState(backing=_cache_dict[key])
            return fn(*args, spec=spec, state=state, **kw)
        return entry
    return deco


def set_some_new_deposits(spec, state, rng):
    num_validators = len(state.validators)
    # Set ~1/10 to just recently deposited
    for index in range(num_validators):
        # If not already active, skip
        if not spec.is_active_validator(state.validators[index], spec.get_current_epoch(state)):
            continue
        if rng.randrange(num_validators) < num_validators // 10:
            mock_deposit(spec, state, index)
            # Set ~half of selected to eligible for activation
            if rng.choice([True, False]):
                state.validators[index].activation_eligibility_epoch = spec.get_current_epoch(state)


def exit_random_validators(spec, state, rng):
    if spec.get_current_epoch(state) < 5:
        # Move epochs forward to allow for some validators already exited/withdrawable
        for _ in range(5):
            next_epoch(spec, state)

    current_epoch = spec.get_current_epoch(state)
    # Exit ~1/2 of validators
    for index in spec.get_active_validator_indices(state, current_epoch):
        if rng.choice([True, False]):
            continue

        validator = state.validators[index]
        validator.exit_epoch = rng.choice([current_epoch - 1, current_epoch - 2, current_epoch - 3])
        # ~1/2 are withdrawable
        if rng.choice([True, False]):
            validator.withdrawable_epoch = current_epoch
        else:
            validator.withdrawable_epoch = current_epoch + 1


def slash_random_validators(spec, state, rng):
    # Slash ~1/2 of validators
    for index in range(len(state.validators)):
        # slash at least one validator
        if index == 0 or rng.choice([True, False]):
            spec.slash_validator(state, index)


def run_test_empty(spec, state):
    # Do not add any attestations to state

    yield from run_deltas(spec, state)


def run_test_full_all_correct(spec, state):
    cached_prepare_state_with_attestations(spec, state)

    yield from run_deltas(spec, state)


def run_test_full_but_partial_participation(spec, state, rng=Random(5522)):
    cached_prepare_state_with_attestations(spec, state)

    for a in state.previous_epoch_attestations:
        a.aggregation_bits = [rng.choice([True, False]) for _ in a.aggregation_bits]

    yield from run_deltas(spec, state)


def run_test_partial(spec, state, fraction_filled):
    cached_prepare_state_with_attestations(spec, state)

    # Remove portion of attestations
    num_attestations = int(len(state.previous_epoch_attestations) * fraction_filled)
    state.previous_epoch_attestations = state.previous_epoch_attestations[:num_attestations]

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

    # Remove attestation
    attestation = state.previous_epoch_attestations[0]
    state.previous_epoch_attestations = state.previous_epoch_attestations[1:]
    # Set removed indices effective balance to very low amount
    indices = spec.get_unslashed_attesting_indices(state, [attestation])
    for i, index in enumerate(indices):
        state.validators[index].effective_balance = i

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
    set_some_new_deposits(spec, state, rng)
    exit_random_validators(spec, state, rng)
    slash_random_validators(spec, state, rng)

    cached_prepare_state_with_attestations(spec, state)

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

    yield from run_deltas(spec, state)
