from copy import deepcopy

import pytest

import eth2spec.phase0.spec as spec

from eth2spec.phase0.spec import (
    get_current_epoch,
    is_active_validator,
)
from tests.phase0.helpers import (
    next_epoch,
)

# mark entire file as 'state'
pytestmark = pytest.mark.state


def test_activation(state):
    index = 0
    assert is_active_validator(state.validator_registry[index], get_current_epoch(state))

    # Mock a new deposit
    state.validator_registry[index].activation_eligibility_epoch = spec.FAR_FUTURE_EPOCH
    state.validator_registry[index].activation_epoch = spec.FAR_FUTURE_EPOCH
    state.validator_registry[index].effective_balance = spec.MAX_EFFECTIVE_BALANCE
    assert not is_active_validator(state.validator_registry[index], get_current_epoch(state))

    pre_state = deepcopy(state)

    blocks = []
    for _ in range(spec.ACTIVATION_EXIT_DELAY + 1):
        block = next_epoch(state)
        blocks.append(block)

    assert state.validator_registry[index].activation_eligibility_epoch != spec.FAR_FUTURE_EPOCH
    assert state.validator_registry[index].activation_epoch != spec.FAR_FUTURE_EPOCH
    assert is_active_validator(
        state.validator_registry[index],
        get_current_epoch(state),
    )

    return pre_state, blocks, state


def test_ejection(state):
    index = 0
    assert is_active_validator(state.validator_registry[index], get_current_epoch(state))
    assert state.validator_registry[index].exit_epoch == spec.FAR_FUTURE_EPOCH

    # Mock an ejection
    state.validator_registry[index].effective_balance = spec.EJECTION_BALANCE

    pre_state = deepcopy(state)

    blocks = []
    for _ in range(spec.ACTIVATION_EXIT_DELAY + 1):
        block = next_epoch(state)
        blocks.append(block)

    assert state.validator_registry[index].exit_epoch != spec.FAR_FUTURE_EPOCH
    assert not is_active_validator(
        state.validator_registry[index],
        get_current_epoch(state),
    )

    return pre_state, blocks, state
