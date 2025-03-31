import random

from eth2spec.test.context import (
    spec_state_test,
    with_electra_and_later,
)
from eth2spec.test.helpers.execution_payload import (
    build_empty_execution_payload,
)
from eth2spec.test.helpers.state import (
    next_slot,
)
from eth2spec.test.helpers.withdrawals import (
    prepare_expected_withdrawals,
    run_withdrawals_processing,
    set_compounding_withdrawal_credential_with_balance,
    prepare_pending_withdrawal,
)


@with_electra_and_later
@spec_state_test
def test_success_mixed_fully_and_partial_withdrawable_compounding(spec, state):
    num_full_withdrawals = spec.MAX_WITHDRAWALS_PER_PAYLOAD // 2
    num_partial_withdrawals = spec.MAX_WITHDRAWALS_PER_PAYLOAD - num_full_withdrawals
    fully_withdrawable_indices, partial_withdrawals_indices = prepare_expected_withdrawals(
        spec, state,
        rng=random.Random(42),
        num_full_withdrawals_comp=num_full_withdrawals,
        num_partial_withdrawals_comp=num_partial_withdrawals,
    )

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)

    yield from run_withdrawals_processing(
        spec, state, execution_payload,
        fully_withdrawable_indices=fully_withdrawable_indices,
        partial_withdrawals_indices=partial_withdrawals_indices)


@with_electra_and_later
@spec_state_test
def test_success_no_max_effective_balance_compounding(spec, state):
    validator_index = len(state.validators) // 2
    # To be partially withdrawable, the validator's effective balance must be maxed out
    effective_balance = spec.MAX_EFFECTIVE_BALANCE_ELECTRA - spec.EFFECTIVE_BALANCE_INCREMENT
    set_compounding_withdrawal_credential_with_balance(spec, state, validator_index, effective_balance)

    validator = state.validators[validator_index]
    assert not spec.is_partially_withdrawable_validator(validator, state.balances[validator_index])

    execution_payload = build_empty_execution_payload(spec, state)

    yield from run_withdrawals_processing(spec, state, execution_payload, num_expected_withdrawals=0)


@with_electra_and_later
@spec_state_test
def test_success_no_excess_balance_compounding(spec, state):
    validator_index = len(state.validators) // 2
    # To be partially withdrawable, the validator needs an excess balance
    effective_balance = spec.MAX_EFFECTIVE_BALANCE_ELECTRA
    set_compounding_withdrawal_credential_with_balance(spec, state, validator_index, effective_balance)

    validator = state.validators[validator_index]
    assert not spec.is_partially_withdrawable_validator(validator, state.balances[validator_index])

    execution_payload = build_empty_execution_payload(spec, state)

    yield from run_withdrawals_processing(spec, state, execution_payload, num_expected_withdrawals=0)


@with_electra_and_later
@spec_state_test
def test_success_excess_balance_but_no_max_effective_balance_compounding(spec, state):
    validator_index = len(state.validators) // 2
    # To be partially withdrawable, the validator needs both a maxed out effective balance and an excess balance
    effective_balance = spec.MAX_EFFECTIVE_BALANCE_ELECTRA - spec.EFFECTIVE_BALANCE_INCREMENT
    balance = spec.MAX_EFFECTIVE_BALANCE_ELECTRA + spec.EFFECTIVE_BALANCE_INCREMENT
    set_compounding_withdrawal_credential_with_balance(spec, state, validator_index, effective_balance, balance)

    validator = state.validators[validator_index]
    assert not spec.is_partially_withdrawable_validator(validator, state.balances[validator_index])

    execution_payload = build_empty_execution_payload(spec, state)

    yield from run_withdrawals_processing(spec, state, execution_payload, num_expected_withdrawals=0)


@with_electra_and_later
@spec_state_test
def test_pending_withdrawals_one_skipped_one_effective(spec, state):
    validator_index_0 = 3
    validator_index_1 = 5

    pending_withdrawal_0 = prepare_pending_withdrawal(spec, state, validator_index_0)
    pending_withdrawal_1 = prepare_pending_withdrawal(spec, state, validator_index_1)

    # If validator doesn't have an excess balance pending withdrawal is skipped
    state.balances[validator_index_0] = spec.MIN_ACTIVATION_BALANCE

    execution_payload = build_empty_execution_payload(spec, state)
    assert state.pending_partial_withdrawals == [pending_withdrawal_0, pending_withdrawal_1]
    yield from run_withdrawals_processing(
        spec, state,
        execution_payload,
        num_expected_withdrawals=1,
        pending_withdrawal_requests=[pending_withdrawal_1]
    )

    assert state.pending_partial_withdrawals == []


