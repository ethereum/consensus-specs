"""Tests for context decorators."""

import pytest
from lru import LRU

from eth_consensus_specs.test.context import (
    get_copy_of_spec,
    with_config_overrides,
    with_custom_state as exported_with_custom_state,
)
from eth_consensus_specs.test.helpers.constants import MINIMAL
from eth_consensus_specs.test.helpers.specs import spec_targets
from tests.infra import context as infra_context
from tests.infra.context import with_custom_state


def get_test_spec():
    """Get a minimal phase0 spec for testing."""
    targets = spec_targets[MINIMAL]
    return targets["phase0"]


class FakeConfig:
    """Minimal config stub for testing cache-key behavior."""

    def __init__(self, config_hash=0):
        self._config_hash = config_hash

    def __hash__(self):
        return self._config_hash


class FakeState:
    """Minimal state stub wrapping a backing object."""

    def __init__(self, backing):
        self.backing = backing

    def get_backing(self):
        return self.backing


class FakeSpec:
    """Minimal spec stub providing BeaconState, fork, config, and __file__."""

    BeaconState = FakeState

    def __init__(self, fork="phase0", config_hash=0, spec_file="phase0.py"):
        self.fork = fork
        self.config = FakeConfig(config_hash)
        self.__file__ = spec_file


@pytest.fixture(autouse=True)
def _reset_custom_state_cache(monkeypatch):
    """Reset the LRU cache before each test to avoid cross-test leakage."""
    monkeypatch.setattr(infra_context, "_custom_state_cache_dict", LRU(size=10))


