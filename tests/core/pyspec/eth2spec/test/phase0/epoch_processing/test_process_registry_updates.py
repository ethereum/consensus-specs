from eth2spec.test.helpers.deposits import mock_deposit
from eth2spec.test.helpers.state import next_epoch, next_slots
from eth2spec.test.context import spec_state_test, with_all_phases
from eth2spec.test.phase0.epoch_processing.run_epoch_process_base import run_epoch_processing_with


def run_process_registry_updates(spec, state):
    yield from run_epoch_processing_with(spec, state, 'process_registry_updates')


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

    # mock validator as having been in queue since latest finalized
    state.finalized_checkpoint.epoch = spec.get_current_epoch(state) - 1
    state.validators[index].activation_eligibility_epoch = state.finalized_checkpoint.epoch

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

    # mock validator as having been in queue only after latest finalized
    state.finalized_checkpoint.epoch = spec.get_current_epoch(state) - 1
    state.validators[index].activation_eligibility_epoch = state.finalized_checkpoint.epoch + 1

    assert not spec.is_active_validator(state.validators[index], spec.get_current_epoch(state))

    yield from run_process_registry_updates(spec, state)

    # validator not activated
    assert state.validators[index].activation_eligibility_epoch != spec.FAR_FUTURE_EPOCH
    assert state.validators[index].activation_epoch == spec.FAR_FUTURE_EPOCH


@with_all_phases
@spec_state_test
def test_activation_queue_sorting(spec, state):
    churn_limit = spec.get_validator_churn_limit(state)

    # try to activate more than the per-epoch churn linmit
    mock_activations = churn_limit * 2

    epoch = spec.get_current_epoch(state)
    for i in range(mock_activations):
        mock_deposit(spec, state, i)
        state.validators[i].activation_eligibility_epoch = epoch + 1

    # give the last priority over the others
    state.validators[mock_activations - 1].activation_eligibility_epoch = epoch

    # move state forward and finalize to allow for activations
    next_slots(spec, state, spec.SLOTS_PER_EPOCH * 3)
    state.finalized_checkpoint.epoch = epoch + 1

    yield from run_process_registry_updates(spec, state)

    # the first got in as second
    assert state.validators[0].activation_epoch != spec.FAR_FUTURE_EPOCH
    # the prioritized got in as first
    assert state.validators[mock_activations - 1].activation_epoch != spec.FAR_FUTURE_EPOCH
    # the second last is at the end of the queue, and did not make the churn,
    #  hence is not assigned an activation_epoch yet.
    assert state.validators[mock_activations - 2].activation_epoch == spec.FAR_FUTURE_EPOCH
    # the one at churn_limit did not make it, it was out-prioritized
    assert state.validators[churn_limit].activation_epoch == spec.FAR_FUTURE_EPOCH
    # but the the one in front of the above did
    assert state.validators[churn_limit - 1].activation_epoch != spec.FAR_FUTURE_EPOCH


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
    next_slots(spec, state, spec.SLOTS_PER_EPOCH * 3)

    state.finalized_checkpoint.epoch = epoch + 1

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


@with_all_phases
@spec_state_test
def test_ejection_past_churn_limit(spec, state):
    churn_limit = spec.get_validator_churn_limit(state)

    # try to eject more than per-epoch churn limit
    mock_ejections = churn_limit * 3

    for i in range(mock_ejections):
        state.validators[i].effective_balance = spec.EJECTION_BALANCE

    expected_ejection_epoch = spec.compute_activation_exit_epoch(spec.get_current_epoch(state))

    yield from run_process_registry_updates(spec, state)

    for i in range(mock_ejections):
        # first third ejected in normal speed
        if i < mock_ejections // 3:
            assert state.validators[i].exit_epoch == expected_ejection_epoch
        # second thirdgets delayed by 1 epoch
        elif mock_ejections // 3 <= i < mock_ejections * 2 // 3:
            assert state.validators[i].exit_epoch == expected_ejection_epoch + 1
        # second thirdgets delayed by 2 epochs
        else:
            assert state.validators[i].exit_epoch == expected_ejection_epoch + 2


@with_all_phases
@spec_state_test
def test_activation_queue_activation_and_ejection(spec, state):
    # move past first two irregular epochs wrt finality
    next_epoch(spec, state)
    next_epoch(spec, state)

    # ready for entrance into activation queue
    activation_queue_index = 0
    mock_deposit(spec, state, activation_queue_index)

    # ready for activation
    activation_index = 1
    mock_deposit(spec, state, activation_index)
    state.finalized_checkpoint.epoch = spec.get_current_epoch(state) - 1
    state.validators[activation_index].activation_eligibility_epoch = state.finalized_checkpoint.epoch

    # ready for ejection
    ejection_index = 2
    state.validators[ejection_index].effective_balance = spec.EJECTION_BALANCE

    yield from run_process_registry_updates(spec, state)

    # validator moved into activation queue
    validator = state.validators[activation_queue_index]
    assert validator.activation_eligibility_epoch != spec.FAR_FUTURE_EPOCH
    assert validator.activation_epoch == spec.FAR_FUTURE_EPOCH
    assert not spec.is_active_validator(validator, spec.get_current_epoch(state))

    # validator activated for future epoch
    validator = state.validators[activation_index]
    assert validator.activation_eligibility_epoch != spec.FAR_FUTURE_EPOCH
    assert validator.activation_epoch != spec.FAR_FUTURE_EPOCH
    assert not spec.is_active_validator(validator, spec.get_current_epoch(state))
    assert spec.is_active_validator(
        validator,
        spec.compute_activation_exit_epoch(spec.get_current_epoch(state))
    )

    # validator ejected for future epoch
    validator = state.validators[ejection_index]
    assert validator.exit_epoch != spec.FAR_FUTURE_EPOCH
    assert spec.is_active_validator(validator, spec.get_current_epoch(state))
    assert not spec.is_active_validator(
        validator,
        spec.compute_activation_exit_epoch(spec.get_current_epoch(state))
    )
