"""Tests for the with_config_overrides decorator."""

from eth_consensus_specs.test.context import (
    get_copy_of_spec,
    with_config_overrides,
)
from eth_consensus_specs.test.helpers.constants import MINIMAL
from eth_consensus_specs.test.helpers.specs import spec_targets


# Test helper to get a spec instance for testing
def get_test_spec():
    """Get a minimal phase0 spec for testing."""
    targets = spec_targets[MINIMAL]
    return targets["phase0"]


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

        # Both overrides should be applied (outer one wins for spec parameter)
        assert result["churn_limit"] == 111
        # Inner decorator should have set this
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
