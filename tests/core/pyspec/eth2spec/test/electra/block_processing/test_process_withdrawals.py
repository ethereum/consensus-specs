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
    prepare_expected_withdrawals_compounding,
    run_withdrawals_processing,
    set_compounding_withdrawal_credential_with_balance,
    prepare_pending_withdrawal,
)


@with_electra_and_later
@spec_state_test
def test_success_mixed_fully_and_partial_withdrawable_compounding(spec, state):
    num_full_withdrawals = spec.MAX_WITHDRAWALS_PER_PAYLOAD // 2
    num_partial_withdrawals = spec.MAX_WITHDRAWALS_PER_PAYLOAD - num_full_withdrawals
    fully_withdrawable_indices, partial_withdrawals_indices = prepare_expected_withdrawals_compounding(
        spec, state,
        rng=random.Random(42),
        num_full_withdrawals=num_full_withdrawals,
        num_partial_withdrawals_sweep=num_partial_withdrawals,
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
    set_compounding_withdrawal_credential_with_balance(spec, state, validator_index, spec.MAX_EFFECTIVE_BALANCE_ELECTRA)

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
    index_0 = 3
    index_1 = 5

    withdrawal_0 = prepare_pending_withdrawal(spec, state, index_0)
    withdrawal_1 = prepare_pending_withdrawal(spec, state, index_1)

    # If validator doesn't have an excess balance pending withdrawal is skipped
    state.balances[index_0] = spec.MIN_ACTIVATION_BALANCE

    execution_payload = build_empty_execution_payload(spec, state)
    assert state.pending_partial_withdrawals == [withdrawal_0, withdrawal_1]
    yield from run_withdrawals_processing(spec, state, execution_payload, num_expected_withdrawals=1)

    assert state.pending_partial_withdrawals == []
