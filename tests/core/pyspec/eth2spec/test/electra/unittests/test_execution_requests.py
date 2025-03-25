from eth2spec.test.context import (
    single_phase,
    spec_test,
    with_electra_and_later,
)


@with_electra_and_later
@spec_test
@single_phase
def test_requests_serialization_round_trip__empty(spec):
    execution_requests = spec.ExecutionRequests()
    serialized_execution_requests = spec.get_execution_requests_list(execution_requests)
    deserialized_execution_requests = spec.get_execution_requests(
        serialized_execution_requests
    )
    assert deserialized_execution_requests == execution_requests


@with_electra_and_later
@spec_test
@single_phase
def test_requests_serialization_round_trip__one_request(spec):
    execution_requests = spec.ExecutionRequests(
        deposits=[spec.DepositRequest()],
    )
    serialized_execution_requests = spec.get_execution_requests_list(execution_requests)
    deserialized_execution_requests = spec.get_execution_requests(
        serialized_execution_requests
    )
    assert deserialized_execution_requests == execution_requests


@with_electra_and_later
@spec_test
@single_phase
def test_requests_serialization_round_trip__multiple_requests(spec):
    execution_requests = spec.ExecutionRequests(
        deposits=[spec.DepositRequest()],
        withdrawals=[spec.WithdrawalRequest()],
        consolidations=[spec.ConsolidationRequest()],
    )
    serialized_execution_requests = spec.get_execution_requests_list(execution_requests)
    deserialized_execution_requests = spec.get_execution_requests(
        serialized_execution_requests
    )
    assert deserialized_execution_requests == execution_requests


@with_electra_and_later
@spec_test
@single_phase
def test_requests_serialization_round_trip__one_request_with_real_data(spec):
    execution_requests = spec.ExecutionRequests(
        deposits=[
            spec.DepositRequest(
                pubkey=spec.BLSPubkey(48 * "aa"),
                withdrawal_credentials=spec.Bytes32(32 * "bb"),
                amount=spec.Gwei(11111111),
                signature=spec.BLSSignature(96 * "cc"),
                index=spec.uint64(22222222),
            ),
        ]
    )
    serialized_execution_requests = spec.get_execution_requests_list(execution_requests)
    deserialized_execution_requests = spec.get_execution_requests(
        serialized_execution_requests
    )
    assert deserialized_execution_requests == execution_requests


@with_electra_and_later
@spec_test
@single_phase
def test_requests_deserialize__reject_duplicate_request(spec):
    serialized_withdrawal = 76 * b"\x0a"
    serialized_execution_requests = [
        spec.WITHDRAWAL_REQUEST_TYPE + serialized_withdrawal,
        spec.WITHDRAWAL_REQUEST_TYPE + serialized_withdrawal,
    ]
    try:
        spec.get_execution_requests(serialized_execution_requests)
        assert False, "expected exception"
    except Exception:
        pass


@with_electra_and_later
@spec_test
@single_phase
def test_requests_deserialize__reject_out_of_order_requests(spec):
    serialized_execution_requests = [
        spec.WITHDRAWAL_REQUEST_TYPE + 76 * b"\x0a",
        spec.DEPOSIT_REQUEST_TYPE + 192 * b"\x0b",
    ]
    assert int(serialized_execution_requests[0][0]) > int(
        serialized_execution_requests[1][0]
    )
    try:
        spec.get_execution_requests(serialized_execution_requests)
        assert False, "expected exception"
    except Exception:
        pass


@with_electra_and_later
@spec_test
@single_phase
def test_requests_deserialize__reject_empty_request(spec):
    serialized_execution_requests = [b"\x01"]
    try:
        spec.get_execution_requests(serialized_execution_requests)
        assert False, "expected exception"
    except Exception:
        pass


@with_electra_and_later
@spec_test
@single_phase
def test_requests_deserialize__reject_unexpected_request_type(spec):
    serialized_execution_requests = [
        b"\x03\xff\xff\xff",
    ]
    try:
        spec.get_execution_requests(serialized_execution_requests)
        assert False, "expected exception"
    except Exception:
        pass
