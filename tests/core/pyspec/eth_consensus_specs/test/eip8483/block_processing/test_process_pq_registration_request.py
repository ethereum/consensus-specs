from eth_consensus_specs.test.context import spec_state_test, with_phases
from eth_consensus_specs.test.helpers.constants import EIP8483
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
        validator_pubkey=validator.pubkey,
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
        validator_pubkey=pubkeys[len(state.validators)],
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
