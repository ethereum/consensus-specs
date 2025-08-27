import inspect
import sys
import types
from collections.abc import Callable

import pytest

from eth2spec.test.helpers.constants import BELLATRIX, CAPELLA, DENEB, PHASE0
from eth2spec.test.helpers.typing import SpecForkName
from tests.infra.template_test import (
    template_test,
    template_test_upgrades_from,
    template_test_upgrades_from_to,
)

### Mock classes for testing


class MockFrame:
    """
    Mock implementation of a Python frame object.

    Used to simulate frame objects returned by inspect.currentframe() during testing.
    """

    def __init__(self, module_name: str, function_name: str | None = None):
        """
        Initialize a mock frame.

        Args:
            module_name: The __name__ of the module this frame represents
            function_name: Optional function name for f_locals
        """
        self.f_globals = {"__name__": module_name}
        if function_name:
            self.f_locals = {"__name__": function_name}
        else:
            self.f_locals = {}
        self.f_back: MockFrame | None = self  # Default to self, can be overridden


class MockRootFrame:
    """
    Mock implementation of a root frame object.

    Represents the outermost frame in a call stack.
    """

    def __init__(self, caller_frame: MockFrame):
        """
        Initialize a mock root frame.

        Args:
            caller_frame: The frame that called this one
        """
        self.f_back = caller_frame


class MockFrameworkUtility:
    """Utility class for mocking frame inspection functionality."""

    def __init__(self, test_module: types.ModuleType):
        """
        Initialize the mock framework utility.

        Args:
            test_module: The module where tests should be registered
        """
        self.test_module = test_module
        self.original_currentframe = inspect.currentframe
        self.original_getmodule = inspect.getmodule

    def create_mock_currentframe(self, module_name: str) -> Callable[[], MockRootFrame]:
        """
        Create a mock currentframe function that simulates being called from a specific module.

        Args:
            module_name: The name of the module to simulate

        Returns:
            A function that returns a mock frame
        """

        def mock_frame():
            mock_caller = MockFrame(module_name)
            mock_root = MockRootFrame(mock_caller)
            return mock_root

        # Set up mock getmodule
        def mock_getmodule(frame):
            if hasattr(frame, "f_globals") and frame.f_globals.get("__name__") == module_name:
                return self.test_module
            return self.original_getmodule(frame)

        inspect.getmodule = mock_getmodule
        return mock_frame

    def create_mock_currentframe_with_function(
        self, module_name: str, function_name: str
    ) -> Callable[[], MockFrame]:
        """
        Create a mock currentframe that simulates being called from within a function.

        Args:
            module_name: The name of the module
            function_name: The name of the function

        Returns:
            A function that returns a mock frame
        """

        def mock_frame():
            # Current frame (decorator's frame)
            current_frame = MockFrame("tests.infra.template_test", "template_test")

            # Caller frame (function that called the template)
            caller_frame = MockFrame(module_name, function_name)

            # Link the frames
            current_frame.f_back = caller_frame

            return current_frame

        # Set up mock getmodule
        def mock_getmodule(frame):
            if hasattr(frame, "f_globals") and frame.f_globals.get("__name__") == module_name:
                return self.test_module
            return self.original_getmodule(frame)

        inspect.getmodule = mock_getmodule
        return mock_frame

    def restore(self):
        """Restore original inspect functions."""
        inspect.currentframe = self.original_currentframe
        inspect.getmodule = self.original_getmodule


class MockDecoratorUtility:
    """Utility class for creating common mock decorators used in tests."""

    @staticmethod
    def create_mock_spec_test() -> Callable:
        """
        Create a mock spec test decorator.

        Returns:
            A decorator that simulates spec test behavior
        """

        def mock_spec_test(fn):
            def wrapper(*args, **kwargs):
                # Simulate spec test behavior
                return fn(*args, **kwargs)

            wrapper.__name__ = fn.__name__
            return wrapper

        return mock_spec_test

    @staticmethod
    def create_mock_with_phases(phases: list) -> Callable:
        """
        Create a mock decorator that adds phases to kwargs.

        Args:
            phases: List of phases to add

        Returns:
            A decorator function
        """

        def decorator(fn):
            def wrapper(*args, **kwargs):
                # Simulate phase handling
                kwargs["phases"] = phases
                return fn(*args, **kwargs)

            wrapper.__name__ = fn.__name__
            return wrapper

        return decorator


### @template_test decorators family tests


