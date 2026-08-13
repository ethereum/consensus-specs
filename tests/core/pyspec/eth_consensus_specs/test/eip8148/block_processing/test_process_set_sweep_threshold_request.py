from eth_consensus_specs.test.context import (
    spec_state_test,
    with_eip8148_and_later,
)
from eth_consensus_specs.test.helpers.keys import pubkeys
from eth_consensus_specs.test.helpers.withdrawals import (
    prepare_set_sweep_threshold_request,
    set_compounding_withdrawal_credential_with_balance,
    set_eth1_withdrawal_credential_with_balance,
)


def _set_compounding_validator(spec, state, validator_index, balance=None):
    set_compounding_withdrawal_credential_with_balance(
        spec, state, validator_index, balance=balance
    )
    state.validator_sweep_thresholds[validator_index] = spec.MAX_EFFECTIVE_BALANCE_ELECTRA


def run_set_sweep_threshold_request_processing(
    spec, state, set_sweep_threshold_request, noop=False
):
    """
    Run ``process_set_sweep_threshold_request``, yielding:
      - pre-state ('pre')
      - set_sweep_threshold_request ('set_sweep_threshold_request')
      - post-state ('post').

    The function never raises. If ``noop`` is True, expect the request to be
    consumed without changing the state.
    """
    pre_state = state.copy()

    yield "pre", state
    yield "set_sweep_threshold_request", set_sweep_threshold_request

    spec.process_set_sweep_threshold_request(state, set_sweep_threshold_request)

    yield "post", state

    if noop:
        assert state == pre_state


@with_eip8148_and_later
@spec_state_test
def test_process_set_sweep_threshold_request__success(spec, state):
    """Test setting the minimum sweep threshold on a compounding validator."""
    validator_index = 7
    _set_compounding_validator(spec, state, validator_index, balance=spec.MIN_ACTIVATION_BALANCE)
    threshold = spec.MIN_ACTIVATION_BALANCE
    assert state.validator_sweep_thresholds[validator_index] != threshold

    set_sweep_threshold_request = prepare_set_sweep_threshold_request(
        spec, state, validator_index, threshold
    )

    yield from run_set_sweep_threshold_request_processing(spec, state, set_sweep_threshold_request)

    assert state.validator_sweep_thresholds[validator_index] == threshold


@with_eip8148_and_later
@spec_state_test
def test_process_set_sweep_threshold_request__success_first_validator(spec, state):
    """
    Test setting a sweep threshold on the first validator of the registry, at
    the lower boundary of the ``validator_sweep_thresholds`` list.
    """
    validator_index = 0
    _set_compounding_validator(spec, state, validator_index, balance=spec.MIN_ACTIVATION_BALANCE)
    threshold = spec.MIN_ACTIVATION_BALANCE
    assert state.validator_sweep_thresholds[validator_index] != threshold

    set_sweep_threshold_request = prepare_set_sweep_threshold_request(
        spec, state, validator_index, threshold
    )

    yield from run_set_sweep_threshold_request_processing(spec, state, set_sweep_threshold_request)

    assert state.validator_sweep_thresholds[validator_index] == threshold


@with_eip8148_and_later
@spec_state_test
def test_process_set_sweep_threshold_request__success_last_validator(spec, state):
    """
    Test setting a sweep threshold on the last validator of the registry, at
    the upper boundary of the ``validator_sweep_thresholds`` list.
    """
    validator_index = len(state.validators) - 1
    _set_compounding_validator(spec, state, validator_index, balance=spec.MIN_ACTIVATION_BALANCE)
    threshold = spec.MIN_ACTIVATION_BALANCE
    assert state.validator_sweep_thresholds[validator_index] != threshold

    set_sweep_threshold_request = prepare_set_sweep_threshold_request(
        spec, state, validator_index, threshold
    )

    yield from run_set_sweep_threshold_request_processing(spec, state, set_sweep_threshold_request)

    assert state.validator_sweep_thresholds[validator_index] == threshold
    # No other threshold was touched
    assert all(
        threshold == spec.Gwei(0)
        for threshold in state.validator_sweep_thresholds[:validator_index]
    )


