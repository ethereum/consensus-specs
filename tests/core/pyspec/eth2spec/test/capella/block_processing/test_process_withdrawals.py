import random

from eth2spec.test.context import (
    spec_state_test,
    with_presets,
    with_capella_and_later,
    with_capella_until_eip7732,
)
from eth2spec.test.helpers.constants import MAINNET, MINIMAL
from eth2spec.test.helpers.execution_payload import (
    build_empty_execution_payload,
    compute_el_block_hash,
)
from eth2spec.test.helpers.random import (
    randomize_state,
)
from eth2spec.test.helpers.state import (
    next_epoch,
    next_slot,
)
from eth2spec.test.helpers.withdrawals import (
    get_expected_withdrawals,
    prepare_expected_withdrawals,
    set_eth1_withdrawal_credential_with_balance,
    set_validator_fully_withdrawable,
    set_validator_partially_withdrawable,
    run_withdrawals_processing,
)


@with_capella_until_eip7732
@spec_state_test
def test_success_zero_expected_withdrawals(spec, state):
    assert len(get_expected_withdrawals(spec, state)) == 0

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)

    yield from run_withdrawals_processing(spec, state, execution_payload)


@with_capella_until_eip7732
@spec_state_test
def test_success_one_full_withdrawal(spec, state):
    fully_withdrawable_indices, partial_withdrawals_indices = prepare_expected_withdrawals(
        spec, state, rng=random.Random(42), num_full_withdrawals=1)
    assert len(fully_withdrawable_indices) == 1
    assert len(partial_withdrawals_indices) == 0

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)

    yield from run_withdrawals_processing(
        spec, state, execution_payload,
        fully_withdrawable_indices=fully_withdrawable_indices,
        partial_withdrawals_indices=partial_withdrawals_indices)


@with_capella_until_eip7732
@spec_state_test
def test_success_one_partial_withdrawal(spec, state):
    fully_withdrawable_indices, partial_withdrawals_indices = prepare_expected_withdrawals(
        spec, state, rng=random.Random(42), num_partial_withdrawals=1)
    assert len(fully_withdrawable_indices) == 0
    assert len(partial_withdrawals_indices) == 1
    for index in partial_withdrawals_indices:
        assert state.balances[index] > spec.MAX_EFFECTIVE_BALANCE

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)

    yield from run_withdrawals_processing(
        spec, state, execution_payload,
        fully_withdrawable_indices=fully_withdrawable_indices,
        partial_withdrawals_indices=partial_withdrawals_indices
    )


@with_capella_until_eip7732
@spec_state_test
def test_success_mixed_fully_and_partial_withdrawable(spec, state):
    num_full_withdrawals = spec.MAX_WITHDRAWALS_PER_PAYLOAD // 2
    num_partial_withdrawals = spec.MAX_WITHDRAWALS_PER_PAYLOAD - num_full_withdrawals
    fully_withdrawable_indices, partial_withdrawals_indices = prepare_expected_withdrawals(
        spec, state,
        rng=random.Random(42),
        num_full_withdrawals=num_full_withdrawals,
        num_partial_withdrawals=num_partial_withdrawals,
    )

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)

    yield from run_withdrawals_processing(
        spec, state, execution_payload,
        fully_withdrawable_indices=fully_withdrawable_indices,
        partial_withdrawals_indices=partial_withdrawals_indices)


@with_capella_until_eip7732
@with_presets([MAINNET], reason="too few validators with minimal config")
@spec_state_test
def test_success_all_fully_withdrawable_in_one_sweep(spec, state):
    assert len(state.validators) <= spec.MAX_VALIDATORS_PER_WITHDRAWALS_SWEEP

    withdrawal_count = len(state.validators)
    fully_withdrawable_indices, partial_withdrawals_indices = prepare_expected_withdrawals(
        spec, state, rng=random.Random(42), num_full_withdrawals=withdrawal_count)

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)

    yield from run_withdrawals_processing(
        spec, state, execution_payload,
        fully_withdrawable_indices=fully_withdrawable_indices,
        partial_withdrawals_indices=partial_withdrawals_indices)