@with_electra_and_later
@spec_state_test
def test_pending_withdrawals_next_epoch(spec, state):
    validator_index = len(state.validators) // 2
    next_epoch = spec.get_current_epoch(state) + 1

    pending_withdrawal = prepare_pending_withdrawal(spec, state, validator_index, withdrawable_epoch=next_epoch)

    execution_payload = build_empty_execution_payload(spec, state)
    yield from run_withdrawals_processing(spec, state, execution_payload, num_expected_withdrawals=0)

    assert state.pending_partial_withdrawals == [pending_withdrawal]


@with_electra_and_later
@spec_state_test
def test_pending_withdrawals_at_max(spec, state):
    pending_withdrawal_requests = []
    # Create spec.MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP + 1 partial withdrawals
    for i in range(0, spec.MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP + 1):
        pending_withdrawal = prepare_pending_withdrawal(spec, state, i)
        pending_withdrawal_requests.append(pending_withdrawal)

    assert len(state.pending_partial_withdrawals) == spec.MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP + 1

    execution_payload = build_empty_execution_payload(spec, state)
    yield from run_withdrawals_processing(
        spec, state,
        execution_payload,
        num_expected_withdrawals=spec.MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP,
        pending_withdrawal_requests=pending_withdrawal_requests[:spec.MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP]
    )

    withdrawals_exceeding_max = pending_withdrawal_requests[spec.MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP:]
    assert state.pending_partial_withdrawals == withdrawals_exceeding_max


@with_electra_and_later
@spec_state_test
def test_pending_withdrawals_exiting_validator(spec, state):
    validator_index = len(state.validators) // 2

    pending_withdrawal = prepare_pending_withdrawal(spec, state, validator_index)
    spec.initiate_validator_exit(state, pending_withdrawal.validator_index)

    execution_payload = build_empty_execution_payload(spec, state)
    yield from run_withdrawals_processing(spec, state, execution_payload, num_expected_withdrawals=0)

    assert state.pending_partial_withdrawals == []


@with_electra_and_later
@spec_state_test
def test_full_pending_withdrawals_but_first_skipped_exiting_validator(spec, state):
    # Fill the pending withdrawals, plus one which will be skipped
    for index in range(spec.MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP + 1):
        # Note, this adds the pending withdrawal to the state
        prepare_pending_withdrawal(spec, state, index)

    # Ensure that there's one more than the limit, the first will be skipped
    assert len(state.pending_partial_withdrawals) == spec.MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP + 1

    # For the first pending withdrawal, set the validator as exiting
    spec.initiate_validator_exit(state, 0)

    yield from run_withdrawals_processing(
        spec,
        state,
        build_empty_execution_payload(spec, state),
        # We expect the first pending withdrawal to be skipped
        num_expected_withdrawals=spec.MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP
    )

    # Ensure all pending withdrawals were processed and the first one was skipped
    assert state.pending_partial_withdrawals == []


@with_electra_and_later
@spec_state_test
def test_pending_withdrawals_low_effective_balance(spec, state):
    validator_index = len(state.validators) // 2

    pending_withdrawal = prepare_pending_withdrawal(spec, state, validator_index)
    state.validators[pending_withdrawal.validator_index].effective_balance = (
        spec.MIN_ACTIVATION_BALANCE - spec.EFFECTIVE_BALANCE_INCREMENT
    )

    execution_payload = build_empty_execution_payload(spec, state)
    yield from run_withdrawals_processing(spec, state, execution_payload, num_expected_withdrawals=0)

    assert state.pending_partial_withdrawals == []


