from eth2spec.test.context import spec_state_test, with_all_phases
from eth2spec.test.helpers.epoch_processing import run_epoch_processing_to


@with_all_phases
@spec_state_test
def test_effective_balance_hysteresis(spec, state):
    # Prepare state up to the final-updates.
    # Then overwrite the balances, we only want to focus to be on the hysteresis based changes.
    run_epoch_processing_to(spec, state, 'process_effective_balance_updates')
    # Set some edge cases for balances
    max = spec.MAX_EFFECTIVE_BALANCE
    min = spec.config.EJECTION_BALANCE
    inc = spec.EFFECTIVE_BALANCE_INCREMENT
    div = spec.HYSTERESIS_QUOTIENT
    hys_inc = inc // div
    down = spec.HYSTERESIS_DOWNWARD_MULTIPLIER
    up = spec.HYSTERESIS_UPWARD_MULTIPLIER
    cases = [
        (max, max, max, "as-is"),
        (max, max - 1, max, "round up"),
        (max, max + 1, max, "round down"),
        (max, max - down * hys_inc, max, "lower balance, but not low enough"),
        (max, max - down * hys_inc - 1, max - inc, "lower balance, step down"),
        (max, max + (up * hys_inc) + 1, max, "already at max, as is"),
        (max, max - inc, max - inc, "exactly 1 step lower"),
        (max, max - inc - 1, max - (2 * inc), "past 1 step lower, double step"),
        (max, max - inc + 1, max - inc, "close to 1 step lower"),
        (min, min + (hys_inc * up), min, "bigger balance, but not high enough"),
        (min, min + (hys_inc * up) + 1, min + inc, "bigger balance, high enough, but small step"),
        (min, min + (hys_inc * div * 2) - 1, min + inc, "bigger balance, high enough, close to double step"),
        (min, min + (hys_inc * div * 2), min + (2 * inc), "exact two step balance increment"),
        (min, min + (hys_inc * div * 2) + 1, min + (2 * inc), "over two steps, round down"),
    ]
    current_epoch = spec.get_current_epoch(state)
    for i, (pre_eff, bal, _, _) in enumerate(cases):
        assert spec.is_active_validator(state.validators[i], current_epoch)
        state.validators[i].effective_balance = pre_eff
        state.balances[i] = bal

    yield 'pre', state
    spec.process_effective_balance_updates(state)
    yield 'post', state

    for i, (_, _, post_eff, name) in enumerate(cases):
        assert state.validators[i].effective_balance == post_eff, name
