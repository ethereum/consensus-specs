from eth2spec.test.context import spec_state_test, with_all_phases
from eth2spec.test.phase_0.epoch_processing.run_epoch_process_base import run_epoch_processing_to


def run_process_final_updates(spec, state):
    yield from run_epoch_processing_to(spec, state, 'process_final_updates')


@with_all_phases
@spec_state_test
def test_eth1_vote_no_reset(spec, state):
    assert spec.SLOTS_PER_ETH1_VOTING_PERIOD > spec.SLOTS_PER_EPOCH
    # skip ahead to near the end of the epoch
    state.slot = spec.SLOTS_PER_EPOCH - 2
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
    # skip ahead to near the end of the voting period
    state.slot = spec.SLOTS_PER_ETH1_VOTING_PERIOD - 2
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
    # Set some edge cases for balances
    max = spec.MAX_EFFECTIVE_BALANCE
    min = spec.EJECTION_BALANCE
    inc = spec.EFFECTIVE_BALANCE_INCREMENT
    half_inc = inc // 2
    cases = [
        (max, max, max),  # as is
        (max, max - 1, max - inc),  # round down, step lower
        (max, max + 1, max),  # round down
        (max, max - inc, max - inc),  # exactly 1 step lower
        (max, max - inc - 1, max - (2 * inc)),  # just 1 over 1 step lower
        (max, max - inc + 1, max - inc),  # close to 1 step lower
        (min, min + (half_inc * 3), min),  # bigger balance, but not high enough
        (min, min + (half_inc * 3) + 1, min + inc),  # bigger balance, high enough, but small step
        (min, min + (half_inc * 4) - 1, min + inc),  # bigger balance, high enough, close to double step
        (min, min + (half_inc * 4), min + (2 * inc)),  # exact two step balance increment
        (min, min + (half_inc * 4) + 1, min + (2 * inc)),  # over two steps, round down
    ]
    for i, (pre_eff, bal, _) in enumerate(cases):
        state.validators[i].effective_balance = pre_eff
        state.balances[i] = bal

    yield from run_process_final_updates(spec, state)

    for i, (_, _, post_eff) in enumerate(cases):
        assert state.validators[i].effective_balance == post_eff
