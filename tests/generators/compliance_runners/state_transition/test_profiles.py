"""Public state-transition generation profile checks."""

from types import SimpleNamespace

import pytest

from eth_consensus_specs.test.context import get_copy_of_spec
from eth_consensus_specs.test.helpers.specs import spec_targets
from eth_consensus_specs.utils import bls
from tests.generators.compliance_runners.runner import state_transition as replay
from tests.generators.compliance_runners.runner.discovery import gather_tests
from tests.generators.compliance_runners.runner.io import read_yaml
from tests.generators.compliance_runners.state_transition import provider as runner
from tests.generators.compliance_runners.state_transition.provider import (
    load_provider,
    materialize_handler,
    PROFILES,
    PROVIDERS,
)
from tests.generators.compliance_runners.state_transition.validation_helpers import bls_enabled


@pytest.mark.parametrize("case_handler", ["blocks", "payload_attestation"])
def test_generation_with_fork_config_replays_all_cases(tmp_path, monkeypatch, case_handler):
    assert case_handler in runner.HANDLERS
    spec = spec_targets["minimal"]["gloas"]
    original_config = spec.config
    monkeypatch.setattr(bls, "bls_active", False)
    count = materialize_handler(case_handler, "max", tmp_path, spec=spec)
    cases = list(gather_tests(tmp_path, kind="state_transition"))
    assert len(cases) == count > 0
    for case in cases:
        if case_handler == "blocks":
            assert read_yaml(case.test_dir / "meta.yaml") == {"bls_setting": 1, "blocks_count": 1}
        provider = read_yaml(case.test_dir / "dimensions.yaml")["test_provider"]
        if provider in ("process_operations_dispatch", "payload_attestation"):
            assert read_yaml(case.test_dir / "config.yaml")["GLOAS_FORK_EPOCH"] == 0
            assert all(
                check.status == "ok"
                for check in load_provider(provider).validate_case(case.test_dir)
            )
        replay.run_test(case)
        if case_handler == "blocks" and not (case.test_dir / "post.ssz_snappy").exists():
            check_rejected_block(case)
    assert spec.config is original_config
    assert bls.bls_active is False


def check_rejected_block(case):
    # Let only the failing operations check return. The signature, remaining block
    # processing, and state root must all validate independently of that rejection.
    spec = get_copy_of_spec(replay.load_spec(case.preset, case.fork, case.test_dir))
    process_operations = spec.process_operations

    def expect_rejected_operations(state, body, parent_slot):
        with pytest.raises(AssertionError):
            process_operations(state, body, parent_slot)

    spec.process_operations = expect_rejected_operations
    vector = replay.get_test_case(spec, case.test_dir, case.handler)
    with bls_enabled():
        spec.state_transition(vector["pre"], vector["blocks"][0], validate_result=True)


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
            self.spec = spec
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