@with_electra_and_later
@spec_state_test
def test_full_pending_withdrawals_but_first_skipped_low_effective_balance(spec, state):
    # Fill the pending withdrawals, plus one which will be skipped
    for index in range(spec.MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP + 1):
        # Note, this adds the pending withdrawal to the state
        prepare_pending_withdrawal(spec, state, index)

    # Ensure that there's one more than the limit, the first will be skipped
    assert len(state.pending_partial_withdrawals) == spec.MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP + 1

    # For the first pending withdrawal, set the validator to insufficient effective balance
    state.validators[0].effective_balance = spec.MIN_ACTIVATION_BALANCE - spec.EFFECTIVE_BALANCE_INCREMENT

    yield from run_withdrawals_processing(
        spec,
        state,
        build_empty_execution_payload(spec, state),
        # We expect the first pending withdrawal to be skipped
        num_expected_withdrawals=spec.MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP
    )

    # Ensure all pending withdrawals were processed and the first one was skipped
    assert state.pending_partial_withdrawals == []


@with_electra_and_later
@spec_state_test
def test_pending_withdrawals_no_excess_balance(spec, state):
    validator_index = len(state.validators) // 2

    pending_withdrawal = prepare_pending_withdrawal(spec, state, validator_index)
    state.balances[pending_withdrawal.validator_index] = spec.MIN_ACTIVATION_BALANCE

    execution_payload = build_empty_execution_payload(spec, state)
    yield from run_withdrawals_processing(spec, state, execution_payload, num_expected_withdrawals=0)

    assert state.pending_partial_withdrawals == []


@with_electra_and_later
@spec_state_test
def test_full_pending_withdrawals_but_first_skipped_no_excess_balance(spec, state):
    # Fill the pending withdrawals, plus one which will be skipped
    for index in range(spec.MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP + 1):
        # Note, this adds the pending withdrawal to the state
        prepare_pending_withdrawal(spec, state, index)

    # Ensure that there's one more than the limit, the first will be skipped
    assert len(state.pending_partial_withdrawals) == spec.MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP + 1

    # For the first pending withdrawal, set the validator to have no excess balance
    state.balances[0] = spec.MIN_ACTIVATION_BALANCE

    yield from run_withdrawals_processing(
        spec,
        state,
        build_empty_execution_payload(spec, state),
        # We expect the first pending withdrawal to be skipped
        num_expected_withdrawals=spec.MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP
    )

    # Ensure all pending withdrawals were processed and the first one was skipped
    assert state.pending_partial_withdrawals == []


@with_electra_and_later
@spec_state_test
def test_pending_withdrawals_with_ineffective_sweep_on_top(spec, state):
    # Ensure validator will be processed by the sweep
    validator_index = min(len(state.validators), spec.MAX_VALIDATORS_PER_WITHDRAWALS_SWEEP) // 2

    pending_withdrawal = prepare_pending_withdrawal(
        spec, state,
        validator_index,
        effective_balance=spec.MAX_EFFECTIVE_BALANCE_ELECTRA,
    )

    # Check that validator is partially withdrawable before pending withdrawal is processed
    assert spec.is_partially_withdrawable_validator(
        state.validators[validator_index],
        state.balances[validator_index]
    )
    # And is not partially withdrawable thereafter
    assert not spec.is_partially_withdrawable_validator(
        state.validators[validator_index],
        state.balances[validator_index] - pending_withdrawal.amount
    )

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)
    yield from run_withdrawals_processing(
        spec, state,
        execution_payload,
        num_expected_withdrawals=1,
        fully_withdrawable_indices=[],
        partial_withdrawals_indices=[],
        pending_withdrawal_requests=[pending_withdrawal]
    )

    assert state.pending_partial_withdrawals == []


@with_electra_and_later
@spec_state_test
def test_pending_withdrawals_with_ineffective_sweep_on_top_2(spec, state):
    # Ensure validator will be processed by the sweep
    validator_index = min(len(state.validators), spec.MAX_VALIDATORS_PER_WITHDRAWALS_SWEEP) // 2

    pending_withdrawal_0 = prepare_pending_withdrawal(
        spec, state,
        validator_index,
        effective_balance=spec.MAX_EFFECTIVE_BALANCE_ELECTRA,
        amount=spec.EFFECTIVE_BALANCE_INCREMENT // 2
    )

    pending_withdrawal_1 = prepare_pending_withdrawal(
        spec, state,
        validator_index,
        effective_balance=spec.MAX_EFFECTIVE_BALANCE_ELECTRA,
        amount=spec.EFFECTIVE_BALANCE_INCREMENT
    )

    # Set excess balance in a way that validator
    # becomes not partially withdrawable only after the second pending withdrawal is processed
    state.balances[validator_index] = spec.MAX_EFFECTIVE_BALANCE_ELECTRA + spec.EFFECTIVE_BALANCE_INCREMENT
    assert spec.is_partially_withdrawable_validator(
        state.validators[validator_index],
        state.balances[validator_index] - pending_withdrawal_0.amount
    )
    assert not spec.is_partially_withdrawable_validator(
        state.validators[validator_index],
        state.balances[validator_index] - pending_withdrawal_0.amount - pending_withdrawal_1.amount
    )

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)
    yield from run_withdrawals_processing(
        spec, state,
        execution_payload,
        num_expected_withdrawals=2,
        fully_withdrawable_indices=[],
        partial_withdrawals_indices=[],
        pending_withdrawal_requests=[pending_withdrawal_0, pending_withdrawal_1]
    )

    assert state.pending_partial_withdrawals == []