@with_capella_until_eip7732
@with_presets([MINIMAL], reason="too many validators with mainnet config")
@spec_state_test
def test_success_all_fully_withdrawable(spec, state):
    assert len(state.validators) > spec.MAX_VALIDATORS_PER_WITHDRAWALS_SWEEP

    withdrawal_count = spec.MAX_VALIDATORS_PER_WITHDRAWALS_SWEEP
    fully_withdrawable_indices, partial_withdrawals_indices = prepare_expected_withdrawals(
        spec, state, rng=random.Random(42), num_full_withdrawals=withdrawal_count)

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)

    yield from run_withdrawals_processing(
        spec, state, execution_payload,
        fully_withdrawable_indices=fully_withdrawable_indices,
        partial_withdrawals_indices=partial_withdrawals_indices)


@with_capella_until_eip7732
@with_presets([MAINNET], reason="too few validators with minimal config")
@spec_state_test
def test_success_all_partially_withdrawable_in_one_sweep(spec, state):
    assert len(state.validators) <= spec.MAX_VALIDATORS_PER_WITHDRAWALS_SWEEP

    withdrawal_count = len(state.validators)
    fully_withdrawable_indices, partial_withdrawals_indices = prepare_expected_withdrawals(
        spec, state, rng=random.Random(42), num_partial_withdrawals=withdrawal_count)

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)

    yield from run_withdrawals_processing(
        spec, state, execution_payload,
        fully_withdrawable_indices=fully_withdrawable_indices,
        partial_withdrawals_indices=partial_withdrawals_indices)


@with_capella_until_eip7732
@with_presets([MINIMAL], reason="too many validators with mainnet config")
@spec_state_test
def test_success_all_partially_withdrawable(spec, state):
    assert len(state.validators) > spec.MAX_VALIDATORS_PER_WITHDRAWALS_SWEEP

    withdrawal_count = spec.MAX_VALIDATORS_PER_WITHDRAWALS_SWEEP
    fully_withdrawable_indices, partial_withdrawals_indices = prepare_expected_withdrawals(
        spec, state, rng=random.Random(42), num_partial_withdrawals=withdrawal_count)

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)

    yield from run_withdrawals_processing(
        spec, state, execution_payload,
        fully_withdrawable_indices=fully_withdrawable_indices,
        partial_withdrawals_indices=partial_withdrawals_indices)


#
# Failure cases in which the number of withdrawals in the execution_payload is incorrect
#

@with_capella_until_eip7732
@spec_state_test
def test_invalid_non_withdrawable_non_empty_withdrawals(spec, state):
    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)
    withdrawal = spec.Withdrawal(
        index=0,
        validator_index=0,
        address=b'\x30' * 20,
        amount=420,
    )
    execution_payload.withdrawals.append(withdrawal)
    execution_payload.block_hash = compute_el_block_hash(spec, execution_payload, state)

    yield from run_withdrawals_processing(spec, state, execution_payload, valid=False)


@with_capella_until_eip7732
@spec_state_test
def test_invalid_one_expected_full_withdrawal_and_none_in_withdrawals(spec, state):
    prepare_expected_withdrawals(spec, state, rng=random.Random(42), num_full_withdrawals=1)

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.withdrawals = []
    execution_payload.block_hash = compute_el_block_hash(spec, execution_payload, state)

    yield from run_withdrawals_processing(spec, state, execution_payload, valid=False)


@with_capella_until_eip7732
@spec_state_test
def test_invalid_one_expected_partial_withdrawal_and_none_in_withdrawals(spec, state):
    prepare_expected_withdrawals(spec, state, rng=random.Random(42), num_partial_withdrawals=1)

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.withdrawals = []
    execution_payload.block_hash = compute_el_block_hash(spec, execution_payload, state)

    yield from run_withdrawals_processing(spec, state, execution_payload, valid=False)


@with_capella_until_eip7732
@spec_state_test
def test_invalid_one_expected_full_withdrawal_and_duplicate_in_withdrawals(spec, state):
    prepare_expected_withdrawals(spec, state, rng=random.Random(42), num_full_withdrawals=2)

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.withdrawals.append(execution_payload.withdrawals[0].copy())
    execution_payload.block_hash = compute_el_block_hash(spec, execution_payload, state)

    yield from run_withdrawals_processing(spec, state, execution_payload, valid=False)


