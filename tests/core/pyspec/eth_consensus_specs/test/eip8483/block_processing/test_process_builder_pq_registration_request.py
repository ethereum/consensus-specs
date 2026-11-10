from eth_consensus_specs.test.context import spec_state_test, with_phases
from eth_consensus_specs.test.helpers.constants import EIP8483


def prepare_builder_pq_registration_request(
    spec, state, builder_index, pq_data, source_address=None
):
    builder = state.builders[builder_index]
    if source_address is None:
        source_address = builder.execution_address
    return spec.BuilderPQRegistrationRequest(
        source_address=source_address,
        builder_pubkey=builder.pubkey,
        pq_data=pq_data,
    )


def run_builder_pq_registration_request_processing(spec, state, request, valid=True):
    """
    Run ``process_builder_pq_registration_request``, yielding:
      - pre-state ('pre')
      - builder_pq_registration_request ('builder_pq_registration_request')
      - post-state ('post').

    The function never raises. If ``valid`` is False, expect the request to be
    ignored without changing the state.
    """
    pre_state = state.copy()

    yield "pre", state
    yield "builder_pq_registration_request", request

    spec.process_builder_pq_registration_request(state, request)

    yield "post", state

    if not valid:
        assert state == pre_state


@with_phases([EIP8483])
@spec_state_test
def test_process_builder_pq_registration_request__success(spec, state):
    request = prepare_builder_pq_registration_request(spec, state, 0, b"\x22" * 32)

    yield from run_builder_pq_registration_request_processing(spec, state, request)

    assert len(state.builder_pq_registrations) == 1
    assert state.builder_pq_registrations[0].builder_pubkey == state.builders[0].pubkey
    assert state.builder_pq_registrations[0].pq_data == b"\x22" * 32


@with_phases([EIP8483])
@spec_state_test
def test_process_builder_pq_registration_request__overwrites_registration(spec, state):
    spec.process_builder_pq_registration_request(
        state, prepare_builder_pq_registration_request(spec, state, 0, b"\x22" * 32)
    )
    request = prepare_builder_pq_registration_request(spec, state, 0, b"\x33" * 32)

    yield from run_builder_pq_registration_request_processing(spec, state, request)

    assert len(state.builder_pq_registrations) == 1
    assert state.builder_pq_registrations[0].pq_data == b"\x33" * 32


@with_phases([EIP8483])
@spec_state_test
def test_process_builder_pq_registration_request__registrations_for_two_builders(spec, state):
    spec.process_builder_pq_registration_request(
        state, prepare_builder_pq_registration_request(spec, state, 1, b"\x22" * 32)
    )
    request = prepare_builder_pq_registration_request(spec, state, 0, b"\x33" * 32)

    yield from run_builder_pq_registration_request_processing(spec, state, request)

    assert [registration.builder_pubkey for registration in state.builder_pq_registrations] == [
        state.builders[1].pubkey,
        state.builders[0].pubkey,
    ]


@with_phases([EIP8483])
@spec_state_test
def test_process_builder_pq_registration_request__unknown_pubkey(spec, state):
    request = spec.BuilderPQRegistrationRequest(
        source_address=b"\x11" * 20,
        builder_pubkey=state.validators[0].pubkey,
        pq_data=b"\x22" * 32,
    )
    assert request.builder_pubkey not in [builder.pubkey for builder in state.builders]

    yield from run_builder_pq_registration_request_processing(spec, state, request, valid=False)


@with_phases([EIP8483])
@spec_state_test
def test_process_builder_pq_registration_request__wrong_source_address(spec, state):
    request = prepare_builder_pq_registration_request(
        spec, state, 0, b"\x22" * 32, source_address=b"\x99" * 20
    )

    yield from run_builder_pq_registration_request_processing(spec, state, request, valid=False)


@with_phases([EIP8483])
@spec_state_test
def test_process_builder_pq_registration_request__xmss_pubkey_registered_by_builder(spec, state):
    spec.process_builder_pq_registration_request(
        state, prepare_builder_pq_registration_request(spec, state, 0, b"\x22" * 32)
    )
    request = prepare_builder_pq_registration_request(spec, state, 1, b"\x22" * 32)

    yield from run_builder_pq_registration_request_processing(spec, state, request, valid=False)


@with_phases([EIP8483])
@spec_state_test
def test_process_builder_pq_registration_request__xmss_pubkey_registered_by_validator(spec, state):
    state.validator_pq_registrations.append(
        spec.ValidatorPQRegistration(validator_index=0, pq_data=b"\x22" * 32 + b"\x33" * 32)
    )
    request = prepare_builder_pq_registration_request(spec, state, 0, b"\x22" * 32)

    yield from run_builder_pq_registration_request_processing(spec, state, request)

    assert len(state.builder_pq_registrations) == 1


@with_phases([EIP8483])
@spec_state_test
def test_process_builder_pq_registration_request__builder_shares_validator_pubkey(spec, state):
    state.builders[0].pubkey = state.validators[0].pubkey
    state.validator_pq_registrations.append(
        spec.ValidatorPQRegistration(validator_index=0, pq_data=b"\x22" * 64)
    )
    request = prepare_builder_pq_registration_request(spec, state, 0, b"\x33" * 32)

    yield from run_builder_pq_registration_request_processing(spec, state, request)

    assert len(state.validator_pq_registrations) == 1
    assert len(state.builder_pq_registrations) == 1
    assert state.builder_pq_registrations[0].builder_pubkey == state.validators[0].pubkey
