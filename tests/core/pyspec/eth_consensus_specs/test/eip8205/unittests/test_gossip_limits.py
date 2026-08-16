import pytest

from eth_consensus_specs.test.context import (
    single_phase,
    spec_test,
    with_eip8205_and_later,
)


def _requests_with_preregistrations(spec, count):
    return spec.ExecutionRequests(
        preregistrations=spec.PreregistrationRequests([spec.PreregistrationRequest()] * count),
    )


@with_eip8205_and_later
@spec_test
@single_phase
def test_execution_requests_limits_at_preregistration_limit(spec):
    requests = _requests_with_preregistrations(spec, spec.MAX_PREREGISTRATION_REQUESTS_PER_PAYLOAD)

    # At the limit, no exception is raised
    spec.verify_execution_requests_limits(requests)


@with_eip8205_and_later
@spec_test
@single_phase
def test_execution_requests_limits_over_preregistration_limit(spec):
    requests = _requests_with_preregistrations(
        spec, spec.MAX_PREREGISTRATION_REQUESTS_PER_PAYLOAD + 1
    )

    with pytest.raises(spec.GossipReject, match="too many validator preregistration requests"):
        spec.verify_execution_requests_limits(requests)
