from eth_consensus_specs.test.context import (
    single_phase,
    spec_test,
    with_eip8148_and_later,
)


@with_eip8148_and_later
@spec_test
@single_phase
def test_requests_serialization_round_trip__sweep_thresholds(spec):
    execution_requests = spec.ExecutionRequests(
        sweep_thresholds=spec.SweepThresholdRequests(
            [
                spec.SetSweepThresholdRequest(
                    source_address=spec.ExecutionAddress(b"\x11" * 20),
                    validator_pubkey=spec.BLSPubkey(b"\x22" * 48),
                    threshold=spec.Gwei(64_000_000_000),
                )
            ]
        ),
    )

    serialized_execution_requests = spec.get_execution_requests_list(execution_requests)
    deserialized_execution_requests = spec.get_execution_requests(serialized_execution_requests)

    assert deserialized_execution_requests == execution_requests
