from eth_consensus_specs.test.context import spec_state_test, with_phases
from eth_consensus_specs.test.helpers.constants import EIP8483
from eth_consensus_specs.test.helpers.keys import pubkeys


def set_execution_withdrawal_address(spec, state, validator_index, address):
    state.validators[validator_index].withdrawal_credentials = (
        spec.ETH1_ADDRESS_WITHDRAWAL_PREFIX + b"\x00" * 11 + address
    )


def prepare_validator_pq_registration_request(
    spec, state, validator_index, pq_data, source_address=None
):
    validator = state.validators[validator_index]
    if source_address is None:
        source_address = validator.withdrawal_credentials[12:]
    return spec.ValidatorPQRegistrationRequest(
        source_address=source_address,
        validator_pubkey=validator.pubkey,
        pq_data=pq_data,
    )


def run_validator_pq_registration_request_processing(spec, state, request, valid=True):
    """
    Run ``process_validator_pq_registration_request``, yielding:
      - pre-state ('pre')
      - validator_pq_registration_request ('validator_pq_registration_request')
      - post-state ('post').

    The function never raises. If ``valid`` is False, expect the request to be
    ignored without changing the state.
    """
    pre_state = state.copy()

    yield "pre", state
    yield "validator_pq_registration_request", request

    spec.process_validator_pq_registration_request(state, request)

    yield "post", state

    if not valid:
        assert state == pre_state


@with_phases([EIP8483])
@spec_state_test
def test_process_validator_pq_registration_request__success(spec, state):
    set_execution_withdrawal_address(spec, state, 0, b"\x11" * 20)
    request = prepare_validator_pq_registration_request(spec, state, 0, b"\x22" * 64)

    yield from run_validator_pq_registration_request_processing(spec, state, request)

    assert len(state.validator_pq_registrations) == 1
    assert state.validator_pq_registrations[0].validator_index == 0
    assert state.validator_pq_registrations[0].pq_data == b"\x22" * 64


@with_phases([EIP8483])
@spec_state_test
def test_process_validator_pq_registration_request__compounding_credentials(spec, state):
    state.validators[0].withdrawal_credentials = (
        spec.COMPOUNDING_WITHDRAWAL_PREFIX + b"\x00" * 11 + b"\x11" * 20
    )
    request = prepare_validator_pq_registration_request(spec, state, 0, b"\x22" * 64)

    yield from run_validator_pq_registration_request_processing(spec, state, request)

    assert len(state.validator_pq_registrations) == 1
    assert state.validator_pq_registrations[0].validator_index == 0


@with_phases([EIP8483])
@spec_state_test
def test_process_validator_pq_registration_request__overwrites_registration(spec, state):
    set_execution_withdrawal_address(spec, state, 0, b"\x11" * 20)
    spec.process_validator_pq_registration_request(
        state, prepare_validator_pq_registration_request(spec, state, 0, b"\x22" * 64)
    )
    request = prepare_validator_pq_registration_request(spec, state, 0, b"\x33" * 64)

    yield from run_validator_pq_registration_request_processing(spec, state, request)

    assert len(state.validator_pq_registrations) == 1
    assert state.validator_pq_registrations[0].pq_data == b"\x33" * 64


@with_phases([EIP8483])
@spec_state_test
def test_process_validator_pq_registration_request__registrations_for_two_validators(spec, state):
    set_execution_withdrawal_address(spec, state, 0, b"\x11" * 20)
    set_execution_withdrawal_address(spec, state, 1, b"\x11" * 20)
    spec.process_validator_pq_registration_request(
        state, prepare_validator_pq_registration_request(spec, state, 1, b"\x22" * 64)
    )
    request = prepare_validator_pq_registration_request(spec, state, 0, b"\x33" * 64)

    yield from run_validator_pq_registration_request_processing(spec, state, request)

    assert [registration.validator_index for registration in state.validator_pq_registrations] == [
        1,
        0,
    ]


@with_phases([EIP8483])
@spec_state_test
def test_process_validator_pq_registration_request__exited_validator(spec, state):
    set_execution_withdrawal_address(spec, state, 0, b"\x11" * 20)
    spec.initiate_validator_exit(state, 0)
    request = prepare_validator_pq_registration_request(spec, state, 0, b"\x22" * 64)

    yield from run_validator_pq_registration_request_processing(spec, state, request)

    assert len(state.validator_pq_registrations) == 1


@with_phases([EIP8483])
@spec_state_test
def test_process_validator_pq_registration_request__unknown_pubkey(spec, state):
    request = spec.ValidatorPQRegistrationRequest(
        source_address=b"\x11" * 20,
        validator_pubkey=pubkeys[len(state.validators)],
        pq_data=b"\x22" * 64,
    )

    yield from run_validator_pq_registration_request_processing(spec, state, request, valid=False)


@with_phases([EIP8483])
@spec_state_test
def test_process_validator_pq_registration_request__bls_withdrawal_credentials(spec, state):
    state.validators[0].withdrawal_credentials = (
        spec.BLS_WITHDRAWAL_PREFIX + spec.sha256(state.validators[0].pubkey)[1:]
    )
    request = prepare_validator_pq_registration_request(
        spec, state, 0, b"\x22" * 64, source_address=b"\x11" * 20
    )

    yield from run_validator_pq_registration_request_processing(spec, state, request, valid=False)