@with_electra_and_later
@spec_state_test
def test_pending_withdrawals_with_effective_sweep_on_top(spec, state):
    # Ensure validator will be processed by the sweep
    validator_index = min(len(state.validators), spec.MAX_VALIDATORS_PER_WITHDRAWALS_SWEEP) // 2

    pending_withdrawal_0 = prepare_pending_withdrawal(
        spec, state,
        validator_index,
        effective_balance=spec.MAX_EFFECTIVE_BALANCE_ELECTRA,
        amount=spec.EFFECTIVE_BALANCE_INCREMENT // 2
    )

    pending_withdrawal_1 = prepare_pending_withdrawal(
        spec, state,
        validator_index,
        effective_balance=spec.MAX_EFFECTIVE_BALANCE_ELECTRA,
        amount=spec.EFFECTIVE_BALANCE_INCREMENT
    )

    # Set excess balance to requested amount times three,
    # so the validator is partially withdrawable after pending withdrawal is processed
    state.balances[validator_index] = spec.MAX_EFFECTIVE_BALANCE_ELECTRA + spec.EFFECTIVE_BALANCE_INCREMENT * 2
    assert spec.is_partially_withdrawable_validator(
        state.validators[validator_index],
        state.balances[validator_index] - pending_withdrawal_0.amount - pending_withdrawal_1.amount
    )

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)
    yield from run_withdrawals_processing(
        spec, state,
        execution_payload,
        num_expected_withdrawals=3,
        fully_withdrawable_indices=[],
        partial_withdrawals_indices=[validator_index],
        pending_withdrawal_requests=[pending_withdrawal_0, pending_withdrawal_1]
    )

    assert state.pending_partial_withdrawals == []


@with_electra_and_later
@spec_state_test
def test_pending_withdrawals_with_sweep_different_validator(spec, state):
    # Ensure validator will be processed by the sweep
    validator_index_0 = min(len(state.validators), spec.MAX_VALIDATORS_PER_WITHDRAWALS_SWEEP) // 2 - 1
    validator_index_1 = min(len(state.validators), spec.MAX_VALIDATORS_PER_WITHDRAWALS_SWEEP) // 2

    # Initiate pending withdrawal for the first validator
    pending_withdrawal_0 = prepare_pending_withdrawal(
        spec, state,
        validator_index_0,
        effective_balance=spec.MAX_EFFECTIVE_BALANCE_ELECTRA,
        amount=spec.EFFECTIVE_BALANCE_INCREMENT
    )

    # Make the second validator partially withdrawable by the sweep
    set_compounding_withdrawal_credential_with_balance(
        spec, state, validator_index_1,
        effective_balance=spec.MAX_EFFECTIVE_BALANCE_ELECTRA,
        balance=(spec.MAX_EFFECTIVE_BALANCE_ELECTRA + spec.EFFECTIVE_BALANCE_INCREMENT)
    )

    assert spec.is_partially_withdrawable_validator(
        state.validators[validator_index_1],
        state.balances[validator_index_1]
    )

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)
    yield from run_withdrawals_processing(
        spec, state,
        execution_payload,
        num_expected_withdrawals=2,
        fully_withdrawable_indices=[],
        partial_withdrawals_indices=[validator_index_1],
        pending_withdrawal_requests=[pending_withdrawal_0]
    )

    assert state.pending_partial_withdrawals == []


