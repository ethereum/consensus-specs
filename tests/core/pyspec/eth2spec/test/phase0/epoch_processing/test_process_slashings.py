from eth2spec.test.context import spec_state_test, with_all_phases
from eth2spec.test.phase0.epoch_processing.run_epoch_process_base import (
    run_epoch_processing_with, run_epoch_processing_to
)
from eth2spec.test.helpers.state import next_epoch


def run_process_slashings(spec, state):
    yield from run_epoch_processing_with(spec, state, 'process_slashings')


def slash_validators(spec, state, indices, out_epochs):
    total_slashed_balance = 0
    for i, out_epoch in zip(indices, out_epochs):
        v = state.validators[i]
        v.slashed = True
        spec.initiate_validator_exit(state, i)
        v.withdrawable_epoch = out_epoch
        total_slashed_balance += v.effective_balance

    state.slashings[
        spec.get_current_epoch(state) % spec.EPOCHS_PER_SLASHINGS_VECTOR
    ] = total_slashed_balance


@with_all_phases
@spec_state_test
def test_max_penalties(spec, state):
    # Slashed count to ensure that enough validators are slashed to induce maximum penalties
    slashed_count = min(
        (len(state.validators) // spec.PROPORTIONAL_SLASHING_MULTIPLIER) + 1,
        # Can't slash more than validator count!
        len(state.validators)
    )
    out_epoch = spec.get_current_epoch(state) + (spec.EPOCHS_PER_SLASHINGS_VECTOR // 2)

    slashed_indices = list(range(slashed_count))
    slash_validators(spec, state, slashed_indices, [out_epoch] * slashed_count)

    total_balance = spec.get_total_active_balance(state)
    total_penalties = sum(state.slashings)

    assert total_balance // spec.PROPORTIONAL_SLASHING_MULTIPLIER <= total_penalties

    yield from run_process_slashings(spec, state)

    for i in slashed_indices:
        assert state.balances[i] == 0


@with_all_phases
@spec_state_test
def test_small_penalty(spec, state):
    # Just the bare minimum for this one validator
    state.balances[0] = state.validators[0].effective_balance = spec.EJECTION_BALANCE
    # All the other validators get the maximum.
    for i in range(1, len(state.validators)):
        state.validators[i].effective_balance = state.balances[i] = spec.MAX_EFFECTIVE_BALANCE

    out_epoch = spec.get_current_epoch(state) + (spec.EPOCHS_PER_SLASHINGS_VECTOR // 2)

    slash_validators(spec, state, [0], [out_epoch])

    total_balance = spec.get_total_active_balance(state)
    total_penalties = sum(state.slashings)

    assert total_balance // 3 > total_penalties

    run_epoch_processing_to(spec, state, 'process_slashings')
    pre_slash_balances = list(state.balances)
    yield 'pre', state
    spec.process_slashings(state)
    yield 'post', state

    expected_penalty = (
        state.validators[0].effective_balance // spec.EFFECTIVE_BALANCE_INCREMENT
        * (3 * total_penalties)
        // total_balance
        * spec.EFFECTIVE_BALANCE_INCREMENT
    )
    assert state.balances[0] == pre_slash_balances[0] - expected_penalty


@with_all_phases
@spec_state_test
def test_scaled_penalties(spec, state):
    # skip to next epoch
    next_epoch(spec, state)

    # Also mock some previous slashings, so that we test to have the delta in the penalties computation.
    base = spec.EJECTION_BALANCE
    incr = spec.EFFECTIVE_BALANCE_INCREMENT
    # Just add some random slashings. non-zero slashings are at least the minimal effective balance.
    state.slashings[0] = base + (incr * 12)
    state.slashings[4] = base + (incr * 3)
    state.slashings[5] = base + (incr * 6)
    state.slashings[spec.EPOCHS_PER_SLASHINGS_VECTOR - 1] = base + (incr * 7)

    slashed_count = len(state.validators) // (spec.PROPORTIONAL_SLASHING_MULTIPLIER + 1)

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
    run_epoch_processing_to(spec, state, 'process_slashings')
    pre_slash_balances = list(state.balances)

    slash_validators(spec, state, slashed_indices, [out_epoch] * slashed_count)

    yield 'pre', state
    spec.process_slashings(state)
    yield 'post', state

    total_penalties = sum(state.slashings)

    for i in slashed_indices:
        v = state.validators[i]
        expected_penalty = (
            v.effective_balance // spec.EFFECTIVE_BALANCE_INCREMENT
            * (spec.PROPORTIONAL_SLASHING_MULTIPLIER * total_penalties)
            // (total_balance)
            * spec.EFFECTIVE_BALANCE_INCREMENT
        )
        assert state.balances[i] == pre_slash_balances[i] - expected_penalty
