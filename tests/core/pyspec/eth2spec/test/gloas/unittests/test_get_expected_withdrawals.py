"""
Comprehensive tests for get_expected_withdrawals function - Gloas version

Tests cover Gloas-specific features: builder withdrawals with three-tier priority system.
"""

import pytest

from eth2spec.test.context import (
    spec_state_test,
    with_gloas_and_later,
)
from eth2spec.test.helpers.withdrawals import (
    set_builder_withdrawal_credential_with_balance,
    set_compounding_withdrawal_credential_with_balance,
)
from tests.infra.helpers.withdrawals import (
    get_expected_withdrawals,
    prepare_withdrawals,
)

#
# Gloas-Only Tests - Builder Withdrawals
#


@with_gloas_and_later
@spec_state_test
def test_builder_withdrawals_processed_first(spec, state):
    """ Builder withdrawals should be processed before pending/regular"""
    builder_index = 0
    regular_index = 1

    set_builder_withdrawal_credential_with_balance(
        spec, state, builder_index,
        effective_balance=spec.MAX_EFFECTIVE_BALANCE_ELECTRA,
        balance=spec.MAX_EFFECTIVE_BALANCE_ELECTRA + spec.MIN_ACTIVATION_BALANCE,
    )

    prepare_withdrawals(
        spec, state,
        builder_indices=[builder_index],
        builder_withdrawal_amounts=[spec.MIN_ACTIVATION_BALANCE],
        builder_withdrawable_offsets=[0],
        full_withdrawal_indices=[regular_index],
        full_withdrawable_offsets=[0],
    )

    withdrawals = get_expected_withdrawals(spec, state)

    assert len(withdrawals) == 2
    assert withdrawals[0].validator_index == builder_index
    assert withdrawals[0].amount == spec.MIN_ACTIVATION_BALANCE
    assert withdrawals[1].validator_index == regular_index


@with_gloas_and_later
@spec_state_test
def test_builder_withdrawal_slashed_calculation(spec, state):
    """ Slashed builder vs non-slashed builder withdrawal calculation"""
    slashed_index = 0
    non_slashed_index = 1
    withdrawal_amount = spec.Gwei(10_000_000_000)  # 10 ETH

    set_builder_withdrawal_credential_with_balance(
        spec, state, slashed_index,
        effective_balance=spec.MAX_EFFECTIVE_BALANCE_ELECTRA,
        balance=spec.MIN_ACTIVATION_BALANCE + withdrawal_amount,
    )
    state.validators[slashed_index].slashed = True

    set_builder_withdrawal_credential_with_balance(
        spec, state, non_slashed_index,
        effective_balance=spec.MAX_EFFECTIVE_BALANCE_ELECTRA,
        balance=spec.MIN_ACTIVATION_BALANCE + withdrawal_amount,
    )
    state.validators[non_slashed_index].slashed = False

    prepare_withdrawals(
        spec, state,
        builder_indices=[slashed_index, non_slashed_index],
        builder_withdrawal_amounts=[withdrawal_amount, withdrawal_amount],
        builder_withdrawable_offsets=[0, 0],
    )

    withdrawals = get_expected_withdrawals(spec, state)

    assert len(withdrawals) == 2

    slashed_withdrawal = None
    non_slashed_withdrawal = None
    for w in withdrawals:
        if w.validator_index == slashed_index:
            slashed_withdrawal = w
        elif w.validator_index == non_slashed_index:
            non_slashed_withdrawal = w

    assert slashed_withdrawal is not None
    assert non_slashed_withdrawal is not None

    assert slashed_withdrawal.amount == withdrawal_amount

    assert non_slashed_withdrawal.amount == withdrawal_amount