@pytest.fixture
def test_module():
    """Create a mock module for testing."""
    module = types.ModuleType("test_module")
    sys.modules["test_module"] = module
    yield module
    # Cleanup
    if "test_module" in sys.modules:
        del sys.modules["test_module"]


@pytest.fixture
def mock_utility(test_module):
    """Create mock framework utility."""
    utility = MockFrameworkUtility(test_module)
    yield utility
    # Cleanup
    utility.restore()


class TestTemplateTestDecorator:
    """Test suite for the template_test decorator."""

    def _mock_currentframe(self, mock_utility, module_name="test_module"):
        """Create a mock frame that simulates being called from a specific module."""
        return mock_utility.create_mock_currentframe(module_name)

    def test_basic_functionality(self, test_module, mock_utility):
        """Test basic template_test decorator functionality."""
        # Mock the frame to simulate being called from test_module
        inspect.currentframe = self._mock_currentframe(mock_utility, "test_module")

        @template_test
        def _test_template(param1, param2):
            def test_func():
                return f"test_{param1}_{param2}"

            return test_func, f"test_generated_{param1}_{param2}"

        # Call the template function - it returns None
        result = _test_template("foo", "bar")
        assert result is None

        # Verify the test was registered in the module
        test_name = "test_generated_foo_bar"
        assert hasattr(test_module, test_name)
        registered_func = getattr(test_module, test_name)
        assert callable(registered_func)
        assert registered_func() == "test_foo_bar"

    def test_template_with_kwargs(self, test_module, mock_utility):
        """Test template function with keyword arguments."""
        inspect.currentframe = self._mock_currentframe(mock_utility, "test_module")

        @template_test
        def _test_template(param1, param2=None, param3="default"):
            def test_func():
                return f"test_{param1}_{param2}_{param3}"

            return test_func, f"test_kwargs_{param1}_{param2}_{param3}"

        _test_template("pos", param2="kw", param3="arg")

        test_name = "test_kwargs_pos_kw_arg"
        assert hasattr(test_module, test_name)
        test_func = getattr(test_module, test_name)
        assert test_func() == "test_pos_kw_arg"

    def test_frame_inspection_error_no_current_frame(self):
        """Test error handling when currentframe returns None."""
        # Mock currentframe to return None
        inspect.currentframe = lambda: None

        @template_test
        def _test_template():
            def test_func():
                pass

            return test_func, "test_name"

        # The error should happen when calling the decorated function
        with pytest.raises(RuntimeError) as excinfo:
            _test_template()

        assert str(excinfo.value) == "Could not determine target module for test registration"

    def test_instantiate_module_parameter(self, test_module, mock_utility):
        """Test that the _instantiate_module parameter allows registering tests in a specific module."""
        # Create a separate module for instantiation
        target_module = types.ModuleType("target_module")
        sys.modules["target_module"] = target_module

        try:
            inspect.currentframe = self._mock_currentframe(mock_utility, "test_module")

            @template_test
            def _test_template(param):
                def test_func():
                    return f"test_{param}"

                return test_func, f"test_instantiate_{param}"

            # Call without _instantiate_module - should register in caller's module
            _test_template("default")
            test_name1 = "test_instantiate_default"
            assert hasattr(test_module, test_name1)
            assert not hasattr(target_module, test_name1)

            # Call with _instantiate_module - should register in target module
            _test_template("target", _instantiate_module=target_module)
            test_name2 = "test_instantiate_target"
            assert not hasattr(test_module, test_name2)
            assert hasattr(target_module, test_name2)

            # Verify they are registered and callable from their modules
            assert getattr(test_module, test_name1)() == "test_default"
            assert getattr(target_module, test_name2)() == "test_target"

        finally:
            del sys.modules["target_module"]


@pytest.fixture
def integration_test_module():
    """Create a mock module for integration testing."""
    module = types.ModuleType("integration_test_module")
    sys.modules["integration_test_module"] = module
    yield module
    # Cleanup
    if "integration_test_module" in sys.modules:
        del sys.modules["integration_test_module"]


@pytest.fixture
def integration_mock_utility(integration_test_module):
    """Create mock framework utility for integration tests."""
    utility = MockFrameworkUtility(integration_test_module)
    yield utility
    # Cleanup
    utility.restore()