class TestWithConfigOverridesDecorator:
    """Tests for with_config_overrides decorator."""

    def test_with_config_overrides_applies_overrides_to_spec(self):
        """Test that decorator applies overrides to spec parameter."""
        spec = get_test_spec()

        # Create a test function
        received_spec_value = None

        def test_fn(spec):
            nonlocal received_spec_value
            received_spec_value = spec.config.MIN_PER_EPOCH_CHURN_LIMIT
            return "test_result"

        # Apply decorator
        overrides = {"MIN_PER_EPOCH_CHURN_LIMIT": 999}
        decorated_fn = with_config_overrides(overrides)(test_fn)

        # Call the decorated function
        result = decorated_fn(spec=spec)

        # Function should receive modified spec
        assert received_spec_value == 999
        assert result == "test_result"

    def test_with_config_overrides_preserves_return_value(self):
        """Test that decorator preserves function return value."""

        def test_fn(spec):
            return {"result": "success", "value": spec.config.MIN_PER_EPOCH_CHURN_LIMIT}

        overrides = {"MIN_PER_EPOCH_CHURN_LIMIT": 999}
        decorated_fn = with_config_overrides(overrides)(test_fn)

        result = decorated_fn(spec=get_test_spec())

        assert result["result"] == "success"
        assert result["value"] == 999

    def test_with_config_overrides_passes_through_args(self):
        """Test that decorator passes through positional arguments."""
        received_args = None

        def test_fn(arg1, arg2, spec):
            nonlocal received_args
            received_args = (arg1, arg2)
            return "ok"

        overrides = {"MIN_PER_EPOCH_CHURN_LIMIT": 999}
        decorated_fn = with_config_overrides(overrides)(test_fn)

        result = decorated_fn("first", "second", spec=get_test_spec())

        assert received_args == ("first", "second")
        assert result == "ok"

    def test_with_config_overrides_passes_through_kwargs(self):
        """Test that decorator passes through keyword arguments."""
        received_kwargs = None

        def test_fn(spec, **kwargs):
            nonlocal received_kwargs
            received_kwargs = kwargs
            return "ok"

        overrides = {"MIN_PER_EPOCH_CHURN_LIMIT": 999}
        decorated_fn = with_config_overrides(overrides)(test_fn)

        result = decorated_fn(spec=get_test_spec(), param1="value1", param2="value2")

        assert received_kwargs["param1"] == "value1"
        assert received_kwargs["param2"] == "value2"
        assert result == "ok"

    def test_with_config_overrides_applies_to_phases(self):
        """Test that decorator applies overrides to phases parameter."""
        spec = get_test_spec()
        phases = {
            "phase0": get_copy_of_spec(spec),
            "altair": get_copy_of_spec(spec),
        }

        received_phases = None

        def test_fn(spec, **kwargs):
            nonlocal received_phases
            received_phases = kwargs.get("phases")
            return "ok"

        overrides = {"MIN_PER_EPOCH_CHURN_LIMIT": 999}
        decorated_fn = with_config_overrides(overrides)(test_fn)

        result = decorated_fn(spec=spec, phases=phases)

        # Phases should be modified
        assert received_phases is not None
        assert "phase0" in received_phases
        assert "altair" in received_phases
        assert received_phases["phase0"].config.MIN_PER_EPOCH_CHURN_LIMIT == 999
        assert received_phases["altair"].config.MIN_PER_EPOCH_CHURN_LIMIT == 999
        assert result == "ok"

    def test_with_config_overrides_doesnt_modify_original_spec(self):
        """Test that decorator doesn't modify the original spec."""
        spec = get_test_spec()
        original_value = spec.config.MIN_PER_EPOCH_CHURN_LIMIT
        assert original_value != 999

        def test_fn(spec):
            # Verify spec received has override
            assert spec.config.MIN_PER_EPOCH_CHURN_LIMIT == 999
            return "ok"

        overrides = {"MIN_PER_EPOCH_CHURN_LIMIT": 999}
        decorated_fn = with_config_overrides(overrides)(test_fn)

        decorated_fn(spec=spec)

        # Original spec should be unchanged
        assert spec.config.MIN_PER_EPOCH_CHURN_LIMIT == original_value

    def test_with_config_overrides_doesnt_modify_original_phases(self):
        """Test that decorator doesn't modify the original phases."""
        spec = get_test_spec()
        phases = {
            "phase0": get_copy_of_spec(spec),
        }
        original_value = phases["phase0"].config.MIN_PER_EPOCH_CHURN_LIMIT

        def test_fn(spec, **kwargs):
            # Verify phases received have override
            modified_phases = kwargs.get("phases")
            assert modified_phases["phase0"].config.MIN_PER_EPOCH_CHURN_LIMIT == 999
            return "ok"

        overrides = {"MIN_PER_EPOCH_CHURN_LIMIT": 999}
        decorated_fn = with_config_overrides(overrides)(test_fn)

        decorated_fn(spec=spec, phases=phases)

        # Original phases should be unchanged
        assert phases["phase0"].config.MIN_PER_EPOCH_CHURN_LIMIT == original_value

    def test_with_config_overrides_works_without_phases(self):
        """Test that decorator works when phases parameter is not provided."""
        received_spec_value = None

        def test_fn(spec, **kwargs):
            nonlocal received_spec_value
            received_spec_value = spec.config.MIN_PER_EPOCH_CHURN_LIMIT
            # Verify no phases in kwargs
            assert "phases" not in kwargs
            return "ok"

        overrides = {"MIN_PER_EPOCH_CHURN_LIMIT": 999}
        decorated_fn = with_config_overrides(overrides)(test_fn)

        result = decorated_fn(spec=get_test_spec())

        assert received_spec_value == 999
        assert result == "ok"

    def test_with_config_overrides_with_multiple_overrides(self):
        """Test decorator with multiple config overrides."""

        def test_fn(spec):
            return {
                "churn_limit": spec.config.MIN_PER_EPOCH_CHURN_LIMIT,
                "churn_quotient": spec.config.CHURN_LIMIT_QUOTIENT,
                "ejection_balance": spec.config.EJECTION_BALANCE,
            }

        overrides = {
            "MIN_PER_EPOCH_CHURN_LIMIT": 111,
            "CHURN_LIMIT_QUOTIENT": 222,
            "EJECTION_BALANCE": 333,
        }
        decorated_fn = with_config_overrides(overrides)(test_fn)

        result = decorated_fn(spec=get_test_spec())

        assert result["churn_limit"] == 111
        assert result["churn_quotient"] == 222
        assert result["ejection_balance"] == 333

    def test_with_config_overrides_empty_overrides_dict(self):
        """Test decorator with empty overrides dict."""
        spec = get_test_spec()
        original_value = spec.config.MIN_PER_EPOCH_CHURN_LIMIT

        def test_fn(spec):
            return spec.config.MIN_PER_EPOCH_CHURN_LIMIT

        overrides = {}
        decorated_fn = with_config_overrides(overrides)(test_fn)

        result = decorated_fn(spec=spec)

        # Should get a copy of the spec but with same values
        assert result == original_value

    def test_with_config_overrides_can_be_stacked(self):
        """Test that multiple with_config_overrides decorators can be stacked."""

        def test_fn(spec):
            return {
                "churn_limit": spec.config.MIN_PER_EPOCH_CHURN_LIMIT,
                "churn_quotient": spec.config.CHURN_LIMIT_QUOTIENT,
            }

        # Apply two decorators
        decorated_fn = with_config_overrides({"MIN_PER_EPOCH_CHURN_LIMIT": 111})(
            with_config_overrides({"CHURN_LIMIT_QUOTIENT": 222})(test_fn)
        )

        result = decorated_fn(spec=get_test_spec())

        # Inner sets CHURN_LIMIT_QUOTIENT, outer sets MIN_PER_EPOCH_CHURN_LIMIT
        # Both are present because they target different keys
        assert result["churn_limit"] == 111
        assert result["churn_quotient"] == 222

    def test_with_config_overrides_with_real_fork_versions(self):
        """Test decorator with fork version overrides (common use case)."""

        def test_fn(spec):
            return {
                "genesis_version": spec.config.GENESIS_FORK_VERSION,
            }

        overrides = {
            "GENESIS_FORK_VERSION": "0x12345678",
        }
        decorated_fn = with_config_overrides(overrides)(test_fn)

        result = decorated_fn(spec=get_test_spec())

        # Should be converted to Version type
        assert result["genesis_version"] == get_test_spec().Version("0x12345678")