@with_gloas_and_later
@spec_state_test
def test_builder_withdrawal_insufficient_balance(spec, state):
    """ Builder with balance < MIN_ACTIVATION_BALANCE should skip"""
    builder_index = 0
    withdrawal_amount = spec.Gwei(10_000_000_000)  # 10 ETH

    set_builder_withdrawal_credential_with_balance(
        spec, state, builder_index,
        effective_balance=spec.MIN_ACTIVATION_BALANCE,
        balance=spec.MIN_ACTIVATION_BALANCE - spec.Gwei(1),  # Just below minimum
    )

    current_epoch = spec.get_current_epoch(state)
    address = state.validators[builder_index].withdrawal_credentials[12:]
    state.builder_pending_withdrawals.append(
        spec.BuilderPendingWithdrawal(
            fee_recipient=address,
            amount=withdrawal_amount,
            builder_index=builder_index,
            withdrawable_epoch=current_epoch,
        )
    )

    withdrawals = get_expected_withdrawals(spec, state)

    builder_withdrawals = [w for w in withdrawals if w.validator_index == builder_index]
    assert len(builder_withdrawals) == 0


@with_gloas_and_later
@spec_state_test
def test_builder_withdrawals_respect_max_limit(spec, state):
    """ When more builder withdrawals than MAX exist, should not exceed MAX total"""
    num_builders = spec.MAX_WITHDRAWALS_PER_PAYLOAD * 2
    # Ensure we have enough validators
    assert len(state.validators) >= num_builders, f"Test requires at least {num_builders} validators"


    for i in range(num_builders):
        set_builder_withdrawal_credential_with_balance(
            spec, state, i,
            effective_balance=spec.MAX_EFFECTIVE_BALANCE_ELECTRA,
            balance=spec.MAX_EFFECTIVE_BALANCE_ELECTRA + spec.MIN_ACTIVATION_BALANCE,
        )

    prepare_withdrawals(
        spec, state,
        builder_indices=list(range(num_builders)),
        builder_withdrawal_amounts=[spec.MIN_ACTIVATION_BALANCE] * num_builders,
        builder_withdrawable_offsets=[0] * num_builders,
    )

    withdrawals = get_expected_withdrawals(spec, state)

    assert len(withdrawals) <= spec.MAX_WITHDRAWALS_PER_PAYLOAD

    builder_withdrawals = [w for w in withdrawals if w.validator_index < num_builders]
    assert len(builder_withdrawals) < num_builders


@with_gloas_and_later
@spec_state_test
def test_builder_uses_fee_recipient_address(spec, state):
    """ Builder withdrawal should use fee_recipient address"""
    builder_index = 0
    custom_address = b"\xAB" * 20

    set_builder_withdrawal_credential_with_balance(
        spec, state, builder_index,
        effective_balance=spec.MAX_EFFECTIVE_BALANCE_ELECTRA,
        balance=spec.MAX_EFFECTIVE_BALANCE_ELECTRA + spec.MIN_ACTIVATION_BALANCE,
        address=custom_address,
    )

    prepare_withdrawals(
        spec, state,
        builder_indices=[builder_index],
        builder_withdrawal_amounts=[spec.MIN_ACTIVATION_BALANCE],
        builder_withdrawable_offsets=[0],
    )

    withdrawals = get_expected_withdrawals(spec, state)

    builder_withdrawal = next((w for w in withdrawals if w.validator_index == builder_index), None)
    assert builder_withdrawal is not None

    assert builder_withdrawal.address == custom_address


# Corner Cases - Gloas Only