@with_phases([EIP8483])
@spec_state_test
def test_process_validator_pq_registration_request__wrong_source_address(spec, state):
    set_execution_withdrawal_address(spec, state, 0, b"\x11" * 20)
    request = prepare_validator_pq_registration_request(
        spec, state, 0, b"\x22" * 64, source_address=b"\x44" * 20
    )

    yield from run_validator_pq_registration_request_processing(spec, state, request, valid=False)


@with_phases([EIP8483])
@spec_state_test
def test_process_validator_pq_registration_request__pq_data_already_registered(spec, state):
    set_execution_withdrawal_address(spec, state, 0, b"\x11" * 20)
    set_execution_withdrawal_address(spec, state, 1, b"\x44" * 20)
    spec.process_validator_pq_registration_request(
        state, prepare_validator_pq_registration_request(spec, state, 0, b"\x22" * 64)
    )
    request = prepare_validator_pq_registration_request(spec, state, 1, b"\x22" * 64)

    yield from run_validator_pq_registration_request_processing(spec, state, request, valid=False)


@with_phases([EIP8483])
@spec_state_test
def test_process_validator_pq_registration_request__resubmitted_registration(spec, state):
    set_execution_withdrawal_address(spec, state, 0, b"\x11" * 20)
    spec.process_validator_pq_registration_request(
        state, prepare_validator_pq_registration_request(spec, state, 0, b"\x22" * 64)
    )
    request = prepare_validator_pq_registration_request(spec, state, 0, b"\x22" * 64)

    yield from run_validator_pq_registration_request_processing(spec, state, request, valid=False)


@with_phases([EIP8483])
@spec_state_test
def test_process_validator_pq_registration_request__overwritten_pq_data_can_be_registered(
    spec, state
):
    set_execution_withdrawal_address(spec, state, 0, b"\x11" * 20)
    set_execution_withdrawal_address(spec, state, 1, b"\x44" * 20)
    spec.process_validator_pq_registration_request(
        state, prepare_validator_pq_registration_request(spec, state, 0, b"\x22" * 64)
    )
    spec.process_validator_pq_registration_request(
        state, prepare_validator_pq_registration_request(spec, state, 0, b"\x33" * 64)
    )
    request = prepare_validator_pq_registration_request(spec, state, 1, b"\x22" * 64)

    yield from run_validator_pq_registration_request_processing(spec, state, request)

    assert [
        (registration.validator_index, registration.pq_data)
        for registration in state.validator_pq_registrations
    ] == [
        (0, b"\x33" * 64),
        (1, b"\x22" * 64),
    ]


@with_phases([EIP8483])
@spec_state_test
def test_process_validator_pq_registration_request__xmss_pubkey_already_registered(spec, state):
    set_execution_withdrawal_address(spec, state, 0, b"\x11" * 20)
    set_execution_withdrawal_address(spec, state, 1, b"\x44" * 20)
    spec.process_validator_pq_registration_request(
        state, prepare_validator_pq_registration_request(spec, state, 0, b"\x22" * 64)
    )
    # Same XMSS public key, different VRF root
    request = prepare_validator_pq_registration_request(spec, state, 1, b"\x22" * 32 + b"\x33" * 32)

    yield from run_validator_pq_registration_request_processing(spec, state, request, valid=False)


@with_phases([EIP8483])
@spec_state_test
def test_process_validator_pq_registration_request__vrf_root_already_registered(spec, state):
    set_execution_withdrawal_address(spec, state, 0, b"\x11" * 20)
    set_execution_withdrawal_address(spec, state, 1, b"\x44" * 20)
    spec.process_validator_pq_registration_request(
        state,
        prepare_validator_pq_registration_request(spec, state, 0, b"\x22" * 32 + b"\x55" * 32),
    )
    # Different XMSS public key, same VRF root
    request = prepare_validator_pq_registration_request(spec, state, 1, b"\x33" * 32 + b"\x55" * 32)

    yield from run_validator_pq_registration_request_processing(spec, state, request, valid=False)


@with_phases([EIP8483])
@spec_state_test
def test_process_validator_pq_registration_request__builder_pubkey(spec, state):
    builder = state.builders[0]
    assert builder.pubkey not in [validator.pubkey for validator in state.validators]
    request = spec.ValidatorPQRegistrationRequest(
        source_address=builder.execution_address,
        validator_pubkey=builder.pubkey,
        pq_data=b"\x22" * 64,
    )

    yield from run_validator_pq_registration_request_processing(spec, state, request, valid=False)


@with_phases([EIP8483])
@spec_state_test
def test_process_validator_pq_registration_request__xmss_pubkey_registered_by_builder(spec, state):
    set_execution_withdrawal_address(spec, state, 0, b"\x11" * 20)
    state.builder_pq_registrations.append(
        spec.BuilderPQRegistration(builder_pubkey=state.builders[0].pubkey, pq_data=b"\x22" * 32)
    )
    request = prepare_validator_pq_registration_request(spec, state, 0, b"\x22" * 32 + b"\x33" * 32)

    yield from run_validator_pq_registration_request_processing(spec, state, request)

    assert len(state.validator_pq_registrations) == 1
