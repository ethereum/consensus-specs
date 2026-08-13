from eth_consensus_specs.test.context import (
    spec_state_test,
    with_eip8148_and_later,
)
from eth_consensus_specs.test.helpers.withdrawals import (
    assert_process_withdrawals,
    check_is_partially_withdrawable_validator,
    prepare_pending_withdrawal,
    set_compounding_withdrawal_credential_with_balance,
    set_parent_block_full,
    set_validator_fully_withdrawable,
)


def run_eip8148_withdrawals_processing(spec, state):
    """
    Minimal test harness for process_withdrawals that generates vectors.
    """

    yield "pre", state
    spec.process_withdrawals(state)
    yield "post", state


@with_eip8148_and_later
@spec_state_test
def test_sweep_custom_threshold_partial_withdrawal(spec, state):
    """
    Test that a compounding validator with a custom sweep threshold gets a
    partial withdrawal of the balance in excess of the threshold, even though
    its balance is far below the max effective balance.
    """
    validator_index = 0
    threshold = spec.MIN_ACTIVATION_BALANCE + 7 * spec.EFFECTIVE_BALANCE_INCREMENT
    excess = spec.Gwei(1_000_000_000)

    set_compounding_withdrawal_credential_with_balance(
        spec, state, validator_index, effective_balance=threshold, balance=threshold + excess
    )
    state.validator_sweep_thresholds[validator_index] = threshold
    set_parent_block_full(spec, state)

    # Without the custom threshold, this validator would not be withdrawable
    assert state.balances[validator_index] < spec.MAX_EFFECTIVE_BALANCE_ELECTRA
    assert check_is_partially_withdrawable_validator(spec, state, validator_index)

    pre_state = state.copy()

    yield from run_eip8148_withdrawals_processing(spec, state)

    assert_process_withdrawals(
        spec,
        state,
        pre_state,
        withdrawal_count=1,
        withdrawal_amounts={validator_index: excess},
        balance_deltas={validator_index: -int(excess)},
        withdrawal_index_delta=1,
    )
    assert state.balances[validator_index] == threshold


@with_eip8148_and_later
@spec_state_test
def test_sweep_custom_threshold_effective_balance_above_threshold(spec, state):
    """
    Test that the partial withdrawal amount is computed against the custom sweep
    threshold and not against the validator's effective balance, when the
    effective balance is transiently above a newly configured threshold.
    """
    validator_index = 0
    threshold = spec.MIN_ACTIVATION_BALANCE + 7 * spec.EFFECTIVE_BALANCE_INCREMENT
    excess = 5 * spec.EFFECTIVE_BALANCE_INCREMENT
    balance = threshold + excess

    set_compounding_withdrawal_credential_with_balance(
        spec, state, validator_index, effective_balance=balance, balance=balance
    )
    state.validator_sweep_thresholds[validator_index] = threshold
    set_parent_block_full(spec, state)

    # The effective balance is strictly above the threshold, so the withdrawal
    # amount is only relative to the threshold
    assert state.validators[validator_index].effective_balance > threshold
    assert check_is_partially_withdrawable_validator(spec, state, validator_index)

    pre_state = state.copy()

    yield from run_eip8148_withdrawals_processing(spec, state)

    assert_process_withdrawals(
        spec,
        state,
        pre_state,
        withdrawal_count=1,
        withdrawal_amounts={validator_index: excess},
        balance_deltas={validator_index: -int(excess)},
        withdrawal_index_delta=1,
    )
    assert state.balances[validator_index] == threshold


@with_eip8148_and_later
@spec_state_test
def test_sweep_custom_threshold_balance_at_threshold(spec, state):
    """
    Test that a validator whose balance is exactly at its custom sweep
    threshold gets no partial withdrawal.
    """
    validator_index = 0
    threshold = spec.MIN_ACTIVATION_BALANCE + 7 * spec.EFFECTIVE_BALANCE_INCREMENT

    set_compounding_withdrawal_credential_with_balance(
        spec, state, validator_index, effective_balance=threshold, balance=threshold
    )
    state.validator_sweep_thresholds[validator_index] = threshold
    set_parent_block_full(spec, state)

    assert not check_is_partially_withdrawable_validator(spec, state, validator_index)

    pre_state = state.copy()

    yield from run_eip8148_withdrawals_processing(spec, state)

    assert_process_withdrawals(
        spec,
        state,
        pre_state,
        withdrawal_count=0,
        no_withdrawal_indices=[validator_index],
    )


@with_eip8148_and_later
@spec_state_test
def test_sweep_custom_threshold_low_effective_balance(spec, state):
    """
    Test that a validator whose effective balance is below its custom sweep
    threshold gets no partial withdrawal, despite having excess balance.
    """
    validator_index = 0
    threshold = spec.MIN_ACTIVATION_BALANCE + 15 * spec.EFFECTIVE_BALANCE_INCREMENT
    effective_balance = threshold - spec.EFFECTIVE_BALANCE_INCREMENT

    set_compounding_withdrawal_credential_with_balance(
        spec,
        state,
        validator_index,
        effective_balance=effective_balance,
        balance=threshold + spec.Gwei(1_000_000_000),
    )
    state.validator_sweep_thresholds[validator_index] = threshold
    set_parent_block_full(spec, state)

    assert not check_is_partially_withdrawable_validator(spec, state, validator_index)

    pre_state = state.copy()

    yield from run_eip8148_withdrawals_processing(spec, state)

    assert_process_withdrawals(
        spec,
        state,
        pre_state,
        withdrawal_count=0,
        no_withdrawal_indices=[validator_index],
    )


