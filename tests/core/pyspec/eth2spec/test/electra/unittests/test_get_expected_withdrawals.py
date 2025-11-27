"""
Comprehensive tests for get_expected_withdrawals function - Electra version

Tests cover Electra-specific features: pending partial withdrawals queue and compounding validators.
"""

import pytest

from eth2spec.test.context import (
    spec_state_test,
    with_electra_and_later,
)
from eth2spec.test.helpers.withdrawals import (
    set_compounding_withdrawal_credential_with_balance,
)
from tests.infra.helpers.withdrawals import (
    get_expected_withdrawals,
    prepare_withdrawals,
)

#
# Electra-Specific Tests - Pending Partial Withdrawals
#


@with_electra_and_later
@spec_state_test
def test_pending_partial_withdrawals_basic(spec, state):
    """ Pending partial withdrawals should be processed before validator sweep"""
    assert len(state.validators) >= 2, "Test requires at least 2 validators"

    pending_index = 1
    sweep_index = 0
    pending_amount = spec.Gwei(1_000_000_000)

    state.next_withdrawal_validator_index = sweep_index

    prepare_withdrawals(
        spec, state,
        pending_partial_indices=[pending_index],
        pending_partial_amounts=[pending_amount],
        pending_partial_withdrawable_offsets=[0],
        partial_withdrawal_indices=[sweep_index],
        partial_excess_balances=[spec.Gwei(2_000_000_000)],
    )

    withdrawals = get_expected_withdrawals(spec, state)

    assert len(withdrawals) == 2
    assert withdrawals[0].validator_index == pending_index
    assert withdrawals[0].amount == pending_amount
    assert withdrawals[1].validator_index == sweep_index


@with_electra_and_later
@spec_state_test
def test_pending_partial_max_per_sweep(spec, state):
    """ Should process only MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP pending partials per sweep"""
    num_pending = spec.MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP + 4

    assert len(state.validators) >= num_pending, f"Test requires at least {num_pending} validators"

    pending_indices = list(range(num_pending))

    prepare_withdrawals(
        spec, state,
        pending_partial_indices=pending_indices,
        pending_partial_amounts=[spec.Gwei(1_000_000_000)] * num_pending,
        pending_partial_withdrawable_offsets=[0] * num_pending,
    )

    withdrawals = get_expected_withdrawals(spec, state)

    pending_withdrawals = [w for w in withdrawals if w.validator_index in pending_indices]
    assert len(pending_withdrawals) == spec.MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP


@with_electra_and_later
@spec_state_test
def test_compounding_credentials(spec, state):
    """ Validator with COMPOUNDING_WITHDRAWAL_PREFIX credentials and max balance"""
    validator_index = 0
    excess_balance = spec.Gwei(10_000_000_000)  # 10 ETH excess

    set_compounding_withdrawal_credential_with_balance(
        spec, state, validator_index,
        effective_balance=spec.MAX_EFFECTIVE_BALANCE_ELECTRA,
        balance=spec.MAX_EFFECTIVE_BALANCE_ELECTRA + excess_balance,
    )

    withdrawals = get_expected_withdrawals(spec, state)

    assert len(withdrawals) == 1
    assert withdrawals[0].validator_index == validator_index
    assert withdrawals[0].amount == excess_balance


@with_electra_and_later
@spec_state_test
def test_multiple_withdrawals_same_validator(spec, state):
    """ Same validator appears multiple times in pending queue"""
    validator_index = 0
    amount_1 = spec.Gwei(1_000_000_000)  # 1 ETH
    amount_2 = spec.Gwei(2_000_000_000)  # 2 ETH

    set_compounding_withdrawal_credential_with_balance(
        spec, state, validator_index,
        effective_balance=spec.MAX_EFFECTIVE_BALANCE_ELECTRA,
        balance=spec.MAX_EFFECTIVE_BALANCE_ELECTRA + amount_1 + amount_2,
    )

    state.pending_partial_withdrawals.append(
        spec.PendingPartialWithdrawal(
            validator_index=validator_index,
            amount=amount_1,
            withdrawable_epoch=spec.get_current_epoch(state),
        )
    )
    state.pending_partial_withdrawals.append(
        spec.PendingPartialWithdrawal(
            validator_index=validator_index,
            amount=amount_2,
            withdrawable_epoch=spec.get_current_epoch(state),
        )
    )

    withdrawals = get_expected_withdrawals(spec, state)

    validator_withdrawals = [w for w in withdrawals if w.validator_index == validator_index]
    assert len(validator_withdrawals) == 2
    total_withdrawn = sum(w.amount for w in validator_withdrawals)
    assert total_withdrawn == amount_1 + amount_2


