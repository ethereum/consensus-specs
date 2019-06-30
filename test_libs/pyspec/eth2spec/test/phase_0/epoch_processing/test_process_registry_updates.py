from eth2spec.test.helpers.state import next_epoch
from eth2spec.test.context import spec_state_test, with_all_phases
from eth2spec.test.phase_0.epoch_processing.run_epoch_process_base import run_epoch_processing_with


def run_process_registry_updates(spec, state):
    yield from run_epoch_processing_with(spec, state, 'process_registry_updates')


def mock_deposit(spec, state, index):
    assert spec.is_active_validator(state.validators[index], spec.get_current_epoch(state))
    state.validators[index].activation_eligibility_epoch = spec.FAR_FUTURE_EPOCH
    state.validators[index].activation_epoch = spec.FAR_FUTURE_EPOCH
    state.validators[index].effective_balance = spec.MAX_EFFECTIVE_BALANCE
    assert not spec.is_active_validator(state.validators[index], spec.get_current_epoch(state))


@with_all_phases
@spec_state_test
def test_activation(spec, state):
    index = 0
    mock_deposit(spec, state, index)

    for _ in range(spec.ACTIVATION_EXIT_DELAY + 1):
        next_epoch(spec, state)

    yield from run_process_registry_updates(spec, state)

    assert state.validators[index].activation_eligibility_epoch != spec.FAR_FUTURE_EPOCH
    assert state.validators[index].activation_epoch != spec.FAR_FUTURE_EPOCH
    assert spec.is_active_validator(state.validators[index], spec.get_current_epoch(state))


@with_all_phases
@spec_state_test
def test_activation_queue_sorting(spec, state):
    mock_activations = 10

    epoch = spec.get_current_epoch(state)
    for i in range(mock_activations):
        mock_deposit(spec, state, i)
        state.validators[i].activation_eligibility_epoch = epoch + 1

    # give the last priority over the others
    state.validators[mock_activations - 1].activation_eligibility_epoch = epoch

    # make sure we are hitting the churn
    churn_limit = spec.get_validator_churn_limit(state)
    assert mock_activations > churn_limit

    yield from run_process_registry_updates(spec, state)

    # the first got in as second
    assert state.validators[0].activation_epoch != spec.FAR_FUTURE_EPOCH
    # the prioritized got in as first
    assert state.validators[mock_activations - 1].activation_epoch != spec.FAR_FUTURE_EPOCH
    # the second last is at the end of the queue, and did not make the churn,
    #  hence is not assigned an activation_epoch yet.
    assert state.validators[mock_activations - 2].activation_epoch == spec.FAR_FUTURE_EPOCH
    # the one at churn_limit - 1 did not make it, it was out-prioritized
    assert state.validators[churn_limit - 1].activation_epoch == spec.FAR_FUTURE_EPOCH
    # but the the one in front of the above did
    assert state.validators[churn_limit - 2].activation_epoch != spec.FAR_FUTURE_EPOCH


@with_all_phases
@spec_state_test
def test_ejection(spec, state):
    index = 0
    assert spec.is_active_validator(state.validators[index], spec.get_current_epoch(state))
    assert state.validators[index].exit_epoch == spec.FAR_FUTURE_EPOCH

    # Mock an ejection
    state.validators[index].effective_balance = spec.EJECTION_BALANCE

    for _ in range(spec.ACTIVATION_EXIT_DELAY + 1):
        next_epoch(spec, state)

    yield from run_process_registry_updates(spec, state)

    assert state.validators[index].exit_epoch != spec.FAR_FUTURE_EPOCH
    assert not spec.is_active_validator(
        state.validators[index],
        spec.get_current_epoch(state),
    )