@with_eip8148_and_later
@spec_state_test
def test_process_set_sweep_threshold_request__success_threshold_at_balance(spec, state):
    """
    Test that a threshold exactly equal to the validator's current balance is
    accepted. The balance guard only rejects thresholds strictly below the
    balance.
    """
    validator_index = 7
    threshold = spec.MIN_ACTIVATION_BALANCE + 7 * spec.EFFECTIVE_BALANCE_INCREMENT
    _set_compounding_validator(spec, state, validator_index, balance=threshold)
    assert state.balances[validator_index] == threshold

    set_sweep_threshold_request = prepare_set_sweep_threshold_request(
        spec, state, validator_index, threshold
    )

    yield from run_set_sweep_threshold_request_processing(spec, state, set_sweep_threshold_request)

    assert state.validator_sweep_thresholds[validator_index] == threshold


@with_eip8148_and_later
@spec_state_test
def test_process_set_sweep_threshold_request__success_after_switch_to_compounding(spec, state):
    """
    Test setting a sweep threshold on a validator that switched to compounding
    credentials via consolidation. The switch sets the sweep threshold to the
    maximum value, but the validator can set a custom one afterwards.
    """
    validator_index = 7
    set_eth1_withdrawal_credential_with_balance(
        spec, state, validator_index, balance=spec.MIN_ACTIVATION_BALANCE
    )
    spec.switch_to_compounding_validator(state, spec.ValidatorIndex(validator_index))
    assert state.validator_sweep_thresholds[validator_index] == spec.MAX_EFFECTIVE_BALANCE_ELECTRA

    threshold = spec.MIN_ACTIVATION_BALANCE
    set_sweep_threshold_request = prepare_set_sweep_threshold_request(
        spec, state, validator_index, threshold
    )

    yield from run_set_sweep_threshold_request_processing(spec, state, set_sweep_threshold_request)

    assert state.validator_sweep_thresholds[validator_index] == threshold


@with_eip8148_and_later
@spec_state_test
def test_process_set_sweep_threshold_request__success_max_threshold(spec, state):
    """Test setting the maximum sweep threshold on a compounding validator."""
    validator_index = 7
    _set_compounding_validator(spec, state, validator_index)
    assert state.balances[validator_index] == spec.MAX_EFFECTIVE_BALANCE_ELECTRA
    threshold = spec.MAX_EFFECTIVE_BALANCE_ELECTRA
    state.validator_sweep_thresholds[validator_index] = spec.MIN_ACTIVATION_BALANCE
    assert state.validator_sweep_thresholds[validator_index] != threshold

    set_sweep_threshold_request = prepare_set_sweep_threshold_request(
        spec, state, validator_index, threshold
    )

    yield from run_set_sweep_threshold_request_processing(spec, state, set_sweep_threshold_request)

    assert state.validator_sweep_thresholds[validator_index] == threshold


@with_eip8148_and_later
@spec_state_test
def test_process_set_sweep_threshold_request__success_lower_existing_threshold(spec, state):
    """Test lowering an existing threshold when the balance is below the new threshold."""
    validator_index = 7
    _set_compounding_validator(spec, state, validator_index, balance=spec.MIN_ACTIVATION_BALANCE)
    state.validator_sweep_thresholds[validator_index] = spec.MAX_EFFECTIVE_BALANCE_ELECTRA
    threshold = spec.MIN_ACTIVATION_BALANCE + 7 * spec.EFFECTIVE_BALANCE_INCREMENT

    set_sweep_threshold_request = prepare_set_sweep_threshold_request(
        spec, state, validator_index, threshold
    )

    yield from run_set_sweep_threshold_request_processing(spec, state, set_sweep_threshold_request)

    assert state.validator_sweep_thresholds[validator_index] == threshold


