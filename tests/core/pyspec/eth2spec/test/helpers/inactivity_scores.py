from random import Random

from eth2spec.test.helpers.state import (
    next_epoch_via_block,
)


def randomize_inactivity_scores(spec, state, minimum=0, maximum=50000, rng=Random(4242)):
    state.inactivity_scores = [rng.randint(minimum, maximum) for _ in range(len(state.validators))]


def zero_inactivity_scores(spec, state, rng=None):
    state.inactivity_scores = [0] * len(state.validators)


def slash_some_validators_for_inactivity_scores_test(spec, state, rng=Random(40404040), fraction=0.25):
    """
    ``run_inactivity_scores_test`` runs at the next epoch from `state`.
    # We retrieve the proposer of this future state to avoid
    # accidentally slashing that validator
    """
    future_state = state.copy()
    next_epoch_via_block(spec, future_state)
    proposer_index = spec.get_beacon_proposer_index(future_state)
    selected_count = int(len(state.validators) * fraction)
    selected_indices = rng.sample(range(len(state.validators)), selected_count)
    if proposer_index in selected_indices:
        selected_indices.remove(proposer_index)
    for validator_index in selected_indices:
        spec.slash_validator(state, validator_index)

    return selected_indices