@with_capella_until_eip7732
@spec_state_test
def test_invalid_two_expected_partial_withdrawal_and_duplicate_in_withdrawals(spec, state):
    prepare_expected_withdrawals(spec, state, rng=random.Random(42), num_partial_withdrawals=2)

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.withdrawals.append(execution_payload.withdrawals[0].copy())
    execution_payload.block_hash = compute_el_block_hash(spec, execution_payload, state)

    yield from run_withdrawals_processing(spec, state, execution_payload, valid=False)


@with_capella_until_eip7732
@spec_state_test
def test_invalid_max_per_slot_full_withdrawals_and_one_less_in_withdrawals(spec, state):
    prepare_expected_withdrawals(spec, state, rng=random.Random(42),
                                 num_full_withdrawals=spec.MAX_WITHDRAWALS_PER_PAYLOAD)

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.withdrawals = execution_payload.withdrawals[:-1]
    execution_payload.block_hash = compute_el_block_hash(spec, execution_payload, state)

    yield from run_withdrawals_processing(spec, state, execution_payload, valid=False)


@with_capella_until_eip7732
@spec_state_test
def test_invalid_max_per_slot_partial_withdrawals_and_one_less_in_withdrawals(spec, state):
    prepare_expected_withdrawals(spec, state, rng=random.Random(42),
                                 num_partial_withdrawals=spec.MAX_WITHDRAWALS_PER_PAYLOAD)

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.withdrawals = execution_payload.withdrawals[:-1]
    execution_payload.block_hash = compute_el_block_hash(spec, execution_payload, state)

    yield from run_withdrawals_processing(spec, state, execution_payload, valid=False)


@with_capella_until_eip7732
@spec_state_test
def test_invalid_a_lot_fully_withdrawable_too_few_in_withdrawals(spec, state):
    prepare_expected_withdrawals(spec, state, rng=random.Random(42),
                                 num_full_withdrawals=spec.MAX_WITHDRAWALS_PER_PAYLOAD * 4)

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.withdrawals = execution_payload.withdrawals[:-1]
    execution_payload.block_hash = compute_el_block_hash(spec, execution_payload, state)

    yield from run_withdrawals_processing(spec, state, execution_payload, valid=False)


@with_capella_until_eip7732
@spec_state_test
def test_invalid_a_lot_partially_withdrawable_too_few_in_withdrawals(spec, state):
    prepare_expected_withdrawals(spec, state, rng=random.Random(42),
                                 num_partial_withdrawals=spec.MAX_WITHDRAWALS_PER_PAYLOAD * 4)

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.withdrawals = execution_payload.withdrawals[:-1]
    execution_payload.block_hash = compute_el_block_hash(spec, execution_payload, state)

    yield from run_withdrawals_processing(spec, state, execution_payload, valid=False)


@with_capella_until_eip7732
@spec_state_test
def test_invalid_a_lot_mixed_withdrawable_in_queue_too_few_in_withdrawals(spec, state):
    prepare_expected_withdrawals(spec, state, rng=random.Random(42),
                                 num_full_withdrawals=spec.MAX_WITHDRAWALS_PER_PAYLOAD,
                                 num_partial_withdrawals=spec.MAX_WITHDRAWALS_PER_PAYLOAD)

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.withdrawals = execution_payload.withdrawals[:-1]
    execution_payload.block_hash = compute_el_block_hash(spec, execution_payload, state)

    yield from run_withdrawals_processing(spec, state, execution_payload, valid=False)


#
# Failure cases in which the withdrawals in the execution_payload are incorrect
#

@with_capella_until_eip7732
@spec_state_test
def test_invalid_incorrect_withdrawal_index(spec, state):
    prepare_expected_withdrawals(spec, state, rng=random.Random(42),
                                 num_full_withdrawals=1)

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.withdrawals[0].index += 1
    execution_payload.block_hash = compute_el_block_hash(spec, execution_payload, state)

    yield from run_withdrawals_processing(spec, state, execution_payload, valid=False)


