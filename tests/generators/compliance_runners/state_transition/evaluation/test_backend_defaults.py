"""Target backend defaults apply to generation, direct binding, and the CLI."""

from importlib import import_module

import pytest

from eth_consensus_specs.test.helpers.specs import spec_targets
from tests.generators.compliance_runners.state_transition import declaration_coverage
from tests.generators.compliance_runners.state_transition.provider import load_provider

from .backend_config import DEFAULT_BACKEND, DEFAULT_SOLVER
from .coverage_dsl import parse_args, TARGETS

# Measured Python wins on both presets; keep this contract explicit so new
# providers continue to inherit MiniZinc rather than an automatic size cutoff.
PYTHON_PROVIDERS = frozenset(
    {
        "attester_slashing",
        "bls_to_execution_change",
        "builder_deposit_request",
        "builder_exit_request",
        "builder_pending_payments",
        "builder_pending_withdrawal_processing",
        "deposit_request",
        "effective_balance_updates",
        "process_operations_dispatch",
        "pending_consolidations",
        "ptc_window",
        "slashings",
        "sync_aggregate",
    }
)


@pytest.mark.parametrize("name", tuple(TARGETS))
@pytest.mark.parametrize("preset", ["minimal", "mainnet"])
def test_provider_backend_policy(name, preset, monkeypatch):
    target_module = import_module(TARGETS[name])
    provider = load_provider(target_module.__package__.rsplit(".", 1)[1])
    spec = spec_targets[preset]["gloas"]
    expected = "python" if name in PYTHON_PROVIDERS else DEFAULT_BACKEND
    assert DEFAULT_BACKEND == "minizinc"
    assert provider.TARGET.backend == expected
    assert provider.TARGET.for_spec(spec).backend == expected
    assert provider.TARGET.solver == DEFAULT_SOLVER == "gecode"
    cli = parse_args(["--tests", "/tmp/vectors", "--target", name])
    assert (
        provider.TARGET.for_spec(spec, backend=cli.backend, solver=cli.solver).backend == expected
    )

    def inspect(bound, profile):
        assert bound.backend == expected
        assert bound.solver == DEFAULT_SOLVER
        assert bound._bound_spec is spec
        assert profile == "smoke"
        return ["central-default"]

    # Exercise the actual provider adapter without running a solver.
    monkeypatch.setattr(declaration_coverage, "profile_records", inspect)
    assert provider.build_profile("smoke", spec=spec) == ["central-default"]
    for backend in ("python", "minizinc"):
        assert provider.TARGET.for_spec(spec, backend=backend).backend == backend
    assert provider.TARGET.backend == expected


def test_cli_inherits_defaults_and_accepts_python_reference():
    defaults = parse_args(["--tests", "/tmp/vectors"])
    assert (defaults.backend, defaults.solver) == (None, None)
    reference = parse_args(["--tests", "/tmp/vectors", "--backend", "python"])
    assert reference.backend == "python"
