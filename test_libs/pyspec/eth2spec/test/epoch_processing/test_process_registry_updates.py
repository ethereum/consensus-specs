import eth2spec.phase0.spec as spec

from eth2spec.phase0.spec import (
    get_current_epoch,
    is_active_validator,
    process_registry_updates
)
from eth2spec.test.helpers.state import next_epoch
from eth2spec.test.context import spec_state_test


@spec_state_test
def test_activation(state):
    index = 0
    assert is_active_validator(state.validator_registry[index], get_current_epoch(state))

    # Mock a new deposit
    state.validator_registry[index].activation_eligibility_epoch = spec.FAR_FUTURE_EPOCH
    state.validator_registry[index].activation_epoch = spec.FAR_FUTURE_EPOCH
    state.validator_registry[index].effective_balance = spec.MAX_EFFECTIVE_BALANCE
    assert not is_active_validator(state.validator_registry[index], get_current_epoch(state))

    for _ in range(spec.ACTIVATION_EXIT_DELAY + 1):
        next_epoch(state)

    yield 'pre', state

    process_registry_updates(state)

    yield 'post', state

    assert state.validator_registry[index].activation_eligibility_epoch != spec.FAR_FUTURE_EPOCH
    assert state.validator_registry[index].activation_epoch != spec.FAR_FUTURE_EPOCH
    assert is_active_validator(
        state.validator_registry[index],
        get_current_epoch(state),
    )


@spec_state_test
def test_ejection(state):
    index = 0
    assert is_active_validator(state.validator_registry[index], get_current_epoch(state))
    assert state.validator_registry[index].exit_epoch == spec.FAR_FUTURE_EPOCH

    # Mock an ejection
    state.validator_registry[index].effective_balance = spec.EJECTION_BALANCE

    for _ in range(spec.ACTIVATION_EXIT_DELAY + 1):
        next_epoch(state)

    yield 'pre', state

    process_registry_updates(state)

    yield 'post', state

    assert state.validator_registry[index].exit_epoch != spec.FAR_FUTURE_EPOCH
    assert not is_active_validator(
        state.validator_registry[index],
        get_current_epoch(state),
    )