@with_electra_and_later
@spec_state_test
def test_pending_withdrawals_mixed_with_sweep_and_fully_withdrawable(spec, state):
    num_full_withdrawals = spec.MAX_WITHDRAWALS_PER_PAYLOAD // 4
    num_partial_withdrawals = spec.MAX_WITHDRAWALS_PER_PAYLOAD // 4
    num_full_withdrawals_comp = spec.MAX_WITHDRAWALS_PER_PAYLOAD // 4
    num_partial_withdrawals_comp = spec.MAX_WITHDRAWALS_PER_PAYLOAD // 4
    num_pending_withdrawal_requests = spec.MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP // 2

    fully_withdrawable_indices, partial_withdrawals_indices = prepare_expected_withdrawals(
        spec, state,
        rng=random.Random(42),
        num_full_withdrawals=num_full_withdrawals,
        num_partial_withdrawals=num_partial_withdrawals,
        num_full_withdrawals_comp=num_full_withdrawals_comp,
        num_partial_withdrawals_comp=num_partial_withdrawals_comp,
    )

    pending_withdrawal_requests = []
    for index in range(0, len(state.validators)):
        if len(pending_withdrawal_requests) >= num_pending_withdrawal_requests:
            break
        if index in (fully_withdrawable_indices + partial_withdrawals_indices):
            continue

        pending_withdrawal = prepare_pending_withdrawal(spec, state, index)
        pending_withdrawal_requests.append(pending_withdrawal)

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)
    yield from run_withdrawals_processing(
        spec, state,
        execution_payload,
        num_expected_withdrawals=spec.MAX_WITHDRAWALS_PER_PAYLOAD,
        fully_withdrawable_indices=fully_withdrawable_indices,
        partial_withdrawals_indices=partial_withdrawals_indices,
        pending_withdrawal_requests=pending_withdrawal_requests
    )

    assert state.pending_partial_withdrawals == []


@with_electra_and_later
@spec_state_test
def test_pending_withdrawals_at_max_mixed_with_sweep_and_fully_withdrawable(spec, state):
    num_full_withdrawals = spec.MAX_WITHDRAWALS_PER_PAYLOAD // 4
    num_partial_withdrawals = spec.MAX_WITHDRAWALS_PER_PAYLOAD // 4
    num_full_withdrawals_comp = spec.MAX_WITHDRAWALS_PER_PAYLOAD // 4
    num_partial_withdrawals_comp = spec.MAX_WITHDRAWALS_PER_PAYLOAD // 4
    num_pending_withdrawal_requests = spec.MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP + 1

    fully_withdrawable_indices, partial_withdrawals_indices = prepare_expected_withdrawals(
        spec, state,
        rng=random.Random(42),
        num_full_withdrawals=num_full_withdrawals,
        num_partial_withdrawals=num_partial_withdrawals,
        num_full_withdrawals_comp=num_full_withdrawals_comp,
        num_partial_withdrawals_comp=num_partial_withdrawals_comp,
    )

    pending_withdrawal_requests = []
    for index in range(0, len(state.validators)):
        if len(pending_withdrawal_requests) >= num_pending_withdrawal_requests:
            break
        if index in (fully_withdrawable_indices + partial_withdrawals_indices):
            continue

        pending_withdrawal = prepare_pending_withdrawal(spec, state, index)
        pending_withdrawal_requests.append(pending_withdrawal)

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)
    yield from run_withdrawals_processing(
        spec, state,
        execution_payload,
        num_expected_withdrawals=spec.MAX_WITHDRAWALS_PER_PAYLOAD,
        fully_withdrawable_indices=fully_withdrawable_indices,
        partial_withdrawals_indices=partial_withdrawals_indices,
        pending_withdrawal_requests=pending_withdrawal_requests[:spec.MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP]
    )

    withdrawals_exceeding_max = pending_withdrawal_requests[spec.MAX_PENDING_PARTIALS_PER_WITHDRAWALS_SWEEP:]
    assert state.pending_partial_withdrawals == withdrawals_exceeding_max


@with_electra_and_later
@spec_state_test
def test_partially_withdrawable_validator_compounding_max_plus_one(spec, state):
    """Test compounding validator with balance just above MAX_EFFECTIVE_BALANCE_ELECTRA"""
    validator_index = 0
    set_compounding_withdrawal_credential_with_balance(
        spec, state,
        validator_index,
        balance=spec.MAX_EFFECTIVE_BALANCE_ELECTRA + 1
    )
    assert spec.is_partially_withdrawable_validator(
        state.validators[validator_index],
        state.balances[validator_index]
    )

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)
    yield from run_withdrawals_processing(
        spec, state,
        execution_payload,
        fully_withdrawable_indices=[],
        partial_withdrawals_indices=[validator_index]
    )
    assert state.pending_partial_withdrawals == []