class TestTemplateTestIntegration:
    """Integration tests for template_test decorator with existing test infrastructure."""

    def _mock_currentframe(self, integration_mock_utility, module_name="integration_test_module"):
        """Create a mock frame for integration tests."""
        return integration_mock_utility.create_mock_currentframe(module_name)

    def test_integration_with_mock_spec_decorators(
        self, integration_test_module, integration_mock_utility
    ):
        """Test template_test integration with mock spec-style decorators."""
        inspect.currentframe = self._mock_currentframe(
            integration_mock_utility, "integration_test_module"
        )

        # Mock some spec-style decorators
        mock_spec_test = MockDecoratorUtility.create_mock_spec_test()
        mock_with_phases = MockDecoratorUtility.create_mock_with_phases

        @template_test
        def _test_template(pre_spec, post_spec):
            @mock_with_phases(phases=[pre_spec, post_spec])
            @mock_spec_test
            def test_fork_transition(spec, phases):
                return f"transition_{pre_spec}_to_{post_spec}"

            return test_fork_transition, f"test_fork_transition_{pre_spec}_to_{post_spec}"

        # Call the template
        _test_template("phase0", "altair")

        # Verify the integration works
        test_name = "test_fork_transition_phase0_to_altair"
        assert hasattr(integration_test_module, test_name)

        # Test the decorated function
        test_func = getattr(integration_test_module, test_name)
        result = test_func(spec="mock_spec", phases=["phase0", "altair"])
        assert result == "transition_phase0_to_altair"

    def test_template_with_generator_functions(
        self, integration_test_module, integration_mock_utility
    ):
        """Test template_test with generator functions (common in spec tests)."""
        inspect.currentframe = self._mock_currentframe(
            integration_mock_utility, "integration_test_module"
        )

        @template_test
        def _test_template(test_case):
            def test_generator(spec, state):
                # Simulate typical spec test generator pattern
                yield "pre", {"state": state, "case": test_case}
                # Simulate test execution
                yield "post", {"result": f"processed_{test_case}"}

            return test_generator, f"test_generator_{test_case}"

        # Call the template
        _test_template("block_processing")

        # Verify registration
        test_name = "test_generator_block_processing"
        assert hasattr(integration_test_module, test_name)

        # Test the generator function
        test_func = getattr(integration_test_module, test_name)
        gen = test_func(spec="mock_spec", state="mock_state")
        pre_result = next(gen)
        post_result = next(gen)

        assert pre_result[0] == "pre"
        assert pre_result[1]["case"] == "block_processing"
        assert post_result[0] == "post"
        assert post_result[1]["result"] == "processed_block_processing"

    def _mock_currentframe_with_function_call(
        self,
        integration_mock_utility,
        module_name="integration_test_module",
        function_name="test_function",
    ):
        """Create a mock frame that simulates being called from within a function."""
        return integration_mock_utility.create_mock_currentframe_with_function(
            module_name, function_name
        )

    def test_template_called_from_within_function(
        self, integration_test_module, integration_mock_utility
    ):
        """Test template_test decorator when called from within a function (non-module-level)."""
        inspect.currentframe = self._mock_currentframe_with_function_call(
            integration_mock_utility, "integration_test_module", "function_that_calls_template"
        )

        @template_test
        def _test_template(param):
            def test_func():
                return f"function_scoped_test_{param}"

            return test_func, f"test_function_scoped_{param}"

        def function_that_calls_template():
            """A function that calls the template from within its body."""
            _test_template("example")

        # Call the template from within the function
        function_that_calls_template()

        # The template should still register in the module, not the function's local scope
        test_name = "test_function_scoped_example"
        assert hasattr(integration_test_module, test_name)

        # The registered function should work correctly
        registered_func = getattr(integration_test_module, test_name)
        assert registered_func() == "function_scoped_test_example"


@pytest.fixture
def upgrade_test_module():
    """Create a mock module for upgrade testing."""
    module = types.ModuleType("upgrade_test_module")
    sys.modules["upgrade_test_module"] = module
    yield module
    # Cleanup
    if "upgrade_test_module" in sys.modules:
        del sys.modules["upgrade_test_module"]


@pytest.fixture
def upgrade_mock_utility(upgrade_test_module):
    """Create mock framework utility for upgrade tests."""
    utility = MockFrameworkUtility(upgrade_test_module)
    yield utility
    # Cleanup
    utility.restore()