@with_gloas_and_later
@spec_state_test
def test_builder_and_pending_leave_room_for_sweep(spec, state):
    """ Builders + pending = MAX-1, exactly 1 slot remains for sweep"""
    assert spec.MAX_WITHDRAWALS_PER_PAYLOAD >= 3, \
        "Test requires MAX_WITHDRAWALS_PER_PAYLOAD to be at least 3"

    num_builders = 2 if spec.MAX_WITHDRAWALS_PER_PAYLOAD >= 4 else 1
    num_pending = min(spec.MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP, spec.MAX_WITHDRAWALS_PER_PAYLOAD - num_builders - 1)

    for i in range(num_builders):
        set_builder_withdrawal_credential_with_balance(
            spec, state, i,
            effective_balance=spec.MAX_EFFECTIVE_BALANCE_ELECTRA,
            balance=spec.MAX_EFFECTIVE_BALANCE_ELECTRA + spec.MIN_ACTIVATION_BALANCE,
        )

    if num_builders > 0:
        prepare_withdrawals(
            spec, state,
            builder_indices=list(range(num_builders)),
            builder_withdrawal_amounts=[spec.MIN_ACTIVATION_BALANCE] * num_builders,
            builder_withdrawable_offsets=[0] * num_builders,
        )

    if num_pending > 0:
        pending_indices = list(range(num_builders, num_builders + num_pending))
        prepare_withdrawals(
            spec, state,
            pending_partial_indices=pending_indices,
            pending_partial_amounts=[spec.Gwei(1_000_000_000)] * num_pending,
            pending_partial_withdrawable_offsets=[0] * num_pending,
        )

    regular_index = num_builders + num_pending + 1
    prepare_withdrawals(
        spec, state,
        full_withdrawal_indices=[regular_index],
        full_withdrawable_offsets=[0],
    )

    withdrawals = get_expected_withdrawals(spec, state)

    assert len(withdrawals) == num_builders + num_pending + 1, \
        "Should process all builders, all pending, and exactly 1 sweep withdrawal"

    regular_withdrawals = [w for w in withdrawals if w.validator_index == regular_index]
    assert len(regular_withdrawals) == 1, "Exactly 1 slot should remain for sweep withdrawal"


@with_gloas_and_later
@spec_state_test
def test_all_builder_withdrawals_invalid(spec, state):
    """ All builders have insufficient balance, should process pending/regular instead"""
    current_epoch = spec.get_current_epoch(state)

    for i in range(2):
        set_builder_withdrawal_credential_with_balance(
            spec, state, i,
            effective_balance=spec.MIN_ACTIVATION_BALANCE,
            balance=spec.MIN_ACTIVATION_BALANCE - spec.Gwei(1),
        )
        address = state.validators[i].withdrawal_credentials[12:]
        state.builder_pending_withdrawals.append(
            spec.BuilderPendingWithdrawal(
                fee_recipient=address,
                amount=spec.MIN_ACTIVATION_BALANCE,
                builder_index=i,
                withdrawable_epoch=current_epoch,
            )
        )

    prepare_withdrawals(
        spec, state,
        full_withdrawal_indices=[5],
        full_withdrawable_offsets=[0],
    )

    withdrawals = get_expected_withdrawals(spec, state)

    assert any(w.validator_index == 5 for w in withdrawals), "Regular sweep withdrawal should be processed"

    for i in range(2):
        assert not any(w.validator_index == i for w in withdrawals), \
            f"Builder {i} with insufficient balance should not withdraw"


@with_gloas_and_later
@spec_state_test
def test_builder_slashed_zero_balance(spec, state):
    """ Slashed builder with 0 balance should skip"""
    builder_index = 0
    current_epoch = spec.get_current_epoch(state)

    set_builder_withdrawal_credential_with_balance(
        spec, state, builder_index,
        effective_balance=spec.Gwei(0),
        balance=spec.Gwei(0),
    )
    state.validators[builder_index].slashed = True

    address = state.validators[builder_index].withdrawal_credentials[12:]
    state.builder_pending_withdrawals.append(
        spec.BuilderPendingWithdrawal(
            fee_recipient=address,
            amount=spec.MIN_ACTIVATION_BALANCE,
            builder_index=builder_index,
            withdrawable_epoch=current_epoch,
        )
    )

    withdrawals = get_expected_withdrawals(spec, state)

    builder_withdrawals = [w for w in withdrawals if w.validator_index == builder_index]
    assert len(builder_withdrawals) == 0


