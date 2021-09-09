from eth2spec.test.helpers.deposits import mock_deposit
from eth2spec.test.helpers.state import next_epoch, next_slots
from eth2spec.test.helpers.constants import MINIMAL
from eth2spec.test.context import (
    spec_test, spec_state_test,
    with_all_phases, single_phase,
    with_custom_state, with_presets,
    scaled_churn_balances,
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


def run_test_activation_queue_efficiency(spec, state):
    churn_limit = spec.get_validator_churn_limit(state)
    mock_activations = churn_limit * 2

    epoch = spec.get_current_epoch(state)
    for i in range(mock_activations):
        mock_deposit(spec, state, i)
        state.validators[i].activation_eligibility_epoch = epoch + 1

    # move state forward and finalize to allow for activations
    next_slots(spec, state, spec.SLOTS_PER_EPOCH * 3)

    state.finalized_checkpoint.epoch = epoch + 1

    # Churn limit could have changed given the active vals removed via `mock_deposit`
    churn_limit_0 = spec.get_validator_churn_limit(state)

    # Run first registry update. Do not yield test vectors
    for _ in run_process_registry_updates(spec, state):
        pass

    # Half should churn in first run of registry update
    for i in range(mock_activations):
        if i < churn_limit_0:
            assert state.validators[i].activation_epoch < spec.FAR_FUTURE_EPOCH
        else:
            assert state.validators[i].activation_epoch == spec.FAR_FUTURE_EPOCH

    # Second half should churn in second run of registry update
    churn_limit_1 = spec.get_validator_churn_limit(state)
    yield from run_process_registry_updates(spec, state)
    for i in range(churn_limit_0 + churn_limit_1):
        assert state.validators[i].activation_epoch < spec.FAR_FUTURE_EPOCH


@with_all_phases
@spec_state_test
def test_activation_queue_efficiency_min(spec, state):
    assert spec.get_validator_churn_limit(state) == spec.config.MIN_PER_EPOCH_CHURN_LIMIT
    yield from run_test_activation_queue_efficiency(spec, state)


@with_all_phases
@with_presets([MINIMAL],
              reason="mainnet config leads to larger validator set than limit of public/private keys pre-generated")
@spec_test
@with_custom_state(balances_fn=scaled_churn_balances, threshold_fn=lambda spec: spec.config.EJECTION_BALANCE)
@single_phase
def test_activation_queue_efficiency_scaled(spec, state):
    assert spec.get_validator_churn_limit(state) > spec.config.MIN_PER_EPOCH_CHURN_LIMIT
    yield from run_test_activation_queue_efficiency(spec, state)


@with_all_phases
@spec_state_test
def test_ejection(spec, state):
    index = 0
    assert spec.is_active_validator(state.validators[index], spec.get_current_epoch(state))
    assert state.validators[index].exit_epoch == spec.FAR_FUTURE_EPOCH

    # Mock an ejection
    state.validators[index].effective_balance = spec.config.EJECTION_BALANCE

    yield from run_process_registry_updates(spec, state)

    assert state.validators[index].exit_epoch != spec.FAR_FUTURE_EPOCH
    assert spec.is_active_validator(state.validators[index], spec.get_current_epoch(state))
    assert not spec.is_active_validator(
        state.validators[index],
        spec.compute_activation_exit_epoch(spec.get_current_epoch(state))
    )


def run_test_ejection_past_churn_limit(spec, state):
    churn_limit = spec.get_validator_churn_limit(state)

    # try to eject more than per-epoch churn limit
    mock_ejections = churn_limit * 3

    for i in range(mock_ejections):
        state.validators[i].effective_balance = spec.config.EJECTION_BALANCE

    expected_ejection_epoch = spec.compute_activation_exit_epoch(spec.get_current_epoch(state))

    yield from run_process_registry_updates(spec, state)

    for i in range(mock_ejections):
        # first third ejected in normal speed
        if i < mock_ejections // 3:
            assert state.validators[i].exit_epoch == expected_ejection_epoch
        # second third gets delayed by 1 epoch
        elif mock_ejections // 3 <= i < mock_ejections * 2 // 3:
            assert state.validators[i].exit_epoch == expected_ejection_epoch + 1
        # final third gets delayed by 2 epochs
        else:
            assert state.validators[i].exit_epoch == expected_ejection_epoch + 2


@with_all_phases
@spec_state_test
def test_ejection_past_churn_limit_min(spec, state):
    assert spec.get_validator_churn_limit(state) == spec.config.MIN_PER_EPOCH_CHURN_LIMIT
    yield from run_test_ejection_past_churn_limit(spec, state)


@with_all_phases
@with_presets([MINIMAL],
              reason="mainnet config leads to larger validator set than limit of public/private keys pre-generated")
@spec_test
@with_custom_state(balances_fn=scaled_churn_balances, threshold_fn=lambda spec: spec.config.EJECTION_BALANCE)
@single_phase
def test_ejection_past_churn_limit_scaled(spec, state):
    assert spec.get_validator_churn_limit(state) > spec.config.MIN_PER_EPOCH_CHURN_LIMIT
    yield from run_test_ejection_past_churn_limit(spec, state)


def run_test_activation_queue_activation_and_ejection(spec, state, num_per_status):
    # move past first two irregular epochs wrt finality
    next_epoch(spec, state)
    next_epoch(spec, state)

    # ready for entrance into activation queue
    activation_queue_start_index = 0
    activation_queue_indices = list(range(activation_queue_start_index, activation_queue_start_index + num_per_status))
    for validator_index in activation_queue_indices:
        mock_deposit(spec, state, validator_index)

    # ready for activation
    state.finalized_checkpoint.epoch = spec.get_current_epoch(state) - 1
    activation_start_index = num_per_status
    activation_indices = list(range(activation_start_index, activation_start_index + num_per_status))
    for validator_index in activation_indices:
        mock_deposit(spec, state, validator_index)
        state.validators[validator_index].activation_eligibility_epoch = state.finalized_checkpoint.epoch

    # ready for ejection
    ejection_start_index = num_per_status * 2
    ejection_indices = list(range(ejection_start_index, ejection_start_index + num_per_status))
    for validator_index in ejection_indices:
        state.validators[validator_index].effective_balance = spec.config.EJECTION_BALANCE

    churn_limit = spec.get_validator_churn_limit(state)
    yield from run_process_registry_updates(spec, state)

    # all eligible validators moved into activation queue
    for validator_index in activation_queue_indices:
        validator = state.validators[validator_index]
        assert validator.activation_eligibility_epoch != spec.FAR_FUTURE_EPOCH
        assert validator.activation_epoch == spec.FAR_FUTURE_EPOCH
        assert not spec.is_active_validator(validator, spec.get_current_epoch(state))

    # up to churn limit validators get activated for future epoch from the queue
    for validator_index in activation_indices[:churn_limit]:
        validator = state.validators[validator_index]
        assert validator.activation_eligibility_epoch != spec.FAR_FUTURE_EPOCH
        assert validator.activation_epoch != spec.FAR_FUTURE_EPOCH
        assert not spec.is_active_validator(validator, spec.get_current_epoch(state))
        assert spec.is_active_validator(
            validator,
            spec.compute_activation_exit_epoch(spec.get_current_epoch(state))
        )

    # any remaining validators do not exit the activation queue
    for validator_index in activation_indices[churn_limit:]:
        validator = state.validators[validator_index]
        assert validator.activation_eligibility_epoch != spec.FAR_FUTURE_EPOCH
        assert validator.activation_epoch == spec.FAR_FUTURE_EPOCH

    # all ejection balance validators ejected for a future epoch
    for i, validator_index in enumerate(ejection_indices):
        validator = state.validators[validator_index]
        assert validator.exit_epoch != spec.FAR_FUTURE_EPOCH
        assert spec.is_active_validator(validator, spec.get_current_epoch(state))
        queue_offset = i // churn_limit
        assert not spec.is_active_validator(
            validator,
            spec.compute_activation_exit_epoch(spec.get_current_epoch(state)) + queue_offset
        )


@with_all_phases
@spec_state_test
def test_activation_queue_activation_and_ejection__1(spec, state):
    yield from run_test_activation_queue_activation_and_ejection(spec, state, 1)


@with_all_phases
@spec_state_test
def test_activation_queue_activation_and_ejection__churn_limit(spec, state):
    churn_limit = spec.get_validator_churn_limit(state)
    assert churn_limit == spec.config.MIN_PER_EPOCH_CHURN_LIMIT
    yield from run_test_activation_queue_activation_and_ejection(spec, state, churn_limit)


@with_all_phases
@spec_state_test
def test_activation_queue_activation_and_ejection__exceed_churn_limit(spec, state):
    churn_limit = spec.get_validator_churn_limit(state)
    assert churn_limit == spec.config.MIN_PER_EPOCH_CHURN_LIMIT
    yield from run_test_activation_queue_activation_and_ejection(spec, state, churn_limit + 1)


@with_all_phases
@with_presets([MINIMAL],
              reason="mainnet config leads to larger validator set than limit of public/private keys pre-generated")
@spec_test
@with_custom_state(balances_fn=scaled_churn_balances, threshold_fn=lambda spec: spec.config.EJECTION_BALANCE)
@single_phase
def test_activation_queue_activation_and_ejection__scaled_churn_limit(spec, state):
    churn_limit = spec.get_validator_churn_limit(state)
    assert churn_limit > spec.config.MIN_PER_EPOCH_CHURN_LIMIT
    yield from run_test_activation_queue_activation_and_ejection(spec, state, churn_limit)


@with_all_phases
@with_presets([MINIMAL],
              reason="mainnet config leads to larger validator set than limit of public/private keys pre-generated")
@spec_test
@with_custom_state(balances_fn=scaled_churn_balances, threshold_fn=lambda spec: spec.config.EJECTION_BALANCE)
@single_phase
def test_activation_queue_activation_and_ejection__exceed_scaled_churn_limit(spec, state):
    churn_limit = spec.get_validator_churn_limit(state)
    assert churn_limit > spec.config.MIN_PER_EPOCH_CHURN_LIMIT
    yield from run_test_activation_queue_activation_and_ejection(spec, state, churn_limit * 2)