@with_eip8148_and_later
@spec_state_test
def test_sweep_default_threshold_compounding(spec, state):
    """
    Test that a compounding validator with the default maximum sweep threshold
    keeps the pre-EIP8148 withdrawal behavior.
    """
    validator_index = 0
    excess = spec.Gwei(1_000_000_000)

    set_compounding_withdrawal_credential_with_balance(
        spec, state, validator_index, balance=spec.MAX_EFFECTIVE_BALANCE_ELECTRA + excess
    )
    state.validator_sweep_thresholds[validator_index] = spec.MAX_EFFECTIVE_BALANCE_ELECTRA
    set_parent_block_full(spec, state)

    assert state.validator_sweep_thresholds[validator_index] == spec.MAX_EFFECTIVE_BALANCE_ELECTRA
    assert check_is_partially_withdrawable_validator(spec, state, validator_index)

    pre_state = state.copy()

    yield from run_eip8148_withdrawals_processing(spec, state)

    assert_process_withdrawals(
        spec,
        state,
        pre_state,
        withdrawal_count=1,
        withdrawal_amounts={validator_index: excess},
        balance_deltas={validator_index: -int(excess)},
        withdrawal_index_delta=1,
    )
    assert state.balances[validator_index] == spec.MAX_EFFECTIVE_BALANCE_ELECTRA


@with_eip8148_and_later
@spec_state_test
def test_sweep_full_withdrawal_ignores_custom_threshold(spec, state):
    """
    Test that a fully withdrawable validator withdraws its entire balance,
    regardless of its custom sweep threshold.
    """
    validator_index = 0
    threshold = spec.MIN_ACTIVATION_BALANCE + 15 * spec.EFFECTIVE_BALANCE_INCREMENT
    balance = threshold + spec.Gwei(1_000_000_000)

    set_compounding_withdrawal_credential_with_balance(
        spec, state, validator_index, effective_balance=threshold, balance=balance
    )
    state.validator_sweep_thresholds[validator_index] = threshold
    set_validator_fully_withdrawable(spec, state, validator_index)
    set_parent_block_full(spec, state)

    pre_state = state.copy()

    yield from run_eip8148_withdrawals_processing(spec, state)

    assert_process_withdrawals(
        spec,
        state,
        pre_state,
        withdrawal_count=1,
        withdrawal_amounts={validator_index: balance},
        balances={validator_index: spec.Gwei(0)},
        withdrawal_index_delta=1,
    )


@with_eip8148_and_later
@spec_state_test
def test_sweep_mixed_thresholds(spec, state):
    """
    Test the sweep with two compounding validators: one with a custom
    threshold and one with the default threshold. Both get partial
    withdrawals with amounts relative to their respective thresholds.
    """
    custom_index = 0
    default_index = 1
    threshold = spec.MIN_ACTIVATION_BALANCE
    custom_excess = spec.Gwei(2_000_000_000)
    default_excess = spec.Gwei(1_000_000_000)

    set_compounding_withdrawal_credential_with_balance(
        spec, state, custom_index, effective_balance=threshold, balance=threshold + custom_excess
    )
    state.validator_sweep_thresholds[custom_index] = threshold
    set_compounding_withdrawal_credential_with_balance(
        spec, state, default_index, balance=spec.MAX_EFFECTIVE_BALANCE_ELECTRA + default_excess
    )
    state.validator_sweep_thresholds[default_index] = spec.MAX_EFFECTIVE_BALANCE_ELECTRA
    set_parent_block_full(spec, state)

    assert check_is_partially_withdrawable_validator(spec, state, custom_index)
    assert check_is_partially_withdrawable_validator(spec, state, default_index)

    pre_state = state.copy()

    yield from run_eip8148_withdrawals_processing(spec, state)

    assert_process_withdrawals(
        spec,
        state,
        pre_state,
        withdrawal_count=2,
        withdrawal_order=[custom_index, default_index],
        withdrawal_amounts={
            custom_index: custom_excess,
            default_index: default_excess,
        },
        balance_deltas={
            custom_index: -int(custom_excess),
            default_index: -int(default_excess),
        },
        withdrawal_index_delta=2,
    )