@with_capella_until_eip7732
@spec_state_test
def test_invalid_incorrect_address_full(spec, state):
    prepare_expected_withdrawals(spec, state, rng=random.Random(42),
                                 num_full_withdrawals=1)

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.withdrawals[0].address = b'\xff' * 20
    execution_payload.block_hash = compute_el_block_hash(spec, execution_payload, state)

    yield from run_withdrawals_processing(spec, state, execution_payload, valid=False)


@with_capella_until_eip7732
@spec_state_test
def test_invalid_incorrect_address_partial(spec, state):
    prepare_expected_withdrawals(spec, state, rng=random.Random(42),
                                 num_partial_withdrawals=1)

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.withdrawals[0].address = b'\xff' * 20
    execution_payload.block_hash = compute_el_block_hash(spec, execution_payload, state)

    yield from run_withdrawals_processing(spec, state, execution_payload, valid=False)


@with_capella_until_eip7732
@spec_state_test
def test_invalid_incorrect_amount_full(spec, state):
    prepare_expected_withdrawals(spec, state, rng=random.Random(42), num_full_withdrawals=1)

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.withdrawals[0].amount += 1
    execution_payload.block_hash = compute_el_block_hash(spec, execution_payload, state)

    yield from run_withdrawals_processing(spec, state, execution_payload, valid=False)


@with_capella_until_eip7732
@spec_state_test
def test_invalid_incorrect_amount_partial(spec, state):
    prepare_expected_withdrawals(spec, state, rng=random.Random(42), num_full_withdrawals=1)

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)
    execution_payload.withdrawals[0].amount += 1
    execution_payload.block_hash = compute_el_block_hash(spec, execution_payload, state)

    yield from run_withdrawals_processing(spec, state, execution_payload, valid=False)


@with_capella_until_eip7732
@spec_state_test
def test_invalid_one_of_many_incorrectly_full(spec, state):
    prepare_expected_withdrawals(spec, state, rng=random.Random(42),
                                 num_full_withdrawals=spec.MAX_WITHDRAWALS_PER_PAYLOAD * 4)

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)
    num_withdrawals = len(execution_payload.withdrawals)

    # Pick withdrawal in middle of list and mutate
    withdrawal = execution_payload.withdrawals[num_withdrawals // 2]
    withdrawal.index += 1
    withdrawal.address = b'\x99' * 20
    withdrawal.amount += 4000000
    execution_payload.block_hash = compute_el_block_hash(spec, execution_payload, state)

    yield from run_withdrawals_processing(spec, state, execution_payload, valid=False)


@with_capella_until_eip7732
@spec_state_test
def test_invalid_one_of_many_incorrectly_partial(spec, state):
    prepare_expected_withdrawals(spec, state, rng=random.Random(42),
                                 num_partial_withdrawals=spec.MAX_WITHDRAWALS_PER_PAYLOAD * 4)

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)
    num_withdrawals = len(execution_payload.withdrawals)

    # Pick withdrawal in middle of list and mutate
    withdrawal = execution_payload.withdrawals[num_withdrawals // 2]
    withdrawal.index += 1
    withdrawal.address = b'\x99' * 20
    withdrawal.amount += 4000000
    execution_payload.block_hash = compute_el_block_hash(spec, execution_payload, state)

    yield from run_withdrawals_processing(spec, state, execution_payload, valid=False)


@with_capella_until_eip7732
@spec_state_test
def test_invalid_many_incorrectly_full(spec, state):
    prepare_expected_withdrawals(spec, state, rng=random.Random(42),
                                 num_full_withdrawals=spec.MAX_WITHDRAWALS_PER_PAYLOAD * 4)

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)
    for i, withdrawal in enumerate(execution_payload.withdrawals):
        if i % 3 == 0:
            withdrawal.index += 1
        elif i % 3 == 1:
            withdrawal.address = i.to_bytes(20, 'big')
        else:
            withdrawal.amount += 1
    execution_payload.block_hash = compute_el_block_hash(spec, execution_payload, state)

    yield from run_withdrawals_processing(spec, state, execution_payload, valid=False)


