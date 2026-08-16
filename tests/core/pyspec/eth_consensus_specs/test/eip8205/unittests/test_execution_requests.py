from eth_consensus_specs.test.context import (
    expect_assertion_error,
    single_phase,
    spec_test,
    with_eip8205_and_later,
)


def _sample_preregistration_request(spec):
    return spec.PreregistrationRequest(
        pubkey=spec.BLSPubkey(b"\x22" * 48),
        withdrawal_credentials=spec.Bytes32(b"\x33" * 32),
        signature=spec.BLSSignature(b"\x44" * 96),
    )


@with_eip8205_and_later
@spec_test
@single_phase
def test_requests_serialization_round_trip__preregistrations(spec):
    request = _sample_preregistration_request(spec)
    execution_requests = spec.ExecutionRequests(
        preregistrations=spec.PreregistrationRequests([request]),
    )

    serialized_execution_requests = spec.get_execution_requests_list(execution_requests)
    deserialized_execution_requests = spec.get_execution_requests(serialized_execution_requests)

    expected_request_data = (
        bytes(request.pubkey) + bytes(request.withdrawal_credentials) + bytes(request.signature)
    )
    assert spec.PreregistrationRequest.is_fixed_byte_length()
    assert spec.PreregistrationRequest.type_byte_length() == 176
    assert request.encode_bytes() == expected_request_data
    assert serialized_execution_requests == [
        spec.PREREGISTRATION_REQUEST_TYPE + expected_request_data
    ]
    assert deserialized_execution_requests == execution_requests


@with_eip8205_and_later
@spec_test
@single_phase
def test_requests_serialization_empty_preregistrations_omitted(spec):
    # EIP-7685 omits empty request objects: an empty preregistrations list must
    # not produce a serialized entry
    execution_requests = spec.ExecutionRequests(
        deposits=spec.DepositRequests([spec.DepositRequest()]),
    )

    serialized_execution_requests = spec.get_execution_requests_list(execution_requests)

    assert len(serialized_execution_requests) == 1
    assert serialized_execution_requests[0][0:1] == spec.DEPOSIT_REQUEST_TYPE

    # A fully empty container serializes to an empty list
    assert spec.get_execution_requests_list(spec.ExecutionRequests()) == []


@with_eip8205_and_later
@spec_test
@single_phase
def test_requests_deserialization_rejects_wrong_order(spec):
    # The preregistration entry must come after all other request types
    preregistration_entry = spec.get_execution_requests_list(
        spec.ExecutionRequests(
            preregistrations=spec.PreregistrationRequests([_sample_preregistration_request(spec)]),
        )
    )
    builder_exit_entry = spec.get_execution_requests_list(
        spec.ExecutionRequests(
            builder_exits=spec.BuilderExitRequests([spec.BuilderExitRequest()]),
        )
    )

    wrong_order = preregistration_entry + builder_exit_entry
    expect_assertion_error(lambda: spec.get_execution_requests(wrong_order))

    right_order = builder_exit_entry + preregistration_entry
    deserialized = spec.get_execution_requests(right_order)
    assert len(deserialized.preregistrations) == 1
    assert len(deserialized.builder_exits) == 1