@with_eip8148_and_later
@spec_state_test
def test_process_set_sweep_threshold_request__success_pending_activation(spec, state):
    """
    Test setting a sweep threshold on a validator that is in the registry but
    has not been activated yet.
    """
    validator_index = 7
    _set_compounding_validator(spec, state, validator_index, balance=spec.MIN_ACTIVATION_BALANCE)
    validator = state.validators[validator_index]
    validator.activation_eligibility_epoch = spec.FAR_FUTURE_EPOCH
    validator.activation_epoch = spec.FAR_FUTURE_EPOCH
    assert not spec.is_active_validator(validator, spec.get_current_epoch(state))

    threshold = spec.MIN_ACTIVATION_BALANCE
    set_sweep_threshold_request = prepare_set_sweep_threshold_request(
        spec, state, validator_index, threshold
    )

    yield from run_set_sweep_threshold_request_processing(spec, state, set_sweep_threshold_request)

    assert state.validator_sweep_thresholds[validator_index] == threshold


@with_eip8148_and_later
@spec_state_test
def test_process_set_sweep_threshold_request__unknown_pubkey(spec, state):
    """Test that a request for an unknown validator pubkey is a no-op."""
    validator_index = 7
    _set_compounding_validator(spec, state, validator_index, balance=spec.MIN_ACTIVATION_BALANCE)

    unknown_pubkey = pubkeys[len(state.validators)]
    assert unknown_pubkey not in [v.pubkey for v in state.validators]

    set_sweep_threshold_request = spec.SetSweepThresholdRequest(
        source_address=state.validators[validator_index].withdrawal_credentials[12:],
        validator_pubkey=unknown_pubkey,
        threshold=spec.MIN_ACTIVATION_BALANCE,
    )

    yield from run_set_sweep_threshold_request_processing(
        spec, state, set_sweep_threshold_request, noop=True
    )


@with_eip8148_and_later
@spec_state_test
def test_process_set_sweep_threshold_request__non_compounding_credential(spec, state):
    """Test that a request for a validator without compounding credentials is a no-op."""
    validator_index = 7
    set_eth1_withdrawal_credential_with_balance(
        spec, state, validator_index, balance=spec.MIN_ACTIVATION_BALANCE
    )

    set_sweep_threshold_request = prepare_set_sweep_threshold_request(
        spec, state, validator_index, spec.MIN_ACTIVATION_BALANCE
    )

    yield from run_set_sweep_threshold_request_processing(
        spec, state, set_sweep_threshold_request, noop=True
    )


@with_eip8148_and_later
@spec_state_test
def test_process_set_sweep_threshold_request__wrong_source_address(spec, state):
    """Test that a request from the wrong source address is a no-op."""
    validator_index = 7
    _set_compounding_validator(spec, state, validator_index, balance=spec.MIN_ACTIVATION_BALANCE)

    wrong_address = b"\x42" * 20
    assert state.validators[validator_index].withdrawal_credentials[12:] != wrong_address

    set_sweep_threshold_request = prepare_set_sweep_threshold_request(
        spec, state, validator_index, spec.MIN_ACTIVATION_BALANCE, source_address=wrong_address
    )

    yield from run_set_sweep_threshold_request_processing(
        spec, state, set_sweep_threshold_request, noop=True
    )


@with_eip8148_and_later
@spec_state_test
def test_process_set_sweep_threshold_request__exited_validator(spec, state):
    """Test that a request for a validator with an initiated exit is a no-op."""
    validator_index = 7
    _set_compounding_validator(spec, state, validator_index, balance=spec.MIN_ACTIVATION_BALANCE)
    state.validators[validator_index].exit_epoch = spec.get_current_epoch(state) + 1

    set_sweep_threshold_request = prepare_set_sweep_threshold_request(
        spec, state, validator_index, spec.MIN_ACTIVATION_BALANCE
    )

    yield from run_set_sweep_threshold_request_processing(
        spec, state, set_sweep_threshold_request, noop=True
    )