@with_capella_until_eip7732
@spec_state_test
def test_invalid_many_incorrectly_partial(spec, state):
    prepare_expected_withdrawals(spec, state, rng=random.Random(42),
                                 num_partial_withdrawals=spec.MAX_WITHDRAWALS_PER_PAYLOAD * 4)

    next_slot(spec, state)
    execution_payload = build_empty_execution_payload(spec, state)
    for i, withdrawal in enumerate(execution_payload.withdrawals):
        if i % 3 == 0:
            withdrawal.index += 1
        elif i % 3 == 1:
            withdrawal.address = i.to_bytes(20, 'big')
        else:
            withdrawal.amount += 1
    execution_payload.block_hash = compute_el_block_hash(spec, execution_payload, state)

    yield from run_withdrawals_processing(spec, state, execution_payload, valid=False)


#
# More full withdrawal cases
#

@with_capella_until_eip7732
@spec_state_test
def test_withdrawable_epoch_but_0_balance(spec, state):
    current_epoch = spec.get_current_epoch(state)
    set_validator_fully_withdrawable(spec, state, 0, current_epoch)

    state.validators[0].effective_balance = 10000000000
    state.balances[0] = 0

    execution_payload = build_empty_execution_payload(spec, state)

    yield from run_withdrawals_processing(spec, state, execution_payload, num_expected_withdrawals=0)


@with_capella_until_eip7732
@spec_state_test
def test_withdrawable_epoch_but_0_effective_balance_0_balance(spec, state):
    current_epoch = spec.get_current_epoch(state)
    set_validator_fully_withdrawable(spec, state, 0, current_epoch)

    state.validators[0].effective_balance = 0
    state.balances[0] = 0

    execution_payload = build_empty_execution_payload(spec, state)

    yield from run_withdrawals_processing(spec, state, execution_payload, num_expected_withdrawals=0)


@with_capella_until_eip7732
@spec_state_test
def test_withdrawable_epoch_but_0_effective_balance_nonzero_balance(spec, state):
    current_epoch = spec.get_current_epoch(state)
    set_validator_fully_withdrawable(spec, state, 0, current_epoch)

    state.validators[0].effective_balance = 0
    state.balances[0] = 100000000

    execution_payload = build_empty_execution_payload(spec, state)

    yield from run_withdrawals_processing(spec, state, execution_payload, num_expected_withdrawals=1)


@with_capella_until_eip7732
@spec_state_test
def test_no_withdrawals_but_some_next_epoch(spec, state):
    current_epoch = spec.get_current_epoch(state)

    # Make a few validators withdrawable at the *next* epoch
    for index in range(3):
        set_validator_fully_withdrawable(spec, state, index, current_epoch + 1)

    execution_payload = build_empty_execution_payload(spec, state)

    yield from run_withdrawals_processing(spec, state, execution_payload, num_expected_withdrawals=0)


@with_capella_until_eip7732
@spec_state_test
def test_all_withdrawal(spec, state):
    # Make all validators withdrawable
    for index in range(len(state.validators)):
        set_validator_fully_withdrawable(spec, state, index)

    execution_payload = build_empty_execution_payload(spec, state)

    yield from run_withdrawals_processing(
        spec, state, execution_payload,
        num_expected_withdrawals=spec.MAX_WITHDRAWALS_PER_PAYLOAD)


def run_random_full_withdrawals_test(spec, state, rng):
    randomize_state(spec, state, rng)
    for index in range(len(state.validators)):
        # 50% withdrawable
        if rng.choice([True, False]):
            set_validator_fully_withdrawable(spec, state, index)
            validator = state.validators[index]
            # 12.5% unset credentials
            if rng.randint(0, 7) == 0:
                validator.withdrawal_credentials = spec.BLS_WITHDRAWAL_PREFIX + validator.withdrawal_credentials[1:]
            # 12.5% not enough balance
            if rng.randint(0, 7) == 0:
                state.balances[index] = 0
            # 12.5% not close enough epoch
            if rng.randint(0, 7) == 0:
                validator.withdrawable_epoch += 1

    execution_payload = build_empty_execution_payload(spec, state)

    yield from run_withdrawals_processing(spec, state, execution_payload)