@with_electra_and_later
@spec_state_test
def test_pending_partial_exiting_validator_skipped(spec, state):
    """ Pending partial for exiting validator should be skipped"""
    validator_index = 0
    withdrawal_amount = spec.Gwei(1_000_000_000)

    prepare_withdrawals(
        spec, state,
        pending_partial_indices=[validator_index],
        pending_partial_amounts=[withdrawal_amount],
        pending_partial_withdrawable_offsets=[0],
    )

    state.validators[validator_index].exit_epoch = spec.get_current_epoch(state) + 1

    withdrawals = get_expected_withdrawals(spec, state)

    validator_withdrawals = [w for w in withdrawals if w.validator_index == validator_index]
    assert len(validator_withdrawals) == 0


@with_electra_and_later
@spec_state_test
def test_pending_partial_insufficient_balance(spec, state):
    """ Pending partial but balance < MIN_ACTIVATION_BALANCE should be skipped"""
    validator_index = 0
    withdrawal_amount = spec.Gwei(1_000_000_000)

    set_compounding_withdrawal_credential_with_balance(
        spec, state, validator_index,
        effective_balance=spec.MIN_ACTIVATION_BALANCE,
        balance=spec.MIN_ACTIVATION_BALANCE - spec.Gwei(1),  # Just below minimum
    )

    state.pending_partial_withdrawals.append(
        spec.PendingPartialWithdrawal(
            validator_index=validator_index,
            amount=withdrawal_amount,
            withdrawable_epoch=spec.get_current_epoch(state),
        )
    )

    withdrawals = get_expected_withdrawals(spec, state)

    validator_withdrawals = [w for w in withdrawals if w.validator_index == validator_index]
    assert len(validator_withdrawals) == 0


# Corner Cases - Electra+


@with_electra_and_later
@spec_state_test
def test_pending_partial_exact_min_activation_balance(spec, state):
    """ Validator balance exactly MIN_ACTIVATION_BALANCE, withdrawable amount should be 0"""
    validator_index = 0
    withdrawal_amount = spec.Gwei(1_000_000_000)

    set_compounding_withdrawal_credential_with_balance(
        spec, state, validator_index,
        effective_balance=spec.MIN_ACTIVATION_BALANCE,
        balance=spec.MIN_ACTIVATION_BALANCE,
    )

    state.pending_partial_withdrawals.append(
        spec.PendingPartialWithdrawal(
            validator_index=validator_index,
            amount=withdrawal_amount,
            withdrawable_epoch=spec.get_current_epoch(state),
        )
    )

    withdrawals = get_expected_withdrawals(spec, state)

    validator_withdrawals = [w for w in withdrawals if w.validator_index == validator_index]
    if len(validator_withdrawals) > 0:
        assert validator_withdrawals[0].amount == 0


@with_electra_and_later
@spec_state_test
def test_pending_partial_amount_exceeds_available(spec, state):
    """ Request 10 ETH, only 5 ETH available, should withdraw only 5 ETH"""
    validator_index = 0
    requested_amount = spec.Gwei(10_000_000_000)  # 10 ETH
    available_amount = spec.Gwei(5_000_000_000)  # 5 ETH

    set_compounding_withdrawal_credential_with_balance(
        spec, state, validator_index,
        effective_balance=spec.MIN_ACTIVATION_BALANCE,
        balance=spec.MIN_ACTIVATION_BALANCE + available_amount,
    )

    state.pending_partial_withdrawals.append(
        spec.PendingPartialWithdrawal(
            validator_index=validator_index,
            amount=requested_amount,
            withdrawable_epoch=spec.get_current_epoch(state),
        )
    )

    withdrawals = get_expected_withdrawals(spec, state)

    validator_withdrawals = [w for w in withdrawals if w.validator_index == validator_index]
    assert len(validator_withdrawals) == 1
    assert validator_withdrawals[0].amount == available_amount