@with_eip8148_and_later
@spec_state_test
def test_sweep_custom_threshold_exit_initiated_validator(spec, state):
    """
    Test that a validator with an initiated but not yet completed exit still
    gets partial withdrawals relative to its custom sweep threshold. The sweep
    does not consider the exit status, matching the pre-EIP8148 behavior for
    validators at the max effective balance.
    """
    validator_index = 0
    threshold = spec.MIN_ACTIVATION_BALANCE + 7 * spec.EFFECTIVE_BALANCE_INCREMENT
    excess = 5 * spec.EFFECTIVE_BALANCE_INCREMENT
    balance = threshold + excess

    set_compounding_withdrawal_credential_with_balance(
        spec, state, validator_index, effective_balance=balance, balance=balance
    )
    state.validator_sweep_thresholds[validator_index] = threshold
    validator = state.validators[validator_index]
    validator.exit_epoch = spec.get_current_epoch(state) + 2
    validator.withdrawable_epoch = (
        validator.exit_epoch + spec.config.MIN_VALIDATOR_WITHDRAWABILITY_DELAY
    )
    set_parent_block_full(spec, state)

    epoch = spec.get_current_epoch(state)
    assert not spec.is_fully_withdrawable_validator(validator, balance, epoch)
    assert check_is_partially_withdrawable_validator(spec, state, validator_index)

    pre_state = state.copy()

    yield from run_eip8148_withdrawals_processing(spec, state)

    assert_process_withdrawals(
        spec,
        state,
        pre_state,
        withdrawal_count=1,
        withdrawal_amounts={validator_index: excess},
        balance_deltas={validator_index: -int(excess)},
        withdrawal_index_delta=1,
    )
    assert state.balances[validator_index] == threshold


@with_eip8148_and_later
@spec_state_test
def test_sweep_custom_threshold_with_pending_partial_withdrawal(spec, state):
    """
    Test that the sweep compares the balance remaining after the prior
    withdrawals of the same payload against the custom sweep threshold.
    """
    validator_index = 0
    threshold = spec.MIN_ACTIVATION_BALANCE + 7 * spec.EFFECTIVE_BALANCE_INCREMENT
    effective_balance = spec.MIN_ACTIVATION_BALANCE + 12 * spec.EFFECTIVE_BALANCE_INCREMENT
    pending_amount = 3 * spec.EFFECTIVE_BALANCE_INCREMENT

    prepare_pending_withdrawal(
        spec,
        state,
        validator_index,
        effective_balance=effective_balance,
        amount=pending_amount,
    )
    state.validator_sweep_thresholds[validator_index] = threshold
    set_parent_block_full(spec, state)

    # The sweep withdraws what is left above the threshold once the pending
    # partial withdrawal of the same payload has been accounted for
    balance = state.balances[validator_index]
    sweep_amount = balance - pending_amount - threshold
    assert check_is_partially_withdrawable_validator(spec, state, validator_index)

    pre_state = state.copy()

    yield from run_eip8148_withdrawals_processing(spec, state)

    assert_process_withdrawals(
        spec,
        state,
        pre_state,
        withdrawal_count=2,
        balances={validator_index: threshold},
        pending_partial_delta=-1,
        withdrawal_index_delta=2,
    )
    withdrawals = list(state.payload_expected_withdrawals)
    assert [w.validator_index for w in withdrawals] == [validator_index, validator_index]
    assert [w.amount for w in withdrawals] == [pending_amount, sweep_amount]


@with_eip8148_and_later
@spec_state_test
def test_sweep_custom_thresholds_reach_withdrawals_limit(spec, state):
    """
    Test that the sweep of validators with custom sweep thresholds stops at
    ``MAX_WITHDRAWALS_PER_PAYLOAD`` and that the next sweep resumes at the
    validator following the last withdrawal.
    """
    withdrawals_limit = spec.MAX_WITHDRAWALS_PER_PAYLOAD
    withdrawable_count = withdrawals_limit + 1
    assert withdrawable_count <= min(
        len(state.validators), spec.MAX_VALIDATORS_PER_WITHDRAWALS_SWEEP
    )

    threshold = spec.MIN_ACTIVATION_BALANCE
    effective_balance = threshold + spec.EFFECTIVE_BALANCE_INCREMENT
    excess = 2 * spec.EFFECTIVE_BALANCE_INCREMENT
    balance = effective_balance + excess
    withdrawal_amount = balance - threshold

    state.next_withdrawal_validator_index = 0
    for validator_index in range(withdrawable_count):
        set_compounding_withdrawal_credential_with_balance(
            spec, state, validator_index, effective_balance=effective_balance, balance=balance
        )
        state.validator_sweep_thresholds[validator_index] = threshold
        assert check_is_partially_withdrawable_validator(spec, state, validator_index)
    set_parent_block_full(spec, state)

    withdrawn_indices = list(range(withdrawals_limit))
    skipped_index = withdrawals_limit

    pre_state = state.copy()

    yield from run_eip8148_withdrawals_processing(spec, state)

    assert_process_withdrawals(
        spec,
        state,
        pre_state,
        withdrawal_count=withdrawals_limit,
        withdrawal_order=withdrawn_indices,
        withdrawal_amounts=dict.fromkeys(withdrawn_indices, withdrawal_amount),
        balance_deltas={
            **{index: -int(withdrawal_amount) for index in withdrawn_indices},
            skipped_index: 0,
        },
        no_withdrawal_indices=[skipped_index],
        withdrawal_index_delta=withdrawals_limit,
    )
    # The next sweep resumes at the validator that did not fit in the payload
    assert state.next_withdrawal_validator_index == skipped_index
