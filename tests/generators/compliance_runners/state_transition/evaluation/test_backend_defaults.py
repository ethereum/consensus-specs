"""TARGET providers and the scoring CLI inherit one backend policy."""

from importlib import import_module

import pytest

from eth_consensus_specs.test.helpers.specs import spec_targets
from tests.generators.compliance_runners.state_transition import declaration_coverage

from .backend_config import DEFAULT_BACKEND, DEFAULT_SOLVER
from .coverage_dsl import parse_args, TARGETS


@pytest.mark.parametrize("name", tuple(TARGETS))
def test_provider_inherits_central_defaults(name, monkeypatch):
    target_module = import_module(TARGETS[name])
    provider = import_module(target_module.__package__)
    spec = spec_targets["minimal"]["gloas"]
    assert provider.TARGET.backend == DEFAULT_BACKEND == "minizinc"
    assert provider.TARGET.solver == DEFAULT_SOLVER == "gecode"

    def inspect(bound, profile):
        assert bound.backend == "minizinc"
        assert bound.solver == DEFAULT_SOLVER
        assert bound._bound_spec is spec
        assert profile == "smoke"
        return ["central-default"]

    # Exercise the actual provider adapter without running a solver.
    monkeypatch.setattr(declaration_coverage, "profile_records", inspect)
    assert provider.build_profile("smoke", spec=spec) == ["central-default"]
    reference = provider.TARGET.for_spec(spec, backend="python")
    assert reference.backend == "python"
    assert provider.TARGET.backend == "minizinc"


def test_cli_inherits_defaults_and_accepts_python_reference():
    defaults = parse_args(["--tests", "/tmp/vectors"])
    assert (defaults.backend, defaults.solver) == (DEFAULT_BACKEND, DEFAULT_SOLVER)
    reference = parse_args(["--tests", "/tmp/vectors", "--backend", "python"])
    assert reference.backend == "python"
