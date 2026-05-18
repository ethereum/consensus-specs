from random import Random

from eth_consensus_specs.test.context import spec_state_test, with_all_phases
from eth_consensus_specs.test.helpers.epoch_processing import (
    run_epoch_processing_to,
    run_epoch_processing_with,
)
from eth_consensus_specs.test.helpers.forks import (
    is_post_altair,
    is_post_bellatrix,
    is_post_electra,
)
from eth_consensus_specs.test.helpers.random import randomize_state
from eth_consensus_specs.test.helpers.state import has_active_balance_differential, next_epoch
from eth_consensus_specs.test.helpers.voluntary_exits import get_unslashed_exited_validators


def run_process_slashings(spec, state):
    yield from run_epoch_processing_with(spec, state, "process_slashings")


def slash_validators(spec, state, indices, out_epochs):
    total_slashed_balance = 0
    for i, out_epoch in zip(indices, out_epochs):
        v = state.validators[i]
        v.slashed = True
        spec.initiate_validator_exit(state, i)
        v.withdrawable_epoch = out_epoch
        total_slashed_balance += v.effective_balance

    state.slashings[spec.get_current_epoch(state) % spec.EPOCHS_PER_SLASHINGS_VECTOR] = (
        total_slashed_balance
    )

    # verify some slashings happened...
    assert total_slashed_balance != 0


def get_slashing_multiplier(spec):
    if is_post_bellatrix(spec):
        return spec.PROPORTIONAL_SLASHING_MULTIPLIER_BELLATRIX
    elif is_post_altair(spec):
        return spec.PROPORTIONAL_SLASHING_MULTIPLIER_ALTAIR
    else:
        return spec.PROPORTIONAL_SLASHING_MULTIPLIER


