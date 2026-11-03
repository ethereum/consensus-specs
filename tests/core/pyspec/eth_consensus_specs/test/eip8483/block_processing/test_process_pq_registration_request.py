from eth_consensus_specs.test.context import spec_state_test, with_phases
from eth_consensus_specs.test.helpers.constants import EIP8483
from eth_consensus_specs.test.helpers.deposits import prepare_builder_deposit_request
from eth_consensus_specs.test.helpers.keys import pubkeys


def set_execution_withdrawal_address(spec, state, validator_index, address):
    state.validators[validator_index].withdrawal_credentials = (
        spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX + b"\x00" * 11 + address
    )


def prepare_pq_registration_request(spec, state, validator_index, pq_data, source_address=None):
    validator = state.validators[validator_index]
    if source_address is None:
        source_address = validator.withdrawal_credentials[12:]
    return spec.PQRegistrationRequest(
        source_address=source_address,
        role=spec.PQ_REGISTRATION_ROLE_VALIDATOR,
        pubkey=validator.pubkey,
        pq_data=pq_data,
    )


def run_pq_registration_request_processing(spec, state, pq_registration_request, valid=True):
    """
    Run ``process_pq_registration_request``, yielding:
      - pre-state ('pre')
      - pq_registration_request ('pq_registration_request')
      - post-state ('post').

    The function never raises. If ``valid`` is False, expect the request to be
    ignored without changing the state.
    """
    pre_state = state.copy()

    yield "pre", state
    yield "pq_registration_request", pq_registration_request

    spec.process_pq_registration_request(state, pq_registration_request)

    yield "post", state

    if not valid:
        assert state == pre_state


@with_phases([EIP8483])
@spec_state_test
def test_process_pq_registration_request__success(spec, state):
    set_execution_withdrawal_address(spec, state, 0, b"\x11" * 20)
    request = prepare_pq_registration_request(spec, state, 0, b"\x22" * 32)

    yield from run_pq_registration_request_processing(spec, state, request)

    assert len(state.pq_registrations) == 1
    assert state.pq_registrations[0].validator_index == 0
    assert state.pq_registrations[0].pq_data == b"\x22" * 32


@with_phases([EIP8483])
@spec_state_test
def test_process_pq_registration_request__compounding_credentials(spec, state):
    state.validators[0].withdrawal_credentials = (
        spec.COMPOUNDING_WITHDRAWAL_PREFIX + b"\x00" * 11 + b"\x11" * 20
    )
    request = prepare_pq_registration_request(spec, state, 0, b"\x22" * 32)

    yield from run_pq_registration_request_processing(spec, state, request)

    assert len(state.pq_registrations) == 1
    assert state.pq_registrations[0].validator_index == 0


@with_phases([EIP8483])
@spec_state_test
def test_process_pq_registration_request__overwrites_registration(spec, state):
    set_execution_withdrawal_address(spec, state, 0, b"\x11" * 20)
    spec.process_pq_registration_request(
        state, prepare_pq_registration_request(spec, state, 0, b"\x22" * 32)
    )
    request = prepare_pq_registration_request(spec, state, 0, b"\x33" * 32)

    yield from run_pq_registration_request_processing(spec, state, request)

    assert len(state.pq_registrations) == 1
    assert state.pq_registrations[0].pq_data == b"\x33" * 32


@with_phases([EIP8483])
@spec_state_test
def test_process_pq_registration_request__registrations_for_two_validators(spec, state):
    set_execution_withdrawal_address(spec, state, 0, b"\x11" * 20)
    set_execution_withdrawal_address(spec, state, 1, b"\x11" * 20)
    spec.process_pq_registration_request(
        state, prepare_pq_registration_request(spec, state, 1, b"\x22" * 32)
    )
    request = prepare_pq_registration_request(spec, state, 0, b"\x33" * 32)

    yield from run_pq_registration_request_processing(spec, state, request)

    assert [registration.validator_index for registration in state.pq_registrations] == [1, 0]


@with_phases([EIP8483])
@spec_state_test
def test_process_pq_registration_request__exited_validator(spec, state):
    set_execution_withdrawal_address(spec, state, 0, b"\x11" * 20)
    spec.initiate_validator_exit(state, 0)
    request = prepare_pq_registration_request(spec, state, 0, b"\x22" * 32)

    yield from run_pq_registration_request_processing(spec, state, request)

    assert len(state.pq_registrations) == 1


@with_phases([EIP8483])
@spec_state_test
def test_process_pq_registration_request__unknown_pubkey(spec, state):
    request = spec.PQRegistrationRequest(
        source_address=b"\x11" * 20,
        role=spec.PQ_REGISTRATION_ROLE_VALIDATOR,
        pubkey=pubkeys[len(state.validators)],
        pq_data=b"\x22" * 32,
    )

    yield from run_pq_registration_request_processing(spec, state, request, valid=False)


