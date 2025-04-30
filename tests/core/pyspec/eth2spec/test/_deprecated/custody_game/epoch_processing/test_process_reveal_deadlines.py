from eth2spec.test._deprecated.helpers.custody import (
    get_valid_custody_key_reveal,
)
from eth2spec.test.helpers.state import transition_to
from eth2spec.test.context import (
    with_phases,
    with_presets,
    spec_state_test,
)
from eth2spec.test.helpers.constants import (
    MINIMAL,
)
from eth2spec.test.helpers.epoch_processing import run_epoch_processing_with
from eth2spec.test._deprecated.custody_game.block_processing.test_process_custody_key_reveal import (
    run_custody_key_reveal_processing,
)
from eth2spec.test.helpers.typing import SpecForkName
CUSTODY_GAME = SpecForkName("custody_game")


def run_process_challenge_deadlines(spec, state):
    yield from run_epoch_processing_with(spec, state, "process_challenge_deadlines")


@with_phases([CUSTODY_GAME])
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_validator_slashed_after_reveal_deadline(spec, state):
    assert state.validators[0].slashed == 0
    transition_to(
        spec, state, spec.get_randao_epoch_for_custody_period(0, 0) * spec.SLOTS_PER_EPOCH
    )

    # Need to run at least one reveal so that not all validators are slashed (otherwise spec fails to find proposers)
    custody_key_reveal = get_valid_custody_key_reveal(spec, state, validator_index=1)
    _, _, _ = run_custody_key_reveal_processing(spec, state, custody_key_reveal)

    transition_to(spec, state, state.slot + spec.EPOCHS_PER_CUSTODY_PERIOD * spec.SLOTS_PER_EPOCH)

    state.validators[0].slashed = 0

    yield from run_process_challenge_deadlines(spec, state)

    assert state.validators[0].slashed == 1


@with_phases([CUSTODY_GAME])
@spec_state_test
@with_presets([MINIMAL], reason="too slow")
def test_validator_not_slashed_after_reveal(spec, state):
    transition_to(spec, state, spec.EPOCHS_PER_CUSTODY_PERIOD * spec.SLOTS_PER_EPOCH)
    custody_key_reveal = get_valid_custody_key_reveal(spec, state)

    _, _, _ = run_custody_key_reveal_processing(spec, state, custody_key_reveal)

    assert state.validators[0].slashed == 0

    transition_to(spec, state, state.slot + spec.EPOCHS_PER_CUSTODY_PERIOD * spec.SLOTS_PER_EPOCH)

    yield from run_process_challenge_deadlines(spec, state)

    assert state.validators[0].slashed == 0
