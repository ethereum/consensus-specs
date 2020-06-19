from eth2spec.test.context import spec_state_test, with_all_phases
from eth2spec.test.phase0.epoch_processing.run_epoch_process_base import (
    run_epoch_processing_with, run_epoch_processing_to
)
from eth2spec.test.helpers.state import transition_to


def run_process_final_updates(spec, state):
    yield from run_epoch_processing_with(spec, state, 'process_final_updates')


@with_all_phases
@spec_state_test
def test_eth1_vote_no_reset(spec, state):
    assert spec.EPOCHS_PER_ETH1_VOTING_PERIOD > 1
    # skip ahead to the end of the epoch
    transition_to(spec, state, spec.SLOTS_PER_EPOCH - 1)

    for i in range(state.slot + 1):  # add a vote for each skipped slot.
        state.eth1_data_votes.append(
            spec.Eth1Data(deposit_root=b'\xaa' * 32,
                          deposit_count=state.eth1_deposit_index,
                          block_hash=b'\xbb' * 32))

    yield from run_process_final_updates(spec, state)

    assert len(state.eth1_data_votes) == spec.SLOTS_PER_EPOCH


@with_all_phases
@spec_state_test
def test_eth1_vote_reset(spec, state):
    # skip ahead to the end of the voting period
    state.slot = (spec.EPOCHS_PER_ETH1_VOTING_PERIOD * spec.SLOTS_PER_EPOCH) - 1
    for i in range(state.slot + 1):  # add a vote for each skipped slot.
        state.eth1_data_votes.append(
            spec.Eth1Data(deposit_root=b'\xaa' * 32,
                          deposit_count=state.eth1_deposit_index,
                          block_hash=b'\xbb' * 32))

    yield from run_process_final_updates(spec, state)

    assert len(state.eth1_data_votes) == 0


@with_all_phases
@spec_state_test
def test_effective_balance_hysteresis(spec, state):
    # Prepare state up to the final-updates.
    # Then overwrite the balances, we only want to focus to be on the hysteresis based changes.
    run_epoch_processing_to(spec, state, 'process_final_updates')
    # Set some edge cases for balances
    max = spec.MAX_EFFECTIVE_BALANCE
    min = spec.EJECTION_BALANCE
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
    spec.process_final_updates(state)
    yield 'post', state

    for i, (_, _, post_eff, name) in enumerate(cases):
        assert state.validators[i].effective_balance == post_eff, name


@with_all_phases
@spec_state_test
def test_historical_root_accumulator(spec, state):
    # skip ahead to near the end of the historical roots period (excl block before epoch processing)
    state.slot = spec.SLOTS_PER_HISTORICAL_ROOT - 1
    history_len = len(state.historical_roots)

    yield from run_process_final_updates(spec, state)

    assert len(state.historical_roots) == history_len + 1