def _compute_expected_correlation_penalty(
    spec, effective_balance, total_slashed_balance, total_balance
):
    if is_post_electra(spec):
        return (
            (get_slashing_multiplier(spec) * total_slashed_balance)
            // (total_balance // spec.EFFECTIVE_BALANCE_INCREMENT)
            * (effective_balance // spec.EFFECTIVE_BALANCE_INCREMENT)
        )
    else:
        return (
            effective_balance
            // spec.EFFECTIVE_BALANCE_INCREMENT
            * (get_slashing_multiplier(spec) * total_slashed_balance)
            // total_balance
            * spec.EFFECTIVE_BALANCE_INCREMENT
        )


def _setup_process_slashings_test(spec, state, not_slashable_set=set()):
    # Slashed count to ensure that enough validators are slashed to induce maximum penalties
    slashed_count = min(
        (len(state.validators) // get_slashing_multiplier(spec)) + 1,
        # Can't slash more than validator count!
        len(state.validators),
    )
    out_epoch = spec.get_current_epoch(state) + (spec.EPOCHS_PER_SLASHINGS_VECTOR // 2)

    eligible_indices = set(range(slashed_count))
    slashed_indices = eligible_indices.difference(not_slashable_set)
    slash_validators(spec, state, sorted(slashed_indices), [out_epoch] * slashed_count)

    total_balance = spec.get_total_active_balance(state)
    total_penalties = sum(state.slashings)

    assert total_balance // get_slashing_multiplier(spec) <= total_penalties

    return slashed_indices


@with_all_phases
@spec_state_test
def test_max_penalties(spec, state):
    slashed_indices = _setup_process_slashings_test(spec, state)

    yield from run_process_slashings(spec, state)

    for i in slashed_indices:
        assert state.balances[i] == 0


@with_all_phases
@spec_state_test
def test_low_penalty(spec, state):
    # Slashed count is one tenth of validator set
    slashed_count = (len(state.validators) // 10) + 1
    out_epoch = spec.get_current_epoch(state) + (spec.EPOCHS_PER_SLASHINGS_VECTOR // 2)

    slashed_indices = list(range(slashed_count))
    slash_validators(spec, state, slashed_indices, [out_epoch] * slashed_count)

    pre_state = state.copy()

    yield from run_process_slashings(spec, state)

    for i in slashed_indices:
        assert 0 < state.balances[i] < pre_state.balances[i]


@with_all_phases
@spec_state_test
def test_minimal_penalty(spec, state):
    #
    # When very few slashings, the resulting slashing penalty gets rounded down
    # to zero so the result of `process_slashings` is null
    #

    # Just the bare minimum for this one validator
    state.balances[0] = state.validators[0].effective_balance = (
        spec.config.EJECTION_BALANCE + spec.EFFECTIVE_BALANCE_INCREMENT
    )
    # All the other validators get the maximum.
    for i in range(1, len(state.validators)):
        state.validators[i].effective_balance = state.balances[i] = spec.MAX_EFFECTIVE_BALANCE

    out_epoch = spec.get_current_epoch(state) + (spec.EPOCHS_PER_SLASHINGS_VECTOR // 2)

    slash_validators(spec, state, [0], [out_epoch])

    total_balance = spec.get_total_active_balance(state)
    total_penalties = sum(state.slashings)

    assert total_balance // 3 > total_penalties

    run_epoch_processing_to(spec, state, "process_slashings")
    pre_slash_balances = list(state.balances)
    yield "pre", state
    spec.process_slashings(state)
    yield "post", state

    expected_penalty = _compute_expected_correlation_penalty(
        spec, state.validators[0].effective_balance, total_penalties, total_balance
    )

    assert state.balances[0] == pre_slash_balances[0] - expected_penalty


@with_all_phases
@spec_state_test
def test_scaled_penalties(spec, state):
    # skip to next epoch
    next_epoch(spec, state)

    # Also mock some previous slashings, so that we test to have the delta in the penalties computation.
    base = spec.config.EJECTION_BALANCE
    incr = spec.EFFECTIVE_BALANCE_INCREMENT
    # Just add some random slashings. non-zero slashings are at least the minimal effective balance.
    state.slashings[0] = base + (incr * 12)
    state.slashings[4] = base + (incr * 3)
    state.slashings[5] = base + (incr * 6)
    state.slashings[spec.EPOCHS_PER_SLASHINGS_VECTOR - 1] = base + (incr * 7)

    slashed_count = len(state.validators) // (get_slashing_multiplier(spec) + 1)

    assert slashed_count > 10

    # make the balances non-uniform.
    # Otherwise it would just be a simple balance slashing. Test the per-validator scaled penalties.
    diff = spec.MAX_EFFECTIVE_BALANCE - base
    increments = diff // incr
    for i in range(10):
        state.validators[i].effective_balance = base + (incr * (i % increments))
        assert state.validators[i].effective_balance <= spec.MAX_EFFECTIVE_BALANCE
        # add/remove some, see if balances different than the effective balances are picked up
        state.balances[i] = state.validators[i].effective_balance + i - 5

    total_balance = spec.get_total_active_balance(state)

    out_epoch = spec.get_current_epoch(state) + (spec.EPOCHS_PER_SLASHINGS_VECTOR // 2)

    slashed_indices = list(range(slashed_count))

    # Process up to the sub-transition, then Hi-jack and get the balances.
    # We just want to test the slashings.
    # But we are not interested in the other balance changes during the same epoch transition.
    run_epoch_processing_to(spec, state, "process_slashings")
    pre_slash_balances = list(state.balances)

    slash_validators(spec, state, slashed_indices, [out_epoch] * slashed_count)

    yield "pre", state
    spec.process_slashings(state)
    yield "post", state

    total_penalties = sum(state.slashings)

    for i in slashed_indices:
        v = state.validators[i]
        expected_penalty = _compute_expected_correlation_penalty(
            spec, v.effective_balance, total_penalties, total_balance
        )
        assert state.balances[i] == pre_slash_balances[i] - expected_penalty


@with_all_phases
@spec_state_test
def test_slashings_with_random_state(spec, state):
    rng = Random(9998)
    randomize_state(spec, state, rng)

    pre_balances = state.balances.copy()

    target_validators = get_unslashed_exited_validators(spec, state)
    assert len(target_validators) != 0
    assert has_active_balance_differential(spec, state)

    slashed_indices = _setup_process_slashings_test(
        spec, state, not_slashable_set=target_validators
    )

    # ensure no accidental slashings of protected set...
    current_target_validators = get_unslashed_exited_validators(spec, state)
    assert len(current_target_validators) != 0
    assert current_target_validators == target_validators

    yield from run_process_slashings(spec, state)

    for i in slashed_indices:
        assert state.balances[i] < pre_balances[i]