@with_electra_and_later
@spec_state_test
def test_partially_withdrawable_validator_compounding_exact_max(spec, state):
    """Test compounding validator with balance exactly equal to MAX_EFFECTIVE_BALANCE_ELECTRA"""
    validator_index = 0
    set_compounding_withdrawal_credential_with_balance(
        spec, state,
        validator_index
    )
    assert not spec.is_partially_withdrawable_validator(
        state.validators[validator_index],
        state.balances[validator_index]
    )

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)
    yield from run_withdrawals_processing(
        spec, state,
        execution_payload,
        fully_withdrawable_indices=[],
        partial_withdrawals_indices=[]
    )
    assert state.pending_partial_withdrawals == []


@with_electra_and_later
@spec_state_test
def test_partially_withdrawable_validator_compounding_max_minus_one(spec, state):
    """Test compounding validator whose balance is just below MAX_EFFECTIVE_BALANCE_ELECTRA"""
    validator_index = 0
    set_compounding_withdrawal_credential_with_balance(
        spec, state,
        validator_index,
        effective_balance=spec.MAX_EFFECTIVE_BALANCE_ELECTRA - spec.EFFECTIVE_BALANCE_INCREMENT,
        balance=spec.MAX_EFFECTIVE_BALANCE_ELECTRA - 1
    )
    assert not spec.is_partially_withdrawable_validator(
        state.validators[validator_index],
        state.balances[validator_index]
    )

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)
    yield from run_withdrawals_processing(
        spec, state,
        execution_payload,
        fully_withdrawable_indices=[],
        partial_withdrawals_indices=[]
    )
    assert state.pending_partial_withdrawals == []


@with_electra_and_later
@spec_state_test
def test_partially_withdrawable_validator_compounding_min_plus_one(spec, state):
    """Test compounding validator just above MIN_ACTIVATION_BALANCE"""
    validator_index = 0
    set_compounding_withdrawal_credential_with_balance(
        spec, state,
        validator_index,
        effective_balance=spec.MIN_ACTIVATION_BALANCE,
        balance=spec.MIN_ACTIVATION_BALANCE + 1
    )
    assert not spec.is_partially_withdrawable_validator(
        state.validators[validator_index],
        state.balances[validator_index]
    )

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)
    yield from run_withdrawals_processing(
        spec, state,
        execution_payload,
        fully_withdrawable_indices=[],
        partial_withdrawals_indices=[]
    )
    assert state.pending_partial_withdrawals == []


@with_electra_and_later
@spec_state_test
def test_partially_withdrawable_validator_compounding_exact_min(spec, state):
    """Test compounding validator with balance exactly equal to MIN_ACTIVATION_BALANCE"""
    validator_index = 0
    set_compounding_withdrawal_credential_with_balance(
        spec, state,
        validator_index,
        effective_balance=spec.MIN_ACTIVATION_BALANCE,
        balance=spec.MIN_ACTIVATION_BALANCE
    )
    assert not spec.is_partially_withdrawable_validator(
        state.validators[validator_index],
        state.balances[validator_index]
    )

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)
    yield from run_withdrawals_processing(
        spec, state,
        execution_payload,
        fully_withdrawable_indices=[],
        partial_withdrawals_indices=[]
    )
    assert state.pending_partial_withdrawals == []


@with_electra_and_later
@spec_state_test
def test_partially_withdrawable_validator_compounding_min_minus_one(spec, state):
    """Test compounding validator below MIN_ACTIVATION_BALANCE"""
    validator_index = 0
    set_compounding_withdrawal_credential_with_balance(
        spec, state,
        validator_index,
        effective_balance=spec.MIN_ACTIVATION_BALANCE - spec.EFFECTIVE_BALANCE_INCREMENT,
        balance=spec.MIN_ACTIVATION_BALANCE - 1
    )
    assert not spec.is_partially_withdrawable_validator(
        state.validators[validator_index],
        state.balances[validator_index]
    )

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)
    yield from run_withdrawals_processing(
        spec, state,
        execution_payload,
        fully_withdrawable_indices=[],
        partial_withdrawals_indices=[]
    )
    assert state.pending_partial_withdrawals == []
