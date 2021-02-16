from eth2spec.test.helpers.deposits import mock_deposit
from eth2spec.test.helpers.state import next_epoch, next_slots
from eth2spec.test.context import (
    spec_state_test, with_all_phases,
    spec_test, with_custom_state, single_phase,
    large_validator_set,
    is_post_lightclient_patch,
)
from eth2spec.test.helpers.epoch_processing import run_epoch_processing_with


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


def get_per_period_churn_limit(spec, state):
    if not is_post_lightclient_patch(spec):
        # No concept of the activation-exit period in phase 0. Simply return the churn limit.
        return spec.get_validator_churn_limit(state)
    else:
        return spec.get_validator_churn_limit(state) * spec.EPOCHS_PER_ACTIVATION_EXIT_PERIOD


def transition_state_and_finalize_to_process_queue(spec, state):
    # move state forward and finalize to allow for activations
    start_epoch = spec.get_current_epoch(state)
    next_slots(spec, state, spec.SLOTS_PER_EPOCH * 3)
    if is_post_lightclient_patch(spec):
        current_epoch = spec.get_current_epoch(state)
        if not spec.is_activation_exit_period_boundary(state):
            epochs_until_period = (
                spec.EPOCHS_PER_ACTIVATION_EXIT_PERIOD
                - (current_epoch % spec.EPOCHS_PER_ACTIVATION_EXIT_PERIOD)
            )
            next_slots(spec, state, spec.SLOTS_PER_EPOCH * epochs_until_period)

    state.finalized_checkpoint.epoch = start_epoch + 1


@with_all_phases
@spec_state_test
def test_activation_queue_sorting(spec, state):
    churn_limit = get_per_period_churn_limit(spec, state)

    # try to activate more than the per period churn limit
    mock_activations = churn_limit * 2

    epoch = spec.get_current_epoch(state)
    for i in range(mock_activations):
        mock_deposit(spec, state, i)
        state.validators[i].activation_eligibility_epoch = epoch + 1

    # give the last priority over the others
    state.validators[mock_activations - 1].activation_eligibility_epoch = epoch

    transition_state_and_finalize_to_process_queue(spec, state)

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
    churn_limit = get_per_period_churn_limit(spec, state)
    mock_activations = churn_limit * 2

    epoch = spec.get_current_epoch(state)
    for i in range(mock_activations):
        mock_deposit(spec, state, i)
        state.validators[i].activation_eligibility_epoch = epoch + 1

    transition_state_and_finalize_to_process_queue(spec, state)

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
@spec_test
@with_custom_state(balances_fn=large_validator_set, threshold_fn=lambda spec: spec.EJECTION_BALANCE)
@single_phase
def test_ejection_past_churn_limit(spec, state):
    churn_limit = spec.get_validator_churn_limit(state)

    if is_post_lightclient_patch(spec):
        # try to eject more than per-period churn limit
        epochs_per_queue_increment = spec.EPOCHS_PER_ACTIVATION_EXIT_PERIOD
        mock_ejections = churn_limit * epochs_per_queue_increment * 3
    else:
        # try to eject more than per-epoch churn limit
        epochs_per_queue_increment = 1
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
            assert state.validators[i].exit_epoch == expected_ejection_epoch + 1 * epochs_per_queue_increment
        # second thirdgets delayed by 2 epochs
        else:
            assert state.validators[i].exit_epoch == expected_ejection_epoch + 2 * epochs_per_queue_increment


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