@with_capella_until_eip7732
@spec_state_test
def test_random_full_withdrawals_0(spec, state):
    yield from run_random_full_withdrawals_test(spec, state, random.Random(444))


@with_capella_until_eip7732
@spec_state_test
def test_random_full_withdrawals_1(spec, state):
    yield from run_random_full_withdrawals_test(spec, state, random.Random(420))


@with_capella_until_eip7732
@spec_state_test
def test_random_full_withdrawals_2(spec, state):
    yield from run_random_full_withdrawals_test(spec, state, random.Random(200))


@with_capella_until_eip7732
@spec_state_test
def test_random_full_withdrawals_3(spec, state):
    yield from run_random_full_withdrawals_test(spec, state, random.Random(2000000))


#
# More partial withdrawal cases
#

@with_capella_and_later
@spec_state_test
def test_success_no_max_effective_balance(spec, state):
    validator_index = len(state.validators) // 2
    # To be partially withdrawable, the validator's effective balance must be maxed out
    set_eth1_withdrawal_credential_with_balance(
        spec,
        state,
        validator_index,
        # Reduce validator's effective balance to make it ineligible for withdrawals
        effective_balance=spec.MAX_EFFECTIVE_BALANCE - spec.EFFECTIVE_BALANCE_INCREMENT,
        # Give the validator an excess balance, so this isn't the reason it fails
        balance=spec.MAX_EFFECTIVE_BALANCE + 1,
    )
    validator = state.validators[validator_index]

    assert validator.effective_balance == spec.MAX_EFFECTIVE_BALANCE - spec.EFFECTIVE_BALANCE_INCREMENT
    assert not spec.is_partially_withdrawable_validator(validator, state.balances[validator_index])

    execution_payload = build_empty_execution_payload(spec, state)

    yield from run_withdrawals_processing(spec, state, execution_payload, num_expected_withdrawals=0)


@with_capella_and_later
@spec_state_test
def test_success_no_excess_balance(spec, state):
    validator_index = len(state.validators) // 2
    # To be partially withdrawable, the validator needs an excess balance
    set_eth1_withdrawal_credential_with_balance(
        spec,
        state,
        validator_index,
        # Ensure validator has the required effective balance, so this isn't the reason it fails
        effective_balance=spec.MAX_EFFECTIVE_BALANCE,
        # Remove validator's excess balance to make it ineligible for withdrawals
        balance=spec.MAX_EFFECTIVE_BALANCE,
    )
    validator = state.validators[validator_index]

    assert validator.effective_balance == spec.MAX_EFFECTIVE_BALANCE
    assert not spec.is_partially_withdrawable_validator(validator, state.balances[validator_index])

    execution_payload = build_empty_execution_payload(spec, state)

    yield from run_withdrawals_processing(spec, state, execution_payload, num_expected_withdrawals=0)


@with_capella_and_later
@spec_state_test
def test_success_excess_balance_but_no_max_effective_balance(spec, state):
    validator_index = len(state.validators) // 2
    set_validator_partially_withdrawable(spec, state, validator_index)
    validator = state.validators[validator_index]

    # To be partially withdrawable, the validator needs both a maxed out effective balance and an excess balance
    validator.effective_balance = spec.MAX_EFFECTIVE_BALANCE - 1

    assert not spec.is_partially_withdrawable_validator(validator, state.balances[validator_index])

    execution_payload = build_empty_execution_payload(spec, state)

    yield from run_withdrawals_processing(spec, state, execution_payload, num_expected_withdrawals=0)


