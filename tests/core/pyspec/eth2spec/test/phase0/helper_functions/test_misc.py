import pytest

from eth2spec.test.context import spec_state_test, with_all_phases

@with_all_phases
@spec_state_test
def test_invalid_large_withdrawable_epoch(spec, state):
    """
    This test forces a validator into a withdrawable epoch that overflows the
    epoch (uint64) type. To do this we need two validators, one validator that
    already has an exit epoch and another with a low effective balance. When
    calculating the withdrawable epoch for the second validator, it will
    use the greatest exit epoch of all of the validators. If the first
    validator is given an exit epoch between
    (FAR_FUTURE_EPOCH-MIN_VALIDATOR_WITHDRAWABILITY_DELAY+1) and
    (FAR_FUTURE_EPOCH-1), it will cause an overflow.
    """
    assert spec.is_active_validator(state.validators[0], spec.get_current_epoch(state))
    assert spec.is_active_validator(state.validators[1], spec.get_current_epoch(state))

    state.validators[0].exit_epoch = spec.FAR_FUTURE_EPOCH - 1
    state.validators[1].effective_balance = spec.config.EJECTION_BALANCE

    yield 'pre', state
    with pytest.raises(ValueError):
        spec.initiate_validator_exit(state, 1)
    yield 'post', None
