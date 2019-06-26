from eth2spec.test.context import spec_state_test, with_all_phases
from eth2spec.test.phase_0.epoch_processing.run_epoch_process_base import (
    run_epoch_processing_with, run_epoch_processing_to
)


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

    state.slashed_balances[
        spec.get_current_epoch(state) % spec.EPOCHS_PER_SLASHED_BALANCES_VECTOR
    ] = total_slashed_balance


@with_all_phases
@spec_state_test
def test_max_penalties(spec, state):
    slashed_count = (len(state.validators) // 3) + 1
    out_epoch = spec.get_current_epoch(state) + (spec.EPOCHS_PER_SLASHED_BALANCES_VECTOR // 2)

    slashed_indices = list(range(slashed_count))
    slash_validators(spec, state, slashed_indices, [out_epoch] * slashed_count)

    total_balance = spec.get_total_active_balance(state)
    total_penalties = state.slashed_balances[spec.get_current_epoch(state) % spec.EPOCHS_PER_SLASHED_BALANCES_VECTOR]

    assert total_balance // 3 <= total_penalties

    yield from run_process_slashings(spec, state)

    for i in slashed_indices:
        assert state.balances[i] == 0


@with_all_phases
@spec_state_test
def test_min_penalties(spec, state):
    # run_epoch_processing_to(spec, state, 'process_slashings', exclusive=True)

    # Just the bare minimum for this one validator
    pre_balance = state.balances[0] = state.validators[0].effective_balance = spec.EJECTION_BALANCE
    # All the other validators get the maximum.
    for i in range(1, len(state.validators)):
        state.validators[i].effective_balance = state.balances[i] = spec.MAX_EFFECTIVE_BALANCE

    out_epoch = spec.get_current_epoch(state) + (spec.EPOCHS_PER_SLASHED_BALANCES_VECTOR // 2)

    slash_validators(spec, state, [0], [out_epoch])

    total_balance = spec.get_total_active_balance(state)
    total_penalties = state.slashed_balances[spec.get_current_epoch(state) % spec.EPOCHS_PER_SLASHED_BALANCES_VECTOR]

    # we are testing the minimum here, i.e. get slashed (effective_balance / MIN_SLASHING_PENALTY_QUOTIENT)
    assert total_penalties * 3 / total_balance < 1 / spec.MIN_SLASHING_PENALTY_QUOTIENT

    yield from run_process_slashings(spec, state)

    assert state.balances[0] == pre_balance - (pre_balance // spec.MIN_SLASHING_PENALTY_QUOTIENT)


@with_all_phases
@spec_state_test
def test_scaled_penalties(spec, state):
    # skip to next epoch
    state.slot = spec.SLOTS_PER_EPOCH

    # Also mock some previous slashings, so that we test to have the delta in the penalties computation.
    for i in range(spec.EPOCHS_PER_SLASHED_BALANCES_VECTOR):
        state.slashed_balances[i] = spec.MAX_EFFECTIVE_BALANCE * 3

    # Mock the very last one (which is to be used for the delta balance computation) to be different.
    # To enforce the client test runner to correctly get this one from the array, not the others.
    prev_penalties = state.slashed_balances[
        (spec.get_current_epoch(state) + 1) % spec.EPOCHS_PER_SLASHED_BALANCES_VECTOR
    ] = spec.MAX_EFFECTIVE_BALANCE * 2

    slashed_count = len(state.validators) // 4

    assert slashed_count > 10

    # make the balances non-uniform.
    # Otherwise it would just be a simple 3/4 balance slashing. Test the per-validator scaled penalties.
    for i in range(10):
        state.validators[i].effective_balance += spec.EFFECTIVE_BALANCE_INCREMENT * 4
        state.balances[i] += spec.EFFECTIVE_BALANCE_INCREMENT * 4

    total_balance = spec.get_total_active_balance(state)

    out_epoch = spec.get_current_epoch(state) + (spec.EPOCHS_PER_SLASHED_BALANCES_VECTOR // 2)

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

    total_penalties = state.slashed_balances[spec.get_current_epoch(state) % spec.EPOCHS_PER_SLASHED_BALANCES_VECTOR]
    total_penalties -= prev_penalties

    for i in slashed_indices:
        v = state.validators[i]
        penalty = v.effective_balance * total_penalties * 3 // total_balance
        assert state.balances[i] == pre_slash_balances[i] - penalty
