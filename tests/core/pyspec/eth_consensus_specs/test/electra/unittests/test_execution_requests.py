from eth_consensus_specs.test.context import (
    expect_assertion_error,
    single_phase,
    spec_test,
    with_all_phases_from_except,
    with_electra_and_later,
)
from eth_consensus_specs.test.helpers.constants import ELECTRA, PQ
from eth_consensus_specs.test.helpers.keys import get_filled_pubkey
from eth_consensus_specs.test.helpers.signatures import get_filled_signature


@with_electra_and_later
@spec_test
@single_phase
def test_requests_serialization_round_trip__empty(spec):
    execution_requests = spec.ExecutionRequests()
    serialized_execution_requests = spec.get_execution_requests_list(execution_requests)
    deserialized_execution_requests = spec.get_execution_requests(serialized_execution_requests)
    assert deserialized_execution_requests == execution_requests


@with_electra_and_later
@spec_test
@single_phase
def test_requests_serialization_round_trip__one_request(spec):
    execution_requests = spec.ExecutionRequests(
        deposits=spec.DepositRequests.of(spec.DepositRequest()),
    )
    serialized_execution_requests = spec.get_execution_requests_list(execution_requests)
    deserialized_execution_requests = spec.get_execution_requests(serialized_execution_requests)
    assert deserialized_execution_requests == execution_requests


@with_all_phases_from_except(ELECTRA, [PQ])
@spec_test
@single_phase
def test_requests_serialization_round_trip__multiple_requests(spec):
    execution_requests = spec.ExecutionRequests(
        deposits=spec.DepositRequests.of(spec.DepositRequest()),
        withdrawals=spec.WithdrawalRequests.of(spec.WithdrawalRequest()),
        consolidations=spec.ConsolidationRequests.of(spec.ConsolidationRequest()),
    )
    serialized_execution_requests = spec.get_execution_requests_list(execution_requests)
    deserialized_execution_requests = spec.get_execution_requests(serialized_execution_requests)
    assert deserialized_execution_requests == execution_requests


@with_electra_and_later
@spec_test
@single_phase
def test_requests_serialization_round_trip__one_request_with_real_data(spec):
    execution_requests = spec.ExecutionRequests(
        deposits=spec.DepositRequests.of(
            spec.DepositRequest(
                pubkey=get_filled_pubkey(spec, b"\xaa"),
                withdrawal_credentials=spec.Bytes32(32 * "bb"),
                amount=spec.Gwei(11111111),
                signature=get_filled_signature(spec, b"\xcc"),
                index=spec.Uint64(22222222),
            )
        )
    )
    serialized_execution_requests = spec.get_execution_requests_list(execution_requests)
    deserialized_execution_requests = spec.get_execution_requests(serialized_execution_requests)
    assert deserialized_execution_requests == execution_requests


@with_electra_and_later
@spec_test
@single_phase
def test_requests_deserialize__reject_duplicate_request(spec):
    serialized_withdrawal = spec.WithdrawalRequest.get_byte_length() * b"\x0a"
    serialized_execution_requests = [
        spec.WITHDRAWAL_REQUEST_TYPE + serialized_withdrawal,
        spec.WITHDRAWAL_REQUEST_TYPE + serialized_withdrawal,
    ]
    expect_assertion_error(lambda: spec.get_execution_requests(serialized_execution_requests))


@with_electra_and_later
@spec_test
@single_phase
def test_requests_deserialize__reject_out_of_order_requests(spec):
    serialized_execution_requests = [
        spec.WITHDRAWAL_REQUEST_TYPE + spec.WithdrawalRequest.get_byte_length() * b"\x0a",
        spec.DEPOSIT_REQUEST_TYPE + spec.DepositRequest.get_byte_length() * b"\x0b",
    ]
    assert int(serialized_execution_requests[0][0]) > int(serialized_execution_requests[1][0])
    expect_assertion_error(lambda: spec.get_execution_requests(serialized_execution_requests))


@with_electra_and_later
@spec_test
@single_phase
def test_requests_deserialize__reject_empty_request(spec):
    serialized_execution_requests = [b"\x01"]
    expect_assertion_error(lambda: spec.get_execution_requests(serialized_execution_requests))


@with_electra_and_later
@spec_test
@single_phase
def test_requests_deserialize__reject_unexpected_request_type(spec):
    serialized_execution_requests = [
        b"\xff\xff\xff\xff",
    ]
    expect_assertion_error(lambda: spec.get_execution_requests(serialized_execution_requests))