@with_phases([EIP8483])
@spec_state_test
def test_process_pq_registration_request__bls_withdrawal_credentials(spec, state):
    state.validators[0].withdrawal_credentials = (
        spec.BLS_WITHDRAWAL_PREFIX + spec.sha256(state.validators[0].pubkey)[1:]
    )
    request = prepare_pq_registration_request(
        spec, state, 0, b"\x22" * 32, source_address=b"\x11" * 20
    )

    yield from run_pq_registration_request_processing(spec, state, request, valid=False)


@with_phases([EIP8483])
@spec_state_test
def test_process_pq_registration_request__wrong_source_address(spec, state):
    set_execution_withdrawal_address(spec, state, 0, b"\x11" * 20)
    request = prepare_pq_registration_request(
        spec, state, 0, b"\x22" * 32, source_address=b"\x44" * 20
    )

    yield from run_pq_registration_request_processing(spec, state, request, valid=False)


def prepare_builder_pq_registration_request(
    spec, state, builder_index, pq_data, source_address=None
):
    builder = state.builders[builder_index]
    if source_address is None:
        source_address = builder.execution_address
    return spec.PQRegistrationRequest(
        source_address=source_address,
        role=spec.PQ_REGISTRATION_ROLE_BUILDER,
        pubkey=builder.pubkey,
        pq_data=pq_data,
    )


@with_phases([EIP8483])
@spec_state_test
def test_process_pq_registration_request__unknown_role(spec, state):
    set_execution_withdrawal_address(spec, state, 0, b"\x11" * 20)
    request = prepare_pq_registration_request(spec, state, 0, b"\x22" * 32)
    request.role = 2

    yield from run_pq_registration_request_processing(spec, state, request, valid=False)


@with_phases([EIP8483])
@spec_state_test
def test_process_pq_registration_request__builder_success(spec, state):
    request = prepare_builder_pq_registration_request(spec, state, 0, b"\x22" * 32)

    yield from run_pq_registration_request_processing(spec, state, request)

    assert len(state.pq_registrations) == 1
    registration = state.pq_registrations[0]
    assert registration.validator_index == spec.convert_builder_index_to_validator_index(0)
    assert registration.pq_data == b"\x22" * 32


@with_phases([EIP8483])
@spec_state_test
def test_process_pq_registration_request__builder_and_validator(spec, state):
    set_execution_withdrawal_address(spec, state, 0, b"\x11" * 20)
    spec.process_pq_registration_request(
        state, prepare_pq_registration_request(spec, state, 0, b"\x22" * 32)
    )
    request = prepare_builder_pq_registration_request(spec, state, 0, b"\x33" * 32)

    yield from run_pq_registration_request_processing(spec, state, request)

    assert [registration.validator_index for registration in state.pq_registrations] == [
        0,
        spec.convert_builder_index_to_validator_index(0),
    ]


@with_phases([EIP8483])
@spec_state_test
def test_process_pq_registration_request__builder_overwrites_registration(spec, state):
    spec.process_pq_registration_request(
        state, prepare_builder_pq_registration_request(spec, state, 0, b"\x22" * 32)
    )
    request = prepare_builder_pq_registration_request(spec, state, 0, b"\x33" * 32)

    yield from run_pq_registration_request_processing(spec, state, request)

    assert len(state.pq_registrations) == 1
    assert state.pq_registrations[0].pq_data == b"\x33" * 32


@with_phases([EIP8483])
@spec_state_test
def test_process_pq_registration_request__builder_pubkey_with_validator_role(spec, state):
    request = prepare_builder_pq_registration_request(spec, state, 0, b"\x22" * 32)
    request.role = spec.PQ_REGISTRATION_ROLE_VALIDATOR

    yield from run_pq_registration_request_processing(spec, state, request, valid=False)


@with_phases([EIP8483])
@spec_state_test
def test_process_pq_registration_request__builder_wrong_source_address(spec, state):
    request = prepare_builder_pq_registration_request(
        spec, state, 0, b"\x22" * 32, source_address=b"\x44" * 20
    )

    yield from run_pq_registration_request_processing(spec, state, request, valid=False)


@with_phases([EIP8483])
@spec_state_test
def test_process_pq_registration_request__reused_builder_index_clears_registration(spec, state):
    spec.process_pq_registration_request(
        state, prepare_builder_pq_registration_request(spec, state, 0, b"\x22" * 32)
    )
    assert len(state.pq_registrations) == 1

    # Builder 0 has exited and been swept, so a new builder takes its index
    state.builders[0].withdrawable_epoch = spec.get_current_epoch(state)
    state.builders[0].balance = 0
    request = prepare_builder_deposit_request(spec, state, spec.MIN_DEPOSIT_AMOUNT, signed=True)

    yield "pre", state
    yield "builder_deposit_request", request

    spec.process_builder_deposit_request(state, request)

    yield "post", state

    assert state.builders[0].pubkey == request.pubkey
    assert len(state.pq_registrations) == 0
