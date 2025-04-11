from eth2spec.test.context import spec_state_test, always_bls, with_electra_and_later
from eth2spec.test.helpers.deposits import (
    prepare_deposit_request,
    run_deposit_request_processing,
)


@with_electra_and_later
@spec_state_test
def test_process_deposit_request_min_activation(spec, state):
    # fresh deposit = next validator index = validator appended to registry
    validator_index = len(state.validators)
    # effective balance will be exactly the same as balance.
    amount = spec.MIN_ACTIVATION_BALANCE
    deposit_request = prepare_deposit_request(spec, validator_index, amount, signed=True)

    yield from run_deposit_request_processing(spec, state, deposit_request, validator_index)


@with_electra_and_later
@spec_state_test
def test_process_deposit_request_extra_gwei(spec, state):
    """The deposit amount must be at least 1 ETH and must be a multiple of gwei."""
    validator_index = len(state.validators)
    # An amount with some gwei (the +1 at the end)
    amount = spec.EFFECTIVE_BALANCE_INCREMENT + 1
    deposit_request = prepare_deposit_request(spec, validator_index, amount, signed=True)

    yield from run_deposit_request_processing(spec, state, deposit_request, validator_index)

    # Ensure the deposit amount is not a multiple of ETH
    assert state.pending_deposits[0].amount % spec.EFFECTIVE_BALANCE_INCREMENT != 0


@with_electra_and_later
@spec_state_test
def test_process_deposit_request_max_effective_balance_compounding(spec, state):
    # fresh deposit = next validator index = validator appended to registry
    validator_index = len(state.validators)
    # effective balance will be exactly the same as balance.
    amount = spec.MAX_EFFECTIVE_BALANCE_ELECTRA
    withdrawal_credentials = (
        spec.COMPOUNDING_WITHDRAWAL_PREFIX
        + b"\x00" * 11  # specified 0s
        + b"\x59" * 20  # a 20-byte eth1 address
    )
    deposit_request = prepare_deposit_request(
        spec, validator_index, amount, signed=True, withdrawal_credentials=withdrawal_credentials
    )

    yield from run_deposit_request_processing(spec, state, deposit_request, validator_index)


@with_electra_and_later
@spec_state_test
def test_process_deposit_request_greater_than_max_effective_balance_compounding(spec, state):
    validator_index = len(state.validators)
    withdrawal_credentials = (
        spec.COMPOUNDING_WITHDRAWAL_PREFIX
        + b"\x00" * 11  # specified 0s
        + b"\x59" * 20  # a 20-byte eth1 address
    )
    deposit_request = prepare_deposit_request(
        spec,
        validator_index,
        # An amount greater than the max effective balance for electra
        spec.MAX_EFFECTIVE_BALANCE_ELECTRA + spec.EFFECTIVE_BALANCE_INCREMENT,
        signed=True,
        withdrawal_credentials=withdrawal_credentials,
    )

    yield from run_deposit_request_processing(spec, state, deposit_request, validator_index)


@with_electra_and_later
@spec_state_test
def test_process_deposit_request_top_up_min_activation(spec, state):
    validator_index = 0
    amount = spec.MIN_ACTIVATION_BALANCE // 4
    deposit_request = prepare_deposit_request(spec, validator_index, amount, signed=True)

    state.balances[validator_index] = spec.MIN_ACTIVATION_BALANCE
    state.validators[validator_index].effective_balance = spec.MIN_ACTIVATION_BALANCE

    yield from run_deposit_request_processing(spec, state, deposit_request, validator_index)


@with_electra_and_later
@spec_state_test
def test_process_deposit_request_top_up_still_less_than_min_activation(spec, state):
    validator_index = 0
    amount = spec.EFFECTIVE_BALANCE_INCREMENT
    deposit_request = prepare_deposit_request(spec, validator_index, amount, signed=True)

    balance = 20 * spec.EFFECTIVE_BALANCE_INCREMENT
    state.balances[validator_index] = balance
    state.validators[validator_index].effective_balance = balance

    yield from run_deposit_request_processing(spec, state, deposit_request, validator_index)


@with_electra_and_later
@spec_state_test
def test_process_deposit_request_top_up_max_effective_balance_compounding(spec, state):
    validator_index = 0
    amount = spec.MIN_ACTIVATION_BALANCE // 4
    withdrawal_credentials = (
        spec.COMPOUNDING_WITHDRAWAL_PREFIX
        + b"\x00" * 11  # specified 0s
        + b"\x59" * 20  # a 20-byte eth1 address
    )

    state.balances[validator_index] = spec.MAX_EFFECTIVE_BALANCE
    state.validators[validator_index].effective_balance = spec.MAX_EFFECTIVE_BALANCE
    state.validators[validator_index].withdrawal_credentials = withdrawal_credentials

    deposit_request = prepare_deposit_request(
        spec, validator_index, amount, signed=True, withdrawal_credentials=withdrawal_credentials
    )

    yield from run_deposit_request_processing(spec, state, deposit_request, validator_index)


@with_electra_and_later
@spec_state_test
@always_bls
def test_process_deposit_request_invalid_sig(spec, state):
    # fresh deposit = next validator index = validator appended to registry
    validator_index = len(state.validators)
    # effective balance will be exactly the same as balance.
    amount = spec.MIN_ACTIVATION_BALANCE
    deposit_request = prepare_deposit_request(spec, validator_index, amount)

    yield from run_deposit_request_processing(spec, state, deposit_request, validator_index)


@with_electra_and_later
@spec_state_test
@always_bls
def test_process_deposit_request_top_up_invalid_sig(spec, state):
    validator_index = 0
    amount = spec.MIN_ACTIVATION_BALANCE // 4
    deposit_request = prepare_deposit_request(spec, validator_index, amount)

    state.balances[validator_index] = spec.MIN_ACTIVATION_BALANCE
    state.validators[validator_index].effective_balance = spec.MIN_ACTIVATION_BALANCE

    yield from run_deposit_request_processing(spec, state, deposit_request, validator_index)


@with_electra_and_later
@spec_state_test
def test_process_deposit_request_set_start_index(spec, state):
    assert state.deposit_requests_start_index == spec.UNSET_DEPOSIT_REQUESTS_START_INDEX

    # fresh deposit = next validator index = validator appended to registry
    validator_index = len(state.validators)
    # effective balance will be exactly the same as balance.
    amount = spec.MIN_ACTIVATION_BALANCE
    deposit_request = prepare_deposit_request(spec, validator_index, amount, signed=True)

    yield from run_deposit_request_processing(spec, state, deposit_request, validator_index)

    assert state.deposit_requests_start_index == deposit_request.index


@with_electra_and_later
@spec_state_test
def test_process_deposit_request_set_start_index_only_once(spec, state):
    initial_start_index = 1

    # fresh deposit = next validator index = validator appended to registry
    validator_index = len(state.validators)
    # effective balance will be exactly the same as balance.
    amount = spec.MIN_ACTIVATION_BALANCE
    deposit_request = prepare_deposit_request(spec, validator_index, amount, signed=True)

    assert initial_start_index != deposit_request.index
    state.deposit_requests_start_index = initial_start_index

    yield from run_deposit_request_processing(spec, state, deposit_request, validator_index)

    assert state.deposit_requests_start_index == initial_start_index
