"""Public state-transition generation profile checks."""

from types import SimpleNamespace

import pytest

from tests.generators.compliance_runners.state_transition.provider import load_provider

from . import provider as runner
from .provider import materialize_handler, PROFILES, PROVIDERS


def test_all_is_not_a_generation_profile(tmp_path):
    assert "all" not in PROFILES
    assert "max" in PROFILES
    with pytest.raises(ValueError, match="unknown profile: all"):
        materialize_handler("blocks", "all", tmp_path)


def test_catalog_providers_expose_all_public_profiles():
    required = {"smoke", "normal", "standard", "max"}
    for provider in PROVIDERS:
        module = load_provider(provider.name)
        assert module.MATERIALIZER.runner_name == provider.runner, provider.name
        assert module.MATERIALIZER.handler_name == provider.handler, provider.name
        assert module.TARGET is load_provider(provider.module).TARGET
        assert callable(module.build_profile), provider.name
        profiles = set(module.TARGET.profiles)
        assert required <= profiles, provider.name
        if "exceptional" not in profiles:
            assert module.build_profile("exceptional", spec=object()) == [], provider.name


def test_shared_withdrawals_materializer_keeps_distinct_targets():
    pending = load_provider("builder_pending_withdrawal_processing")
    aggregate = load_provider("withdrawal_processing")
    assert pending.MATERIALIZER is aggregate.MATERIALIZER
    assert pending.TARGET is not aggregate.TARGET
    assert pending.TARGET.backend == "python"
    assert aggregate.TARGET.backend == "minizinc"


def test_unknown_provider_fails_explicitly():
    with pytest.raises(ValueError, match="unknown provider: missing"):
        load_provider("missing")


def test_materialization_runner_consumes_case_lists(monkeypatch, tmp_path):
    selected_spec = object()
    cases = [{"value": 1}, {"value": 2}]

    def build(name, *, spec):
        assert name == "smoke"
        assert spec is selected_spec
        return cases

    class Materializer:
        runner_name = "epoch_processing"
        handler_name = "example"
        fork_name = "gloas"

        def __init__(self, spec, **kwargs):
            assert spec is selected_spec
            assert kwargs == {"preset_name": "minimal", "seed": 124}

        def materialize_reps(self, directory, representatives, **kwargs):
            assert directory == tmp_path
            assert [vars(r) for r in representatives] == cases
            assert kwargs == {"case_offset": 7, "clean": False}
            return len(representatives)

    module = SimpleNamespace(
        build_profile=build,
        MATERIALIZER=Materializer,
        validate_case=object(),
    )
    monkeypatch.setattr(runner, "load_provider", lambda *args: module)
    provider = runner.Provider("example", "example", "epoch_processing", "example")
    assert runner._materialize_provider(
        provider,
        "smoke",
        tmp_path,
        7,
        clean=False,
        spec=selected_spec,
        preset_name="minimal",
        seed=124,
    ) == (module.validate_case, 2, "gloas")