@with_gloas_and_later
@spec_state_test
def test_mixed_all_three_withdrawal_types(spec, state):
    """ Builder + pending + regular, verify priority order"""
    builder_index = 0
    pending_index = 1
    regular_index = 2

    set_builder_withdrawal_credential_with_balance(
        spec, state, builder_index,
        effective_balance=spec.MAX_EFFECTIVE_BALANCE_ELECTRA,
        balance=spec.MAX_EFFECTIVE_BALANCE_ELECTRA + spec.MIN_ACTIVATION_BALANCE,
    )

    prepare_withdrawals(
        spec, state,
        builder_indices=[builder_index],
        builder_withdrawal_amounts=[spec.MIN_ACTIVATION_BALANCE],
        builder_withdrawable_offsets=[0],
    )

    prepare_withdrawals(
        spec, state,
        pending_partial_indices=[pending_index],
        pending_partial_amounts=[spec.Gwei(1_000_000_000)],
        pending_partial_withdrawable_offsets=[0],
    )

    prepare_withdrawals(
        spec, state,
        full_withdrawal_indices=[regular_index],
        full_withdrawable_offsets=[0],
    )

    withdrawals = get_expected_withdrawals(spec, state)

    assert len(withdrawals) == 3

    builder_pos = next((i for i, w in enumerate(withdrawals) if w.validator_index == builder_index), None)
    pending_pos = next((i for i, w in enumerate(withdrawals) if w.validator_index == pending_index), None)
    regular_pos = next((i for i, w in enumerate(withdrawals) if w.validator_index == regular_index), None)

    assert builder_pos is not None
    assert pending_pos is not None
    assert regular_pos is not None

    assert builder_pos < pending_pos
    assert pending_pos < regular_pos


@with_gloas_and_later
@spec_state_test
def test_builder_max_minus_one_plus_one_regular(spec, state):
    """ Exactly MAX-1 builder withdrawals should add exactly 1 regular withdrawal"""
    num_builders = spec.MAX_WITHDRAWALS_PER_PAYLOAD - 1

    for i in range(num_builders):
        set_builder_withdrawal_credential_with_balance(
            spec, state, i,
            effective_balance=spec.MAX_EFFECTIVE_BALANCE_ELECTRA,
            balance=spec.MAX_EFFECTIVE_BALANCE_ELECTRA + spec.MIN_ACTIVATION_BALANCE,
        )

    prepare_withdrawals(
        spec, state,
        builder_indices=list(range(num_builders)),
        builder_withdrawal_amounts=[spec.MIN_ACTIVATION_BALANCE] * num_builders,
        builder_withdrawable_offsets=[0] * num_builders,
    )

    regular_indices = [num_builders + 1, num_builders + 2, num_builders + 3]
    assert len(state.validators) >= max(regular_indices) + 1, \
        f"Test requires at least {max(regular_indices) + 1} validators"

    state.next_withdrawal_validator_index = regular_indices[0]

    prepare_withdrawals(
        spec, state,
        full_withdrawal_indices=regular_indices,
        full_withdrawable_offsets=[0] * len(regular_indices),
    )

    withdrawals = get_expected_withdrawals(spec, state)

    assert len(withdrawals) == spec.MAX_WITHDRAWALS_PER_PAYLOAD

    builder_withdrawals = [w for w in withdrawals if w.validator_index < num_builders]
    assert len(builder_withdrawals) == num_builders

    regular_withdrawals = [w for w in withdrawals if w.validator_index in regular_indices]
    assert len(regular_withdrawals) == 1, "Should process exactly 1 regular withdrawal when builders fill MAX-1 slots"
    assert regular_withdrawals[0].validator_index == regular_indices[0], "Should process the first regular withdrawal in sweep order"


# Builder Processing Edge Cases


@with_gloas_and_later
@spec_state_test
def test_builder_wrong_credentials_still_processes(spec, state):
    """ Builder pending withdrawal processes even with non-BUILDER_WITHDRAWAL_PREFIX (no validation in get_expected_withdrawals)"""
    builder_index = 0
    regular_index = 1
    current_epoch = spec.get_current_epoch(state)

    set_compounding_withdrawal_credential_with_balance(
        spec, state, builder_index,
        effective_balance=spec.MAX_EFFECTIVE_BALANCE_ELECTRA,
        balance=spec.MAX_EFFECTIVE_BALANCE_ELECTRA + spec.MIN_ACTIVATION_BALANCE,
    )

    assert state.validators[builder_index].withdrawal_credentials[0:1] != spec.BUILDER_WITHDRAWAL_PREFIX, \
        "Validator should have non-builder credentials (0x02 compounding) for this test"

    address = state.validators[builder_index].withdrawal_credentials[12:]
    state.builder_pending_withdrawals.append(
        spec.BuilderPendingWithdrawal(
            fee_recipient=address,
            amount=spec.MIN_ACTIVATION_BALANCE,
            builder_index=builder_index,
            withdrawable_epoch=current_epoch,
        )
    )

    prepare_withdrawals(
        spec, state,
        full_withdrawal_indices=[regular_index],
        full_withdrawable_offsets=[0],
    )

    withdrawals = get_expected_withdrawals(spec, state)

    builder_withdrawals = [w for w in withdrawals if w.validator_index == builder_index]
    regular_withdrawals = [w for w in withdrawals if w.validator_index == regular_index]

    assert len(builder_withdrawals) == 1, \
        f"Builder withdrawal IS processed even with wrong credentials (0x{state.validators[builder_index].withdrawal_credentials[0:1].hex()}) - no validation in get_expected_withdrawals"
    assert len(regular_withdrawals) == 1, \
        "Regular withdrawal should also be processed"


