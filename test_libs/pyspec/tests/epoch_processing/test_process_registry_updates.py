from copy import deepcopy

import eth2spec.phase0.spec as spec

from eth2spec.phase0.spec import (
    get_current_epoch,
    is_active_validator,
)
from tests.helpers import (
    next_epoch,
)


def test_activation(state):
    # Mock a new deposit
    index = 0
    state.validator_registry[index].activation_eligibility_epoch = spec.FAR_FUTURE_EPOCH
    state.validator_registry[index].activation_epoch = spec.FAR_FUTURE_EPOCH
    state.validator_registry[index].effective_balance = spec.MAX_EFFECTIVE_BALANCE

    assert not is_active_validator(state.validator_registry[index], get_current_epoch(state))

    pre_state = deepcopy(state)

    for _ in range(spec.ACTIVATION_EXIT_DELAY + 1):
        next_epoch(state)

    assert state.validator_registry[index].activation_eligibility_epoch != spec.FAR_FUTURE_EPOCH
    assert state.validator_registry[index].activation_epoch != spec.FAR_FUTURE_EPOCH
    assert is_active_validator(
        state.validator_registry[index],
        get_current_epoch(state),
    )

    return pre_state, state
