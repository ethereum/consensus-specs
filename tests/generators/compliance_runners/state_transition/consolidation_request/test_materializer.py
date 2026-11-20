"""Checks for consolidation churn when a request validator is inactive."""

from random import Random
from types import SimpleNamespace

from eth_consensus_specs.gloas import minimal as spec
from tests.generators.compliance_runners.state_transition.declaration_coverage import (
    materializer_record,
)
from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import Context
from tests.generators.compliance_runners.state_transition.evaluation.declarations import (
    BoundFormula,
    fix,
)

from .materializer import ConsolidationRequestMaterializer
from .target import TARGET


def _record(**obligation):
    bound = TARGET.for_spec(spec)
    witnesses = BoundFormula(bound, fix(**obligation)).generation_obligations()
    assert len(witnesses) == 1
    return materializer_record(bound, dict(next(iter(witnesses))))


def test_inactive_request_validators_preserve_claimed_churn():
    cases = (
        _record(
            consolidation_churn_to_min_activation="EQ",
            validator_pubkey_found=True,
            validator_active=False,
        ),
        _record(
            consolidation_churn_to_min_activation="EQ",
            validator_pubkey_found=True,
            validator_active=True,
            target_found=True,
            target_active=False,
        ),
    )
    for record in cases:
        materializer = ConsolidationRequestMaterializer(spec)
        materializer.rng = Random(0)
        _, parts = materializer.materialize_solution(SimpleNamespace(**record))
        pre = spec.BeaconState.decode_bytes(parts[0][2])
        request = spec.ConsolidationRequest.decode_bytes(parts[1][2])
        post = spec.BeaconState.decode_bytes(parts[2][2])
        observed = TARGET.record(TARGET.observation(Context(spec, pre, request, post, {})))
        assert observed["consolidation_churn_to_min_activation"] == "EQ"