@with_eip8148_and_later
@spec_state_test
def test_process_set_sweep_threshold_request__same_threshold(spec, state):
    """
    Test that a request equal to the current threshold leaves the state
    unchanged. The spec has no explicit guard for this case; the assignment is
    idempotent. This case is covered for clients that handle it as a distinct
    request shape.
    """
    validator_index = 7
    _set_compounding_validator(spec, state, validator_index, balance=spec.MIN_ACTIVATION_BALANCE)
    threshold = spec.MIN_ACTIVATION_BALANCE
    state.validator_sweep_thresholds[validator_index] = threshold

    set_sweep_threshold_request = prepare_set_sweep_threshold_request(
        spec, state, validator_index, threshold
    )

    yield from run_set_sweep_threshold_request_processing(
        spec, state, set_sweep_threshold_request, noop=True
    )


@with_eip8148_and_later
@spec_state_test
def test_process_set_sweep_threshold_request__threshold_below_balance(spec, state):
    """
    Test that a request with a threshold below the validator's current balance
    is a no-op. This prevents bypassing the partial withdrawal queue.
    """
    validator_index = 7
    _set_compounding_validator(spec, state, validator_index)
    threshold = spec.MIN_ACTIVATION_BALANCE
    assert threshold < state.balances[validator_index]

    set_sweep_threshold_request = prepare_set_sweep_threshold_request(
        spec, state, validator_index, threshold
    )

    yield from run_set_sweep_threshold_request_processing(
        spec, state, set_sweep_threshold_request, noop=True
    )


@with_eip8148_and_later
@spec_state_test
def test_process_set_sweep_threshold_request__threshold_not_multiple_of_increment(spec, state):
    """Test that a threshold not divisible by EFFECTIVE_BALANCE_INCREMENT is a no-op."""
    validator_index = 7
    _set_compounding_validator(spec, state, validator_index, balance=spec.MIN_ACTIVATION_BALANCE)
    threshold = spec.MIN_ACTIVATION_BALANCE + spec.Gwei(1)
    assert threshold % spec.EFFECTIVE_BALANCE_INCREMENT != 0

    set_sweep_threshold_request = prepare_set_sweep_threshold_request(
        spec, state, validator_index, threshold
    )

    yield from run_set_sweep_threshold_request_processing(
        spec, state, set_sweep_threshold_request, noop=True
    )


@with_eip8148_and_later
@spec_state_test
def test_process_set_sweep_threshold_request__threshold_below_minimum(spec, state):
    """Test that a threshold below MIN_ACTIVATION_BALANCE is a no-op."""
    validator_index = 7
    threshold = spec.MIN_ACTIVATION_BALANCE - spec.EFFECTIVE_BALANCE_INCREMENT
    _set_compounding_validator(spec, state, validator_index, balance=threshold)
    assert threshold >= state.balances[validator_index]
    assert threshold % spec.EFFECTIVE_BALANCE_INCREMENT == 0

    set_sweep_threshold_request = prepare_set_sweep_threshold_request(
        spec, state, validator_index, threshold
    )

    yield from run_set_sweep_threshold_request_processing(
        spec, state, set_sweep_threshold_request, noop=True
    )


@with_eip8148_and_later
@spec_state_test
def test_process_set_sweep_threshold_request__threshold_above_maximum(spec, state):
    """Test that a threshold above MAX_EFFECTIVE_BALANCE_ELECTRA is a no-op."""
    validator_index = 7
    _set_compounding_validator(spec, state, validator_index, balance=spec.MIN_ACTIVATION_BALANCE)
    threshold = spec.MAX_EFFECTIVE_BALANCE_ELECTRA + spec.EFFECTIVE_BALANCE_INCREMENT
    assert threshold % spec.EFFECTIVE_BALANCE_INCREMENT == 0

    set_sweep_threshold_request = prepare_set_sweep_threshold_request(
        spec, state, validator_index, threshold
    )

    yield from run_set_sweep_threshold_request_processing(
        spec, state, set_sweep_threshold_request, noop=True
    )
