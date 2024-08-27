from eth2spec.test.context import spec_state_test, always_bls, with_electra_and_later
from eth2spec.test.helpers.deposits import (
    prepare_deposit_request,
    run_deposit_request_processing,
)


def _run_deposit_request_switching_to_compounding(
    spec,
    state,
    validator_index,
    initial_creds,
    request_creds,
    signed=True,
    effective=True
):
    deposit_request = prepare_deposit_request(
        spec,
        validator_index,
        # Minimal deposit amount
        amount=(spec.EFFECTIVE_BALANCE_INCREMENT * 1),
        withdrawal_credentials=request_creds,
        signed=signed
    )
    state.validators[validator_index].withdrawal_credentials = initial_creds

    yield from run_deposit_request_processing(
        spec,
        state,
        deposit_request,
        validator_index,
        switches_to_compounding=effective
    )

    if effective:
        # Withdrawal address must never be changed, the change applies to the type only
        expected_credentials = spec.COMPOUNDING_WITHDRAWAL_PREFIX + initial_creds[1:]
        assert state.validators[validator_index].withdrawal_credentials == expected_credentials
    else:
        assert state.validators[validator_index].withdrawal_credentials == initial_creds


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
def test_process_deposit_request_max_effective_balance_compounding(spec, state):
    # fresh deposit = next validator index = validator appended to registry
    validator_index = len(state.validators)
    # effective balance will be exactly the same as balance.
    amount = spec.MAX_EFFECTIVE_BALANCE_ELECTRA
    withdrawal_credentials = (
        spec.COMPOUNDING_WITHDRAWAL_PREFIX
        + b'\x00' * 11  # specified 0s
        + b'\x59' * 20  # a 20-byte eth1 address
    )
    deposit_request = prepare_deposit_request(
        spec,
        validator_index,
        amount,
        signed=True,
        withdrawal_credentials=withdrawal_credentials
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
def test_process_deposit_request_top_up_max_effective_balance_compounding(spec, state):
    validator_index = 0
    amount = spec.MIN_ACTIVATION_BALANCE // 4
    withdrawal_credentials = (
        spec.COMPOUNDING_WITHDRAWAL_PREFIX
        + b'\x00' * 11  # specified 0s
        + b'\x59' * 20  # a 20-byte eth1 address
    )

    state.balances[validator_index] = spec.MAX_EFFECTIVE_BALANCE
    state.validators[validator_index].effective_balance = spec.MAX_EFFECTIVE_BALANCE
    state.validators[validator_index].withdrawal_credentials = withdrawal_credentials

    deposit_request = prepare_deposit_request(
        spec,
        validator_index,
        amount,
        signed=True,
        withdrawal_credentials=withdrawal_credentials
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

    state.deposit_requests_start_index = initial_start_index

    yield from run_deposit_request_processing(spec, state, deposit_request, validator_index)

    assert state.deposit_requests_start_index == initial_start_index


@with_electra_and_later
@spec_state_test
def test_process_deposit_request_switch_to_compounding_normal(spec, state):
    validator_index = 0
    initial_withdrawal_credentials = (
        spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX
        + b'\x00' * 11  # specified 0s
        + b'\x59' * 20  # a 20-byte eth1 address
    )
    compounding_credentials = (
        spec.COMPOUNDING_WITHDRAWAL_PREFIX
        + b'\x00' * 11  # specified 0s
        + b'\x59' * 20  # a 20-byte eth1 address
    )

    yield from _run_deposit_request_switching_to_compounding(
        spec,
        state,
        validator_index,
        initial_withdrawal_credentials,
        compounding_credentials,
        effective=True
    )


@with_electra_and_later
@spec_state_test
def test_process_deposit_request_switch_to_compounding_with_excess(spec, state):
    validator_index = 0
    # there is excess balance that will be enqueued to pending deposits
    initial_balance = initial_effective_balance = (
        spec.MIN_ACTIVATION_BALANCE + spec.EFFECTIVE_BALANCE_INCREMENT // 2)
    initial_withdrawal_credentials = (
        spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX
        + b'\x00' * 11  # specified 0s
        + b'\x59' * 20  # a 20-byte eth1 address
    )
    compounding_credentials = (
        spec.COMPOUNDING_WITHDRAWAL_PREFIX
        + b'\x00' * 11  # specified 0s
        + b'\x59' * 20  # a 20-byte eth1 address
    )
    state.balances[validator_index] = initial_balance
    state.validators[validator_index].effective_balance = initial_effective_balance

    yield from _run_deposit_request_switching_to_compounding(
        spec,
        state,
        validator_index,
        initial_withdrawal_credentials,
        compounding_credentials,
        effective=True
    )


@with_electra_and_later
@spec_state_test
def test_process_deposit_request_switch_to_compounding_incorrect_credentials(spec, state):
    validator_index = 0
    initial_withdrawal_credentials = (
        spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX
        + b'\x00' * 11  # specified 0s
        + b'\x59' * 20  # a 20-byte eth1 address
    )
    compounding_credentials = (
        spec.COMPOUNDING_WITHDRAWAL_PREFIX + spec.hash(b"junk")[1:]
    )

    yield from _run_deposit_request_switching_to_compounding(
        spec,
        state,
        validator_index,
        initial_withdrawal_credentials,
        compounding_credentials,
        effective=True
    )


@with_electra_and_later
@spec_state_test
def test_process_deposit_request_switch_to_compounding_no_compounding(spec, state):
    validator_index = 0
    initial_withdrawal_credentials = (
        spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX
        + b'\x00' * 11  # specified 0s
        + b'\x59' * 20  # a 20-byte eth1 address
    )
    # credentials with ETH1 prefix
    incorrect_compounding_credentials = (
        b'\xFF'
        + b'\x00' * 11  # specified 0s
        + b'\x59' * 20  # a 20-byte eth1 address
    )

    yield from _run_deposit_request_switching_to_compounding(
        spec,
        state,
        validator_index,
        initial_withdrawal_credentials,
        incorrect_compounding_credentials,
        effective=False
    )


@with_electra_and_later
@spec_state_test
def test_process_deposit_request_switch_to_compounding_has_bls(spec, state):
    validator_index = 0
    initial_withdrawal_credentials = state.validators[validator_index].withdrawal_credentials.copy()
    compounding_credentials = (
        spec.COMPOUNDING_WITHDRAWAL_PREFIX
        + b'\x00' * 11  # specified 0s
        + b'\x59' * 20  # a 20-byte eth1 address
    )

    yield from _run_deposit_request_switching_to_compounding(
        spec,
        state,
        validator_index,
        initial_withdrawal_credentials,
        compounding_credentials,
        effective=False
    )


@with_electra_and_later
@spec_state_test
@always_bls
def test_process_deposit_request_switch_to_compounding_invalid_sig(spec, state):
    validator_index = 0
    initial_withdrawal_credentials = (
        spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX
        + b'\x00' * 11  # specified 0s
        + b'\x59' * 20  # a 20-byte eth1 address
    )
    compounding_credentials = (
        spec.COMPOUNDING_WITHDRAWAL_PREFIX
        + b'\x00' * 11  # specified 0s
        + b'\x59' * 20  # a 20-byte eth1 address
    )

    yield from _run_deposit_request_switching_to_compounding(
        spec,
        state,
        validator_index,
        initial_withdrawal_credentials,
        compounding_credentials,
        signed=False,
        effective=False
    )


@with_electra_and_later
@spec_state_test
def test_process_deposit_request_switch_to_compounding_inactive(spec, state):
    validator_index = 0
    initial_withdrawal_credentials = (
        spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX
        + b'\x00' * 11  # specified 0s
        + b'\x59' * 20  # a 20-byte eth1 address
    )
    compounding_credentials = (
        spec.COMPOUNDING_WITHDRAWAL_PREFIX
        + b'\x00' * 11  # specified 0s
        + b'\x59' * 20  # a 20-byte eth1 address
    )

    # Set exit_epoch to the current epoch to make validator inactive
    spec.initiate_validator_exit(state, validator_index)
    state.validators[validator_index].exit_epoch = spec.get_current_epoch(state)

    yield from _run_deposit_request_switching_to_compounding(
        spec,
        state,
        validator_index,
        initial_withdrawal_credentials,
        compounding_credentials,
        effective=False
    )


@with_electra_and_later
@spec_state_test
def test_process_deposit_request_switch_to_compounding_exited_and_active(spec, state):
    validator_index = 0
    initial_withdrawal_credentials = (
        spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX
        + b'\x00' * 11  # specified 0s
        + b'\x59' * 20  # a 20-byte eth1 address
    )
    compounding_credentials = (
        spec.COMPOUNDING_WITHDRAWAL_PREFIX
        + b'\x00' * 11  # specified 0s
        + b'\x59' * 20  # a 20-byte eth1 address
    )

    # Initiate exit
    spec.initiate_validator_exit(state, validator_index)

    yield from _run_deposit_request_switching_to_compounding(
        spec,
        state,
        validator_index,
        initial_withdrawal_credentials,
        compounding_credentials,
        effective=True
    )
