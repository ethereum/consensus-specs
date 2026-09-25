"""Regression checks for empty registry-update obligations."""

from types import SimpleNamespace

from eth_consensus_specs.gloas import minimal as spec
from tests.generators.compliance_runners.state_transition.evaluation.coverage_dsl import Context

from .materializer import RegistryUpdatesMaterializer
from .target import TARGET


def _observed(**obligation):
    materializer = RegistryUpdatesMaterializer(spec)
    _, parts = materializer.materialize_solution(SimpleNamespace(**obligation))
    pre = spec.BeaconState.decode_bytes(parts[0][2])
    post = spec.BeaconState.decode_bytes(parts[1][2])
    return TARGET.record(TARGET.observation(Context(spec, pre, None, post, {})), "predicate")


def test_empty_set_with_unchanged_branch_excluded():
    observed = _observed(has_validators=False, leaves_validator_unchanged=False)
    assert observed["has_validators"] is False
    assert observed["leaves_validator_unchanged"] is False


def test_all_branches_excluded_implies_empty_set():
    observed = _observed(
        queues_validator=False,
        ejects_validator=False,
        activates_validator=False,
        leaves_validator_unchanged=False,
    )
    assert observed["has_validators"] is False
    assert not any(
        observed[name]
        for name in (
            "queues_validator",
            "ejects_validator",
            "activates_validator",
            "leaves_validator_unchanged",
        )
    )
