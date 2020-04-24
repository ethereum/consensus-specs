from eth2spec.test.helpers.custody import (
    get_valid_custody_key_reveal,
)
from eth2spec.test.helpers.state import next_epoch
from eth2spec.test.context import (
    with_all_phases_except,
    spec_state_test,
)
from eth2spec.test.phase_0.epoch_processing.run_epoch_process_base import run_epoch_processing_with
from eth2spec.test.phase_1.block_processing.test_process_custody_key_reveal import run_custody_key_reveal_processing


def run_process_challenge_deadlines(spec, state):
    yield from run_epoch_processing_with(spec, state, 'process_challenge_deadlines')


@with_all_phases_except(['phase0'])
@spec_state_test
def test_validator_slashed_after_reveal_deadline(spec, state):
    assert state.validators[0].slashed == 0

    state.slot += ((spec.CHUNK_RESPONSE_DEADLINE + spec.EPOCHS_PER_CUSTODY_PERIOD)
                   * spec.SLOTS_PER_EPOCH)
    next_epoch(spec, state)

    yield from run_process_challenge_deadlines(spec, state)

    assert state.validators[0].slashed == 1


@with_all_phases_except(['phase0'])
@spec_state_test
def test_validator_not_slashed_after_reveal(spec, state):
    state.slot += spec.EPOCHS_PER_CUSTODY_PERIOD * spec.SLOTS_PER_EPOCH
    custody_key_reveal = get_valid_custody_key_reveal(spec, state)

    _, _, _ = run_custody_key_reveal_processing(spec, state, custody_key_reveal)

    assert state.validators[0].slashed == 0

    state.slot += spec.CHUNK_RESPONSE_DEADLINE * spec.SLOTS_PER_EPOCH
    next_epoch(spec, state)

    yield from run_process_challenge_deadlines(spec, state)

    assert state.validators[0].slashed == 0
