from eth2spec.test.helpers.state import (
    next_epoch,
    next_epoch_with_attestations,
)
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
def test_add_to_activation_queue(spec, state):
    # move past first two irregular epochs wrt finality
    next_epoch(spec, state)
    next_epoch(spec, state)

    index = 0
    mock_deposit(spec, state, index)

    yield from run_process_registry_updates(spec, state)

    # validator moved into queue
    assert state.validators[index].activation_eligibility_epoch != spec.FAR_FUTURE_EPOCH
    assert state.validators[index].activation_epoch == spec.FAR_FUTURE_EPOCH
    assert not spec.is_active_validator(state.validators[index], spec.get_current_epoch(state))


@with_all_phases
@spec_state_test
def test_activation_queue_to_activated_if_finalized(spec, state):
    # move past first two irregular epochs wrt finality
    next_epoch(spec, state)
    next_epoch(spec, state)

    index = 0
    mock_deposit(spec, state, index)

    # mock validator as having been in queue since before latest finalized
    state.finalized_checkpoint.epoch = spec.get_current_epoch(state) - 1
    state.validators[index].activation_eligibility_epoch = state.finalized_checkpoint.epoch - 1

    assert not spec.is_active_validator(state.validators[index], spec.get_current_epoch(state))

    yield from run_process_registry_updates(spec, state)

    # validator activated for future epoch
    assert state.validators[index].activation_eligibility_epoch != spec.FAR_FUTURE_EPOCH
    assert state.validators[index].activation_epoch != spec.FAR_FUTURE_EPOCH
    assert not spec.is_active_validator(state.validators[index], spec.get_current_epoch(state))
    assert spec.is_active_validator(
        state.validators[index],
        spec.compute_activation_exit_epoch(spec.get_current_epoch(state))
    )


@with_all_phases
@spec_state_test
def test_activation_queue_no_activation_no_finality(spec, state):
    # move past first two irregular epochs wrt finality
    next_epoch(spec, state)
    next_epoch(spec, state)

    index = 0
    mock_deposit(spec, state, index)

    # mock validator as having been in queue only since latest finalized (not before)
    state.finalized_checkpoint.epoch = spec.get_current_epoch(state) - 1
    state.validators[index].activation_eligibility_epoch = state.finalized_checkpoint.epoch

    assert not spec.is_active_validator(state.validators[index], spec.get_current_epoch(state))

    yield from run_process_registry_updates(spec, state)

    # validator not activated
    assert state.validators[index].activation_eligibility_epoch != spec.FAR_FUTURE_EPOCH
    assert state.validators[index].activation_epoch == spec.FAR_FUTURE_EPOCH


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

    # move state forward and finalize to allow for activations
    state.slot += spec.SLOTS_PER_EPOCH * 3
    state.finalized_checkpoint.epoch = epoch + 2

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
def test_activation_queue_efficiency(spec, state):
    churn_limit = spec.get_validator_churn_limit(state)
    mock_activations = churn_limit * 2

    epoch = spec.get_current_epoch(state)
    for i in range(mock_activations):
        mock_deposit(spec, state, i)
        state.validators[i].activation_eligibility_epoch = epoch + 1

    # move state forward and finalize to allow for activations
    state.slot += spec.SLOTS_PER_EPOCH * 3
    state.finalized_checkpoint.epoch = epoch + 2

    # Run first registry update. Do not yield test vectors
    for _ in run_process_registry_updates(spec, state):
        pass

    # Half should churn in first run of registry update
    for i in range(mock_activations):
        if i < mock_activations // 2:
            assert state.validators[i].activation_epoch < spec.FAR_FUTURE_EPOCH
        else:
            assert state.validators[i].activation_epoch == spec.FAR_FUTURE_EPOCH

    # Second half should churn in second run of registry update
    yield from run_process_registry_updates(spec, state)
    for i in range(mock_activations):
        assert state.validators[i].activation_epoch < spec.FAR_FUTURE_EPOCH


@with_all_phases
@spec_state_test
def test_ejection(spec, state):
    index = 0
    assert spec.is_active_validator(state.validators[index], spec.get_current_epoch(state))
    assert state.validators[index].exit_epoch == spec.FAR_FUTURE_EPOCH

    # Mock an ejection
    state.validators[index].effective_balance = spec.EJECTION_BALANCE

    yield from run_process_registry_updates(spec, state)

    assert state.validators[index].exit_epoch != spec.FAR_FUTURE_EPOCH
    assert spec.is_active_validator(state.validators[index], spec.get_current_epoch(state))
    assert not spec.is_active_validator(
        state.validators[index],
        spec.compute_activation_exit_epoch(spec.get_current_epoch(state))
    )
