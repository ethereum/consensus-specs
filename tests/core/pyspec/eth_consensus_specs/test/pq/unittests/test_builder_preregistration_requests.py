from eth_consensus_specs.test.context import single_phase, spec_test, with_phases
from eth_consensus_specs.test.helpers.constants import PQ


@with_phases([PQ])
@spec_test
@single_phase
def test_builder_preregistration_requests_serialization_round_trip(spec):
    requests = spec.ExecutionRequests(
        validator_preregistrations=spec.ValidatorPreregistrationRequests(
            data=[spec.ValidatorPreregistrationRequest()]
        ),
        builder_preregistrations=spec.BuilderPreregistrationRequests(
            data=[spec.BuilderPreregistrationRequest()]
        ),
        voluntary_exits=spec.VoluntaryExitRequests(data=[spec.VoluntaryExitRequest()]),
    )

    serialized = spec.get_execution_requests_list(requests)

    assert [request[0:1] for request in serialized] == [
        spec.VALIDATOR_PREREGISTRATION_REQUEST_TYPE,
        spec.BUILDER_PREREGISTRATION_REQUEST_TYPE,
        spec.VOLUNTARY_EXIT_REQUEST_TYPE,
    ]
    assert spec.get_execution_requests(serialized) == requests
