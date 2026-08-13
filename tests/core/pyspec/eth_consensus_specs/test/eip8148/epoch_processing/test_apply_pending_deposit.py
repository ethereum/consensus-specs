from eth_consensus_specs.test.context import (
    spec_state_test,
    with_eip8148_and_later,
)
from eth_consensus_specs.test.helpers.deposits import (
    prepare_pending_deposit,
    run_pending_deposit_applying,
)
from eth_consensus_specs.test.helpers.withdrawals import (
    set_compounding_withdrawal_credential_with_balance,
)


def _get_withdrawal_credentials(spec, prefix, threshold):
    increments = int(threshold // spec.EFFECTIVE_BALANCE_INCREMENT)
    return prefix + b"\x42" * 9 + increments.to_bytes(2, spec.ENDIANNESS) + b"\x59" * 20


@with_eip8148_and_later
@spec_state_test
def test_apply_pending_deposit_new_validator_compounding_credentials(spec, state):
    """
    Test that a validator added to the registry with compounding withdrawal
    credentials and a zero encoded threshold gets the default maximum threshold.
    """
    # fresh deposit = next validator index = validator appended to registry
    validator_index = len(state.validators)
    withdrawal_credentials = _get_withdrawal_credentials(
        spec, spec.COMPOUNDING_WITHDRAWAL_PREFIX, spec.Gwei(0)
    )
    amount = spec.MIN_ACTIVATION_BALANCE
    pending_deposit = prepare_pending_deposit(
        spec,
        validator_index,
        amount,
        withdrawal_credentials=withdrawal_credentials,
        signed=True,
    )

    yield from run_pending_deposit_applying(spec, state, pending_deposit, validator_index)

    assert len(state.validator_sweep_thresholds) == len(state.validators)
    assert state.validator_sweep_thresholds[validator_index] == spec.MAX_EFFECTIVE_BALANCE_ELECTRA


@with_eip8148_and_later
@spec_state_test
def test_apply_pending_deposit_new_validator_custom_sweep_threshold(spec, state):
    """Test decoding a custom sweep threshold from compounding credentials."""
    validator_index = len(state.validators)
    threshold = spec.Gwei(258) * spec.EFFECTIVE_BALANCE_INCREMENT
    withdrawal_credentials = _get_withdrawal_credentials(
        spec, spec.COMPOUNDING_WITHDRAWAL_PREFIX, threshold
    )
    pending_deposit = prepare_pending_deposit(
        spec,
        validator_index,
        spec.MAX_EFFECTIVE_BALANCE_ELECTRA,
        withdrawal_credentials=withdrawal_credentials,
        signed=True,
    )

    yield from run_pending_deposit_applying(spec, state, pending_deposit, validator_index)

    assert state.validators[validator_index].withdrawal_credentials == withdrawal_credentials
    assert state.validators[validator_index].effective_balance == spec.MAX_EFFECTIVE_BALANCE_ELECTRA
    assert len(state.validator_sweep_thresholds) == len(state.validators)
    assert state.validator_sweep_thresholds[validator_index] == threshold


@with_eip8148_and_later
@spec_state_test
def test_apply_pending_deposit_sweep_threshold_at_minimum(spec, state):
    """Test accepting an encoded threshold at the minimum boundary."""
    validator_index = len(state.validators)
    threshold = spec.MIN_ACTIVATION_BALANCE
    withdrawal_credentials = _get_withdrawal_credentials(
        spec, spec.COMPOUNDING_WITHDRAWAL_PREFIX, threshold
    )
    pending_deposit = prepare_pending_deposit(
        spec,
        validator_index,
        spec.MIN_ACTIVATION_BALANCE,
        withdrawal_credentials=withdrawal_credentials,
        signed=True,
    )

    yield from run_pending_deposit_applying(spec, state, pending_deposit, validator_index)

    assert len(state.validator_sweep_thresholds) == len(state.validators)
    assert state.validator_sweep_thresholds[validator_index] == threshold


@with_eip8148_and_later
@spec_state_test
def test_apply_pending_deposit_sweep_threshold_below_minimum(spec, state):
    """Test that a nonzero threshold below the minimum falls back to the maximum."""
    validator_index = len(state.validators)
    encoded_threshold = spec.MIN_ACTIVATION_BALANCE - spec.EFFECTIVE_BALANCE_INCREMENT
    withdrawal_credentials = _get_withdrawal_credentials(
        spec, spec.COMPOUNDING_WITHDRAWAL_PREFIX, encoded_threshold
    )
    pending_deposit = prepare_pending_deposit(
        spec,
        validator_index,
        spec.MIN_ACTIVATION_BALANCE,
        withdrawal_credentials=withdrawal_credentials,
        signed=True,
    )

    yield from run_pending_deposit_applying(spec, state, pending_deposit, validator_index)

    assert len(state.validator_sweep_thresholds) == len(state.validators)
    assert state.validator_sweep_thresholds[validator_index] == spec.MAX_EFFECTIVE_BALANCE_ELECTRA


@with_eip8148_and_later
@spec_state_test
def test_apply_pending_deposit_sweep_threshold_above_maximum(spec, state):
    """Test that an encoded threshold above the maximum falls back to the maximum."""
    validator_index = len(state.validators)
    encoded_threshold = spec.MAX_EFFECTIVE_BALANCE_ELECTRA + spec.EFFECTIVE_BALANCE_INCREMENT
    withdrawal_credentials = _get_withdrawal_credentials(
        spec, spec.COMPOUNDING_WITHDRAWAL_PREFIX, encoded_threshold
    )
    pending_deposit = prepare_pending_deposit(
        spec,
        validator_index,
        spec.MIN_ACTIVATION_BALANCE,
        withdrawal_credentials=withdrawal_credentials,
        signed=True,
    )

    yield from run_pending_deposit_applying(spec, state, pending_deposit, validator_index)

    assert len(state.validator_sweep_thresholds) == len(state.validators)
    assert state.validator_sweep_thresholds[validator_index] == spec.MAX_EFFECTIVE_BALANCE_ELECTRA


@with_eip8148_and_later
@spec_state_test
def test_apply_pending_deposit_new_validator_eth1_credentials(spec, state):
    """
    Test that a validator added to the registry with eth1 withdrawal
    credentials gets a zero sweep threshold.
    """
    # fresh deposit = next validator index = validator appended to registry
    validator_index = len(state.validators)
    encoded_threshold = spec.MIN_ACTIVATION_BALANCE + 7 * spec.EFFECTIVE_BALANCE_INCREMENT
    withdrawal_credentials = _get_withdrawal_credentials(
        spec, spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX, encoded_threshold
    )
    amount = spec.MIN_ACTIVATION_BALANCE
    pending_deposit = prepare_pending_deposit(
        spec,
        validator_index,
        amount,
        withdrawal_credentials=withdrawal_credentials,
        signed=True,
    )

    yield from run_pending_deposit_applying(spec, state, pending_deposit, validator_index)

    assert len(state.validator_sweep_thresholds) == len(state.validators)
    assert state.validator_sweep_thresholds[validator_index] == spec.Gwei(0)


@with_eip8148_and_later
@spec_state_test
def test_apply_pending_deposit_top_up_keeps_sweep_threshold(spec, state):
    """
    Test that a top-up of an existing validator does not touch its custom sweep
    threshold.
    """
    validator_index = 0
    set_compounding_withdrawal_credential_with_balance(
        spec, state, validator_index, balance=spec.MIN_ACTIVATION_BALANCE
    )
    threshold = spec.MIN_ACTIVATION_BALANCE + 7 * spec.EFFECTIVE_BALANCE_INCREMENT
    state.validator_sweep_thresholds[validator_index] = threshold

    amount = spec.MIN_ACTIVATION_BALANCE // 4
    deposit_threshold = threshold + spec.EFFECTIVE_BALANCE_INCREMENT
    withdrawal_credentials = _get_withdrawal_credentials(
        spec, spec.COMPOUNDING_WITHDRAWAL_PREFIX, deposit_threshold
    )
    pending_deposit = prepare_pending_deposit(
        spec,
        validator_index,
        amount,
        withdrawal_credentials=withdrawal_credentials,
        signed=True,
    )
    pre_thresholds_count = len(state.validator_sweep_thresholds)

    yield from run_pending_deposit_applying(spec, state, pending_deposit, validator_index)

    assert len(state.validator_sweep_thresholds) == len(state.validators)
    assert len(state.validator_sweep_thresholds) == pre_thresholds_count
    assert state.validator_sweep_thresholds[validator_index] == threshold