@with_electra_and_later
@spec_state_test
def test_all_pending_partials_invalid(spec, state):
    """ All pending partials fail conditions, pending queue should not process them"""
    assert len(state.validators) >= 3, "Test requires at least 3 validators"

    for i in range(3):
        set_compounding_withdrawal_credential_with_balance(
            spec, state, i,
            effective_balance=spec.MAX_EFFECTIVE_BALANCE_ELECTRA,
            balance=spec.MAX_EFFECTIVE_BALANCE_ELECTRA,
        )
        state.pending_partial_withdrawals.append(
            spec.PendingPartialWithdrawal(
                validator_index=i,
                amount=spec.Gwei(1_000_000_000),
                withdrawable_epoch=spec.get_current_epoch(state),
            )
        )
        state.validators[i].exit_epoch = spec.get_current_epoch(state) + 1

    withdrawals = get_expected_withdrawals(spec, state)

    for i in range(3):
        assert not any(w.validator_index == i for w in withdrawals), f"Validator {i} with pending partial and exit_epoch set should not withdraw"


@with_electra_and_later
@spec_state_test
def test_pending_partials_and_sweep_together(spec, state):
    """Pending partials processed first, then regular sweep fills remaining slots"""
    num_pending = spec.MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP
    sweep_validator_index = num_pending

    assert len(state.validators) >= num_pending + 1, f"Test requires at least {num_pending + 1} validators"

    state.next_withdrawal_validator_index = sweep_validator_index

    pending_indices = list(range(num_pending))
    pending_amounts = [spec.Gwei(1_000_000_000)] * num_pending

    prepare_withdrawals(
        spec, state,
        pending_partial_indices=pending_indices,
        pending_partial_amounts=pending_amounts,
        pending_partial_withdrawable_offsets=[0] * num_pending,
        partial_withdrawal_indices=[sweep_validator_index],
        partial_excess_balances=[spec.Gwei(2_000_000_000)],
    )

    withdrawals = get_expected_withdrawals(spec, state)

    pending_count = sum(1 for w in withdrawals if w.validator_index in pending_indices)
    assert pending_count == spec.MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP, "Should process all pending partials up to limit"

    if pending_count < spec.MAX_WITHDRAWALS_PER_PAYLOAD:
        assert sweep_validator_index in [w.validator_index for w in withdrawals], "Regular sweep should fill remaining slots after pending partials"


@with_electra_and_later
@spec_state_test
def test_validator_depleted_by_multiple_partials(spec, state):
    """ Multiple pending partials drain validator balance, later ones get reduced"""
    validator_index = 0
    total_excess = spec.Gwei(5_000_000_000)  # 5 ETH excess
    amount_per_request = spec.Gwei(3_000_000_000)  # 3 ETH each

    set_compounding_withdrawal_credential_with_balance(
        spec, state, validator_index,
        effective_balance=spec.MIN_ACTIVATION_BALANCE,
        balance=spec.MIN_ACTIVATION_BALANCE + total_excess,
    )

    state.pending_partial_withdrawals.append(
        spec.PendingPartialWithdrawal(
            validator_index=validator_index,
            amount=amount_per_request,
            withdrawable_epoch=spec.get_current_epoch(state),
        )
    )
    state.pending_partial_withdrawals.append(
        spec.PendingPartialWithdrawal(
            validator_index=validator_index,
            amount=amount_per_request,
            withdrawable_epoch=spec.get_current_epoch(state),
        )
    )

    withdrawals = get_expected_withdrawals(spec, state)

    validator_withdrawals = [w for w in withdrawals if w.validator_index == validator_index]
    assert len(validator_withdrawals) == 2

    assert validator_withdrawals[0].amount == amount_per_request
    assert validator_withdrawals[1].amount == total_excess - amount_per_request

    total_withdrawn = sum(w.amount for w in validator_withdrawals)
    assert total_withdrawn == total_excess


# Edge Cases by Processing Phase