class TestWithCustomStateDecorator:
    """Tests for with_custom_state decorator."""

    def test_with_custom_state_is_reexported_from_pyspec_context(self):
        """Test that pyspec context re-exports the infra decorator."""
        assert exported_with_custom_state is with_custom_state

    def test_with_custom_state_injects_state_and_preserves_call_arguments(self, monkeypatch):
        spec = FakeSpec()
        phases = {"phase0": spec}
        prepared_backing = object()
        calls = {}

        def balances_fn(_spec):
            return [1]

        def threshold_fn(_spec):
            return 1

        def prepare_state(input_balances_fn, input_threshold_fn, input_spec, input_phases):
            calls["prepare_args"] = (
                input_balances_fn,
                input_threshold_fn,
                input_spec,
                input_phases,
            )
            return FakeState(prepared_backing)

        monkeypatch.setattr(infra_context, "_prepare_state", prepare_state)

        @with_custom_state(balances_fn=balances_fn, threshold_fn=threshold_fn)
        def test_case(first_arg, *, spec, phases, state, extra_kwarg):
            return first_arg, spec, phases, state, extra_kwarg

        first_arg, output_spec, output_phases, state, extra_kwarg = test_case(
            "first",
            spec=spec,
            phases=phases,
            extra_kwarg="extra",
        )

        assert calls["prepare_args"] == (balances_fn, threshold_fn, spec, phases)
        assert first_arg == "first"
        assert output_spec is spec
        assert output_phases is phases
        assert extra_kwarg == "extra"
        assert state.backing is prepared_backing

    def test_with_custom_state_caches_backing_and_returns_fresh_views(self, monkeypatch):
        spec = FakeSpec()
        phases = {"phase0": spec}
        prepare_calls = []
        received_args = {}

        def balances_fn(_spec):
            return [1]

        def threshold_fn(_spec):
            return 1

        def prepare_state(input_balances_fn, input_threshold_fn, input_spec, input_phases):
            backing = object()
            prepare_calls.append((input_balances_fn, input_threshold_fn, input_spec, input_phases))
            return FakeState(backing)

        monkeypatch.setattr(infra_context, "_prepare_state", prepare_state)

        @with_custom_state(balances_fn=balances_fn, threshold_fn=threshold_fn)
        def test_case(*, spec, phases, state):
            received_args["spec"] = spec
            received_args["phases"] = phases
            received_args["state"] = state
            return state

        first_state = test_case(spec=spec, phases=phases)
        second_state = test_case(spec=spec, phases=phases)

        assert prepare_calls == [(balances_fn, threshold_fn, spec, phases)]
        assert first_state is not second_state
        assert first_state.get_backing() is second_state.get_backing()
        assert received_args["spec"] is spec
        assert received_args["phases"] is phases
        assert received_args["state"].get_backing() is first_state.get_backing()

    def test_with_custom_state_cache_key_includes_spec_and_input_functions(self, monkeypatch):
        phases = {}
        prepare_calls = []

        def balances_fn(_spec):
            return [1]

        def other_balances_fn(_spec):
            return [1]

        def threshold_fn(_spec):
            return 1

        def other_threshold_fn(_spec):
            return 1

        def prepare_state(input_balances_fn, input_threshold_fn, input_spec, input_phases):
            prepare_calls.append((input_balances_fn, input_threshold_fn, input_spec))
            return FakeState(object())

        monkeypatch.setattr(infra_context, "_prepare_state", prepare_state)

        @with_custom_state(balances_fn=balances_fn, threshold_fn=threshold_fn)
        def test_case(*, spec, phases, state):
            return state

        @with_custom_state(balances_fn=other_balances_fn, threshold_fn=threshold_fn)
        def test_case_other_balances(*, spec, phases, state):
            return state

        @with_custom_state(balances_fn=balances_fn, threshold_fn=other_threshold_fn)
        def test_case_other_threshold(*, spec, phases, state):
            return state

        base_spec = FakeSpec()
        same_key_spec = FakeSpec()
        other_fork_spec = FakeSpec(fork="altair")
        other_config_spec = FakeSpec(config_hash=1)
        other_file_spec = FakeSpec(spec_file="altair.py")

        test_case(spec=base_spec, phases=phases)
        test_case(spec=same_key_spec, phases=phases)
        test_case(spec=other_fork_spec, phases=phases)
        test_case(spec=other_config_spec, phases=phases)
        test_case(spec=other_file_spec, phases=phases)
        test_case_other_balances(spec=base_spec, phases=phases)
        test_case_other_threshold(spec=base_spec, phases=phases)

        assert prepare_calls == [
            (balances_fn, threshold_fn, base_spec),
            (balances_fn, threshold_fn, other_fork_spec),
            (balances_fn, threshold_fn, other_config_spec),
            (balances_fn, threshold_fn, other_file_spec),
            (other_balances_fn, threshold_fn, base_spec),
            (balances_fn, other_threshold_fn, base_spec),
        ]
