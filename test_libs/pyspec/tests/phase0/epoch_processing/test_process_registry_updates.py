<<<<<<< HEAD:test_libs/pyspec/tests/phase0/epoch_processing/test_process_registry_updates.py
from copy import deepcopy
import pytest


# mark entire file as 'state'
pytestmark = pytest.mark.state


=======
import eth2spec.phase0.spec as spec

from eth2spec.phase0.spec import (
    get_current_epoch,
    is_active_validator,
    process_registry_updates
)
from eth2spec.phase0.spec import state_transition
from eth2spec.test.helpers.block import build_empty_block_for_next_slot, sign_block
from eth2spec.test.helpers.state import next_epoch
from eth2spec.test.context import spec_state_test


def run_process_registry_updates(state, valid=True):
    """
    Run ``process_crosslinks``, yielding:
      - pre-state ('pre')
      - post-state ('post').
    If ``valid == False``, run expecting ``AssertionError``
    """
    # transition state to slot before state transition
    slot = state.slot + (spec.SLOTS_PER_EPOCH - state.slot % spec.SLOTS_PER_EPOCH) - 1
    block = build_empty_block_for_next_slot(state)
    block.slot = slot
    sign_block(state, block)
    state_transition(state, block)

    # cache state before epoch transition
    spec.process_slot(state)

    # process components of epoch transition before registry update
    spec.process_justification_and_finalization(state)
    spec.process_crosslinks(state)
    spec.process_rewards_and_penalties(state)

    yield 'pre', state
    process_registry_updates(state)
    yield 'post', state


@spec_state_test
>>>>>>> dev:test_libs/pyspec/eth2spec/test/epoch_processing/test_process_registry_updates.py
def test_activation(state):
    index = 0
    assert spec.is_active_validator(state.validator_registry[index], spec.get_current_epoch(state))

    # Mock a new deposit
    state.validator_registry[index].activation_eligibility_epoch = spec.FAR_FUTURE_EPOCH
    state.validator_registry[index].activation_epoch = spec.FAR_FUTURE_EPOCH
    state.validator_registry[index].effective_balance = spec.MAX_EFFECTIVE_BALANCE
    assert not spec.is_active_validator(state.validator_registry[index], spec.get_current_epoch(state))

    for _ in range(spec.ACTIVATION_EXIT_DELAY + 1):
<<<<<<< HEAD:test_libs/pyspec/tests/phase0/epoch_processing/test_process_registry_updates.py
        block = helpers.next_epoch(state)
        blocks.append(block)
=======
        next_epoch(state)

    yield from run_process_registry_updates(state)
>>>>>>> dev:test_libs/pyspec/eth2spec/test/epoch_processing/test_process_registry_updates.py

    assert state.validator_registry[index].activation_eligibility_epoch != spec.FAR_FUTURE_EPOCH
    assert state.validator_registry[index].activation_epoch != spec.FAR_FUTURE_EPOCH
    assert spec.is_active_validator(
        state.validator_registry[index],
        spec.get_current_epoch(state),
    )


@spec_state_test
def test_ejection(state):
    index = 0
    assert spec.is_active_validator(state.validator_registry[index], spec.get_current_epoch(state))
    assert state.validator_registry[index].exit_epoch == spec.FAR_FUTURE_EPOCH

    # Mock an ejection
    state.validator_registry[index].effective_balance = spec.EJECTION_BALANCE

    for _ in range(spec.ACTIVATION_EXIT_DELAY + 1):
<<<<<<< HEAD:test_libs/pyspec/tests/phase0/epoch_processing/test_process_registry_updates.py
        block = helpers.next_epoch(state)
        blocks.append(block)
=======
        next_epoch(state)

    yield from run_process_registry_updates(state)
>>>>>>> dev:test_libs/pyspec/eth2spec/test/epoch_processing/test_process_registry_updates.py

    assert state.validator_registry[index].exit_epoch != spec.FAR_FUTURE_EPOCH
    assert not spec.is_active_validator(
        state.validator_registry[index],
        spec.get_current_epoch(state),
    )