@with_electra_and_later
@spec_state_test
def test_pending_partial_future_epoch(spec, state):
    """ withdrawable_epoch > current_epoch should break processing pending queue"""
    validator_index_current = 10
    validator_index_future = 11
    validator_index_after = 12

    # Ensure we have enough validators
    assert len(state.validators) >= validator_index_after + 1, \
        f"Test requires at least {validator_index_after + 1} validators"

    withdrawal_amount = spec.Gwei(1_000_000_000)
    future_epoch = spec.get_current_epoch(state) + 10

    set_compounding_withdrawal_credential_with_balance(
        spec, state, validator_index_current,
        effective_balance=spec.MAX_EFFECTIVE_BALANCE_ELECTRA,
        balance=spec.MAX_EFFECTIVE_BALANCE_ELECTRA + withdrawal_amount,
    )

    set_compounding_withdrawal_credential_with_balance(
        spec, state, validator_index_future,
        effective_balance=spec.MAX_EFFECTIVE_BALANCE_ELECTRA,
        balance=spec.MAX_EFFECTIVE_BALANCE_ELECTRA,  # No excess
    )

    set_compounding_withdrawal_credential_with_balance(
        spec, state, validator_index_after,
        effective_balance=spec.MAX_EFFECTIVE_BALANCE_ELECTRA,
        balance=spec.MAX_EFFECTIVE_BALANCE_ELECTRA,  # No excess
    )

    state.pending_partial_withdrawals.append(
        spec.PendingPartialWithdrawal(
            validator_index=validator_index_current,
            amount=withdrawal_amount,
            withdrawable_epoch=spec.get_current_epoch(state),
        )
    )

    state.pending_partial_withdrawals.append(
        spec.PendingPartialWithdrawal(
            validator_index=validator_index_future,
            amount=withdrawal_amount,
            withdrawable_epoch=future_epoch,
        )
    )

    state.pending_partial_withdrawals.append(
        spec.PendingPartialWithdrawal(
            validator_index=validator_index_after,
            amount=withdrawal_amount,
            withdrawable_epoch=spec.get_current_epoch(state),  # Current epoch, but after break
        )
    )

    withdrawals = get_expected_withdrawals(spec, state)

    validator_withdrawals_current = [w for w in withdrawals if w.validator_index == validator_index_current]
    validator_withdrawals_future = [w for w in withdrawals if w.validator_index == validator_index_future]
    validator_withdrawals_after = [w for w in withdrawals if w.validator_index == validator_index_after]

    assert len(validator_withdrawals_current) == 1  # Should be processed
    assert len(validator_withdrawals_future) == 0  # Future, should be skipped
    assert len(validator_withdrawals_after) == 0  # After break, should be skipped


@with_electra_and_later
@spec_state_test
def test_pending_partial_invalid_validator_index(spec, state):
    """ Invalid validator index should raise IndexError"""
    invalid_index = len(state.validators) + 10

    state.pending_partial_withdrawals.append(
        spec.PendingPartialWithdrawal(
            validator_index=invalid_index,
            amount=spec.Gwei(1_000_000_000),
            withdrawable_epoch=spec.get_current_epoch(state),
        )
    )

    with pytest.raises(IndexError):
        get_expected_withdrawals(spec, state)


@with_electra_and_later
@spec_state_test
def test_pending_queue_fifo_order(spec, state):
    """ Multiple pending entries should process in FIFO order"""
    indices = [2, 0, 1]
    # Ensure we have enough validators
    required_validators = max(indices) + 1
    assert len(state.validators) >= required_validators, f"Test requires at least {required_validators} validators"


    for idx in indices:
        withdrawal_amount = spec.Gwei(1_000_000_000)  # 1 ETH
        set_compounding_withdrawal_credential_with_balance(
            spec, state, idx,
            effective_balance=spec.MAX_EFFECTIVE_BALANCE_ELECTRA,
            balance=spec.MAX_EFFECTIVE_BALANCE_ELECTRA + withdrawal_amount,  # Exact amount
        )
        state.pending_partial_withdrawals.append(
            spec.PendingPartialWithdrawal(
                validator_index=idx,
                amount=withdrawal_amount,
                withdrawable_epoch=spec.get_current_epoch(state),
            )
        )

    withdrawals = get_expected_withdrawals(spec, state)

    pending_withdrawals = withdrawals[:len(indices)]
    withdrawal_indices = [w.validator_index for w in pending_withdrawals]

    assert withdrawal_indices == indices
