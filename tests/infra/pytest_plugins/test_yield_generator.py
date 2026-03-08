from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

# Import context first to resolve the circular dependency:
# yield_generator -> dumper -> context -> yield_generator.
# When context initiates the chain, the partial module resolution works correctly.
from eth_consensus_specs.test import context  # noqa: F401
from tests.infra.manifest import Manifest
from tests.infra.pytest_plugins.yield_generator import (
    _derive_handler_name,
    _find_runner,
    _infer_manifest,
)


class TestFindRunner:
    """Tests for _find_runner."""

    def test_returns_none_for_unittests(self):
        path = Path("/some/path/unittests/test_foo.py")
        assert _find_runner(path) is None

    def test_finds_closest_runner_when_multiple_in_path(self):
        # fork is closer to the file than sanity, so it wins
        path = Path("/some/path/sanity/fork/test_foo.py")
        pkg_name, config = _find_runner(path)
        assert pkg_name == "fork"
        assert config["handler_name_fixed"] == "fork"


class TestDeriveHandlerName:
    """Tests for _derive_handler_name."""

    def test_map_takes_precedence_over_strip(self):
        config = {
            "handler_name_map": {
                "test_process_sync_aggregate_random": "sync_aggregate",
            },
            "handler_name_strip": ["test_process_"],
        }
        result = _derive_handler_name(config, "test_process_sync_aggregate_random")
        assert result == "sync_aggregate"

    def test_strip_only_removes_prefix(self):
        """removeprefix must not strip occurrences in the middle of the name."""
        config = {
            "handler_name_strip": ["test_"],
        }
        result = _derive_handler_name(config, "contest_results")
        assert result == "contest_results"

    def test_custom_strip_prefixes(self):
        config = {
            "handler_name_strip": ["test_process_", "test_apply_"],
        }
        assert _derive_handler_name(config, "test_process_rewards") == "rewards"
        assert _derive_handler_name(config, "test_apply_pending_deposit") == "pending_deposit"


def _make_stub(name, path, originalname=None, obj=None, callspec=None):
    """Build a stub with the attributes _infer_manifest reads."""
    stub = MagicMock(
        spec=[
            "name",
            "parent",
            "obj",
            "originalname",
        ]
    )
    stub.name = name
    stub.parent = SimpleNamespace(path=path)
    stub.originalname = originalname or name
    stub.obj = obj if obj is not None else SimpleNamespace()
    if callspec is not None:
        stub.callspec = callspec
    return stub


class TestInferManifest:
    """Tests for _infer_manifest."""

    def test_block_processing_runner(self):
        """block_processing maps runner to 'operations' and strips test_process_ from handler."""
        stub = _make_stub(
            name="test_success",
            path=Path("/x/block_processing/test_process_attestation.py"),
        )
        m = _infer_manifest(stub)
        assert m.runner_name == "operations"
        assert m.handler_name == "attestation"
        assert m.case_name == "success"
        assert m.suite_name == "pyspec_tests"

    def test_no_manifest_for_unittests_path(self):
        """When the path walks through unittests, no manifest is set."""
        stub = _make_stub(
            name="test_foo",
            path=Path("/x/unittests/test_foo.py"),
        )
        assert _infer_manifest(stub) is None

    def test_obj_manifest_overrides_guessed(self):
        """A manifest attached to the test function overrides guessed fields."""
        obj = SimpleNamespace(
            manifest=Manifest(handler_name="custom_handler"),
        )
        stub = _make_stub(
            name="test_something",
            path=Path("/x/fork/test_fork.py"),
            obj=obj,
        )
        m = _infer_manifest(stub)
        assert m.handler_name == "custom_handler"
        # Non-overridden fields still come from the guess
        assert m.runner_name == "fork"
        assert m.case_name == "something"

    def test_callspec_preset(self):
        """Preset is extracted from callspec.params when present."""
        callspec = SimpleNamespace(params={"preset": "mainnet"})
        stub = _make_stub(
            name="test_valid",
            path=Path("/x/bls/test_verify.py"),
            callspec=callspec,
        )
        m = _infer_manifest(stub)
        assert m.preset_name == "mainnet"

    def test_obj_suite_name(self):
        """suite_name from the test function object is used when present."""
        obj = SimpleNamespace(suite_name="custom_suite")
        stub = _make_stub(
            name="test_core",
            path=Path("/x/shuffling/test_shuffling.py"),
            obj=obj,
        )
        m = _infer_manifest(stub)
        # shuffling has config suite_name="shuffle", which takes precedence over obj
        assert m.suite_name == "shuffle"
        assert m.handler_name == "core"

        # But for a runner without config suite_name, obj.suite_name is used
        stub2 = _make_stub(
            name="test_core",
            path=Path("/x/bls/test_verify.py"),
            obj=obj,
        )
        m2 = _infer_manifest(stub2)
        assert m2.suite_name == "custom_suite"