class TestTemplateUpgradeDecorators:
    """Test suite for template_test_upgrades_from and template_test_upgrades_from_to decorators."""

    def _mock_currentframe(self, upgrade_mock_utility, module_name="upgrade_test_module"):
        """Create a mock frame that simulates being called from a specific module."""
        return upgrade_mock_utility.create_mock_currentframe(module_name)

    def test_template_test_upgrades_from_basic(self, upgrade_test_module, upgrade_mock_utility):
        """Test basic functionality of template_test_upgrades_from decorator."""
        inspect.currentframe = self._mock_currentframe(upgrade_mock_utility, "upgrade_test_module")

        @template_test_upgrades_from(CAPELLA)
        def _template_upgrade(pre_spec: SpecForkName, post_spec: SpecForkName):
            def test_func():
                return f"upgrade_{pre_spec}_to_{post_spec}"

            return test_func, f"test_upgrade_{pre_spec}_to_{post_spec}"

        # Call the decorated function to trigger registration
        _template_upgrade()

        # The decorator should have registered tests for CAPELLA->DENEB, DENEB->ELECTRA, ELECTRA->FULU
        # Check that tests were registered for the expected upgrades
        assert hasattr(upgrade_test_module, "test_upgrade_capella_to_deneb")
        assert hasattr(upgrade_test_module, "test_upgrade_deneb_to_electra")
        assert hasattr(upgrade_test_module, "test_upgrade_electra_to_fulu")

        # Should NOT have registered for earlier forks
        assert not hasattr(upgrade_test_module, "test_upgrade_phase0_to_altair")
        assert not hasattr(upgrade_test_module, "test_upgrade_altair_to_bellatrix")

        # Execute the registered tests to verify they work
        test_capella_deneb = getattr(upgrade_test_module, "test_upgrade_capella_to_deneb")
        assert test_capella_deneb() == "upgrade_capella_to_deneb"

        test_deneb_electra = getattr(upgrade_test_module, "test_upgrade_deneb_to_electra")
        assert test_deneb_electra() == "upgrade_deneb_to_electra"

        test_electra_fulu = getattr(upgrade_test_module, "test_upgrade_electra_to_fulu")
        assert test_electra_fulu() == "upgrade_electra_to_fulu"

    def test_template_test_upgrades_from_to_basic(self, upgrade_test_module, upgrade_mock_utility):
        """Test basic functionality of template_test_upgrades_from_to decorator."""
        inspect.currentframe = self._mock_currentframe(upgrade_mock_utility, "upgrade_test_module")

        @template_test_upgrades_from_to(PHASE0, BELLATRIX)
        def _template_range_upgrade(pre_spec: SpecForkName, post_spec: SpecForkName):
            def test_func():
                return f"range_{pre_spec}_to_{post_spec}"

            return test_func, f"test_range_{pre_spec}_to_{post_spec}"

        # Call the decorated function to trigger registration
        _template_range_upgrade()

        # Should have registered tests for PHASE0->ALTAIR, ALTAIR->BELLATRIX, and BELLATRIX->CAPELLA
        assert hasattr(upgrade_test_module, "test_range_phase0_to_altair")
        assert hasattr(upgrade_test_module, "test_range_altair_to_bellatrix")
        assert hasattr(upgrade_test_module, "test_range_bellatrix_to_capella")

        # Should NOT have registered beyond CAPELLA
        assert not hasattr(upgrade_test_module, "test_range_capella_to_deneb")

        # Execute the registered tests
        test_phase0_altair = getattr(upgrade_test_module, "test_range_phase0_to_altair")
        assert test_phase0_altair() == "range_phase0_to_altair"

        test_altair_bellatrix = getattr(upgrade_test_module, "test_range_altair_to_bellatrix")
        assert test_altair_bellatrix() == "range_altair_to_bellatrix"

        test_bellatrix_capella = getattr(upgrade_test_module, "test_range_bellatrix_to_capella")
        assert test_bellatrix_capella() == "range_bellatrix_to_capella"

    def test_template_test_upgrades_from_to_single_upgrade(
        self, upgrade_test_module, upgrade_mock_utility
    ):
        """Test template_test_upgrades_from_to with a single upgrade."""
        inspect.currentframe = self._mock_currentframe(upgrade_mock_utility, "upgrade_test_module")

        @template_test_upgrades_from_to(DENEB, DENEB)
        def _template_single(pre_spec: SpecForkName, post_spec: SpecForkName):
            def test_func():
                return f"single_{pre_spec}_to_{post_spec}"

            return test_func, f"test_single_{pre_spec}_to_{post_spec}"

        # Call the decorated function to trigger registration
        _template_single()

        # Should only register the upgrade from DENEB to ELECTRA
        assert hasattr(upgrade_test_module, "test_single_deneb_to_electra")

        # Should NOT register others
        assert not hasattr(upgrade_test_module, "test_single_capella_to_deneb")
        assert not hasattr(upgrade_test_module, "test_single_electra_to_fulu")