@with_capella_and_later
@spec_state_test
def test_success_one_partial_withdrawable_not_yet_active(spec, state):
    validator_index = min(len(state.validators) // 2, spec.MAX_VALIDATORS_PER_WITHDRAWALS_SWEEP - 1)
    state.validators[validator_index].activation_epoch += 4
    set_validator_partially_withdrawable(spec, state, validator_index)

    assert not spec.is_active_validator(state.validators[validator_index], spec.get_current_epoch(state))

    execution_payload = build_empty_execution_payload(spec, state)

    yield from run_withdrawals_processing(spec, state, execution_payload, num_expected_withdrawals=1)


@with_capella_and_later
@spec_state_test
def test_success_one_partial_withdrawable_in_exit_queue(spec, state):
    validator_index = min(len(state.validators) // 2, spec.MAX_VALIDATORS_PER_WITHDRAWALS_SWEEP - 1)
    state.validators[validator_index].exit_epoch = spec.get_current_epoch(state) + 1
    set_validator_partially_withdrawable(spec, state, validator_index)

    assert spec.is_active_validator(state.validators[validator_index], spec.get_current_epoch(state))
    assert not spec.is_active_validator(state.validators[validator_index], spec.get_current_epoch(state) + 1)

    execution_payload = build_empty_execution_payload(spec, state)

    yield from run_withdrawals_processing(spec, state, execution_payload, num_expected_withdrawals=1)


@with_capella_and_later
@spec_state_test
def test_success_one_partial_withdrawable_exited(spec, state):
    validator_index = min(len(state.validators) // 2, spec.MAX_VALIDATORS_PER_WITHDRAWALS_SWEEP - 1)
    state.validators[validator_index].exit_epoch = spec.get_current_epoch(state)
    set_validator_partially_withdrawable(spec, state, validator_index)

    assert not spec.is_active_validator(state.validators[validator_index], spec.get_current_epoch(state))

    execution_payload = build_empty_execution_payload(spec, state)

    yield from run_withdrawals_processing(spec, state, execution_payload, num_expected_withdrawals=1)


@with_capella_and_later
@spec_state_test
def test_success_one_partial_withdrawable_active_and_slashed(spec, state):
    validator_index = min(len(state.validators) // 2, spec.MAX_VALIDATORS_PER_WITHDRAWALS_SWEEP - 1)
    state.validators[validator_index].slashed = True
    set_validator_partially_withdrawable(spec, state, validator_index)

    assert spec.is_active_validator(state.validators[validator_index], spec.get_current_epoch(state))

    execution_payload = build_empty_execution_payload(spec, state)

    yield from run_withdrawals_processing(spec, state, execution_payload, num_expected_withdrawals=1)


@with_capella_and_later
@spec_state_test
def test_success_one_partial_withdrawable_exited_and_slashed(spec, state):
    validator_index = min(len(state.validators) // 2, spec.MAX_VALIDATORS_PER_WITHDRAWALS_SWEEP - 1)
    state.validators[validator_index].slashed = True
    state.validators[validator_index].exit_epoch = spec.get_current_epoch(state)
    set_validator_partially_withdrawable(spec, state, validator_index)

    assert not spec.is_active_validator(state.validators[validator_index], spec.get_current_epoch(state))

    execution_payload = build_empty_execution_payload(spec, state)

    yield from run_withdrawals_processing(spec, state, execution_payload, num_expected_withdrawals=1)


@with_capella_and_later
@spec_state_test
def test_success_two_partial_withdrawable(spec, state):
    set_validator_partially_withdrawable(spec, state, 0)
    set_validator_partially_withdrawable(spec, state, 1)

    execution_payload = build_empty_execution_payload(spec, state)

    yield from run_withdrawals_processing(spec, state, execution_payload, num_expected_withdrawals=2)


@with_capella_and_later
@spec_state_test
def test_success_max_partial_withdrawable(spec, state):
    # Sanity check that this test works for this state
    assert len(state.validators) >= spec.MAX_WITHDRAWALS_PER_PAYLOAD

    for i in range(spec.MAX_WITHDRAWALS_PER_PAYLOAD):
        set_validator_partially_withdrawable(spec, state, i)

    execution_payload = build_empty_execution_payload(spec, state)

    yield from run_withdrawals_processing(
        spec, state, execution_payload, num_expected_withdrawals=spec.MAX_WITHDRAWALS_PER_PAYLOAD)


@with_capella_and_later
@with_presets([MINIMAL], reason="not enough validators with mainnet config")
@spec_state_test
def test_success_max_plus_one_withdrawable(spec, state):
    # Sanity check that this test works for this state
    assert len(state.validators) >= spec.MAX_WITHDRAWALS_PER_PAYLOAD + 1

    # More than MAX_WITHDRAWALS_PER_PAYLOAD partially withdrawable
    for i in range(spec.MAX_WITHDRAWALS_PER_PAYLOAD + 1):
        set_validator_partially_withdrawable(spec, state, i)

    execution_payload = build_empty_execution_payload(spec, state)

    # Should only have MAX_WITHDRAWALS_PER_PAYLOAD withdrawals created
    yield from run_withdrawals_processing(
        spec, state, execution_payload, num_expected_withdrawals=spec.MAX_WITHDRAWALS_PER_PAYLOAD)


def run_random_partial_withdrawals_test(spec, state, rng):
    for _ in range(rng.randint(0, 2)):
        next_epoch(spec, state)
    randomize_state(spec, state, rng)

    num_validators = len(state.validators)
    state.next_withdrawal_validator_index = rng.randint(0, num_validators - 1)

    num_partially_withdrawable = rng.randint(0, num_validators - 1)
    partially_withdrawable_indices = rng.sample(range(num_validators), num_partially_withdrawable)
    for index in partially_withdrawable_indices:
        set_validator_partially_withdrawable(spec, state, index, excess_balance=rng.randint(1, 1000000000))

    execution_payload = build_empty_execution_payload(spec, state)

    # Note: due to the randomness and other block processing, some of these set as "partially withdrawable"
    # may not be partially withdrawable once we get to ``process_withdrawals``,
    # thus *not* using the optional third param in this call
    yield from run_withdrawals_processing(spec, state, execution_payload)


@with_capella_and_later
@spec_state_test
def test_random_0(spec, state):
    yield from run_random_partial_withdrawals_test(spec, state, random.Random(0))


@with_capella_and_later
@spec_state_test
def test_random_partial_withdrawals_1(spec, state):
    yield from run_random_partial_withdrawals_test(spec, state, random.Random(1))


@with_capella_and_later
@spec_state_test
def test_random_partial_withdrawals_2(spec, state):
    yield from run_random_partial_withdrawals_test(spec, state, random.Random(2))


@with_capella_and_later
@spec_state_test
def test_random_partial_withdrawals_3(spec, state):
    yield from run_random_partial_withdrawals_test(spec, state, random.Random(3))


@with_capella_and_later
@spec_state_test
def test_random_partial_withdrawals_4(spec, state):
    yield from run_random_partial_withdrawals_test(spec, state, random.Random(4))


@with_capella_and_later
@spec_state_test
def test_random_partial_withdrawals_5(spec, state):
    yield from run_random_partial_withdrawals_test(spec, state, random.Random(5))


@with_capella_and_later
@spec_state_test
def test_partially_withdrawable_validator_legacy_max_plus_one(spec, state):
    """Test legacy validator with balance just above MAX_EFFECTIVE_BALANCE"""
    validator_index = 0
    set_eth1_withdrawal_credential_with_balance(
        spec, state,
        validator_index,
        effective_balance=spec.MAX_EFFECTIVE_BALANCE,
        balance=spec.MAX_EFFECTIVE_BALANCE + 1
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


@with_capella_and_later
@spec_state_test
def test_partially_withdrawable_validator_legacy_exact_max(spec, state):
    """Test legacy validator whose balance is exactly MAX_EFFECTIVE_BALANCE"""
    validator_index = 0
    set_eth1_withdrawal_credential_with_balance(
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


@with_capella_and_later
@spec_state_test
def test_partially_withdrawable_validator_legacy_max_minus_one(spec, state):
    """Test legacy validator whose balance is below MAX_EFFECTIVE_BALANCE"""
    validator_index = 0
    set_eth1_withdrawal_credential_with_balance(
        spec, state,
        validator_index,
        # Assume effective balance updates haven't happened yet
        effective_balance=spec.MAX_EFFECTIVE_BALANCE,
        balance=spec.MAX_EFFECTIVE_BALANCE - 1
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
