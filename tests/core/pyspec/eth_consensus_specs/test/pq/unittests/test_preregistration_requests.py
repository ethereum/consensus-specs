from eth_consensus_specs.test.context import single_phase, spec_test, with_phases
from eth_consensus_specs.test.helpers.constants import PQ


@with_phases([PQ])
@spec_test
@single_phase
def test_preregistration_requests_serialization_round_trip(spec):
    requests = spec.ExecutionRequests(
        builder_exits=spec.BuilderExitRequests(data=[spec.BuilderExitRequest()]),
        preregistrations=spec.PreregistrationRequests(data=[spec.PreregistrationRequest()]),
    )

    serialized = spec.get_execution_requests_list(requests)

    assert [request[0:1] for request in serialized] == [
        spec.BUILDER_EXIT_REQUEST_TYPE,
        spec.PREREGISTRATION_REQUEST_TYPE,
    ]
    assert spec.get_execution_requests(serialized) == requests