@with_gloas_and_later
@spec_state_test
def test_builder_zero_withdrawal_amount(spec, state):
    """ Builder withdrawal with amount = 0 should skip"""
    builder_index = 0
    current_epoch = spec.get_current_epoch(state)

    set_builder_withdrawal_credential_with_balance(
        spec, state, builder_index,
        effective_balance=spec.MAX_EFFECTIVE_BALANCE_ELECTRA,
        balance=spec.MAX_EFFECTIVE_BALANCE_ELECTRA,  # No excess
    )

    address = state.validators[builder_index].withdrawal_credentials[12:]
    state.builder_pending_withdrawals.append(
        spec.BuilderPendingWithdrawal(
            fee_recipient=address,
            amount=spec.Gwei(0),
            builder_index=builder_index,
            withdrawable_epoch=current_epoch,
        )
    )

    withdrawals = get_expected_withdrawals(spec, state)

    builder_withdrawals = [w for w in withdrawals if w.validator_index == builder_index]
    assert len(builder_withdrawals) == 0


@with_gloas_and_later
@spec_state_test
def test_builder_max_capacity_no_room_others(spec, state):
    """ Exactly MAX builder withdrawals should fill all slots, no room for pending/regular"""
    num_builders = spec.MAX_WITHDRAWALS_PER_PAYLOAD

    assert len(state.validators) >= num_builders + 2, f"Test requires at least {num_builders + 2} validators"

    for i in range(num_builders):
        set_builder_withdrawal_credential_with_balance(
            spec, state, i,
            effective_balance=spec.MAX_EFFECTIVE_BALANCE_ELECTRA,
            balance=spec.MAX_EFFECTIVE_BALANCE_ELECTRA + spec.MIN_ACTIVATION_BALANCE,
        )

    prepare_withdrawals(
        spec, state,
        builder_indices=list(range(num_builders)),
        builder_withdrawal_amounts=[spec.MIN_ACTIVATION_BALANCE] * num_builders,
        builder_withdrawable_offsets=[0] * num_builders,
    )

    prepare_withdrawals(
        spec, state,
        pending_partial_indices=[num_builders],
        pending_partial_amounts=[spec.Gwei(1_000_000_000)],
        pending_partial_withdrawable_offsets=[0],
    )

    prepare_withdrawals(
        spec, state,
        full_withdrawal_indices=[num_builders + 1],
        full_withdrawable_offsets=[0],
    )

    withdrawals = get_expected_withdrawals(spec, state)

    assert len(withdrawals) == spec.MAX_WITHDRAWALS_PER_PAYLOAD, \
        "Should return exactly MAX withdrawals when builders fill all slots"

    builder_withdrawals = [w for w in withdrawals if w.validator_index < num_builders]
    assert len(builder_withdrawals) == num_builders, \
        "All withdrawals should be builders only"

    pending_withdrawals = [w for w in withdrawals if w.validator_index == num_builders]
    regular_withdrawals = [w for w in withdrawals if w.validator_index == num_builders + 1]

    assert len(pending_withdrawals) == 0, "No room for pending partials when builders fill MAX"
    assert len(regular_withdrawals) == 0, "No room for regular withdrawals when builders fill MAX"
