import inspect
import sys
import types
import unittest
from collections.abc import Callable
from unittest import TestCase

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


class TestTemplateTestDecorator(TestCase):
    """Test suite for the template_test decorator."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a mock module for testing
        self.test_module = types.ModuleType("test_module")
        sys.modules["test_module"] = self.test_module

        # Store original functions for restoration
        self.original_currentframe = inspect.currentframe
        self.original_getmodule = inspect.getmodule

        # Create mock framework utility
        self.mock_utility = MockFrameworkUtility(self.test_module)

    def tearDown(self):
        """Clean up after tests."""
        # Remove test module from sys.modules
        if "test_module" in sys.modules:
            del sys.modules["test_module"]

        # Restore original functions
        self.mock_utility.restore()

    def _mock_currentframe(self, module_name="test_module"):
        """Create a mock frame that simulates being called from a specific module."""
        return self.mock_utility.create_mock_currentframe(module_name)

    def test_basic_functionality(self):
        """Test basic template_test decorator functionality."""
        # Mock the frame to simulate being called from test_module
        inspect.currentframe = self._mock_currentframe("test_module")

        @template_test
        def _test_template(param1, param2):
            def test_func():
                return f"test_{param1}_{param2}"

            return test_func, f"test_generated_{param1}_{param2}"

        # Call the template function - it returns None
        result = _test_template("foo", "bar")
        self.assertIsNone(result)

        # Verify the test was registered in the module
        test_name = "test_generated_foo_bar"
        self.assertTrue(hasattr(self.test_module, test_name))
        registered_func = getattr(self.test_module, test_name)
        self.assertTrue(callable(registered_func))
        self.assertEqual(registered_func(), "test_foo_bar")

    def test_template_with_kwargs(self):
        """Test template function with keyword arguments."""
        inspect.currentframe = self._mock_currentframe("test_module")

        @template_test
        def _test_template(param1, param2=None, param3="default"):
            def test_func():
                return f"test_{param1}_{param2}_{param3}"

            return test_func, f"test_kwargs_{param1}_{param2}_{param3}"

        _test_template("pos", param2="kw", param3="arg")

        test_name = "test_kwargs_pos_kw_arg"
        self.assertTrue(hasattr(self.test_module, test_name))
        test_func = getattr(self.test_module, test_name)
        self.assertEqual(test_func(), "test_pos_kw_arg")

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
        with self.assertRaises(RuntimeError) as context:
            _test_template()

        self.assertEqual(
            str(context.exception), "Could not determine target module for test registration"
        )

    def test_instantiate_module_parameter(self):
        """Test that the _instantiate_module parameter allows registering tests in a specific module."""
        # Create a separate module for instantiation
        target_module = types.ModuleType("target_module")
        sys.modules["target_module"] = target_module

        try:
            inspect.currentframe = self._mock_currentframe("test_module")

            @template_test
            def _test_template(param):
                def test_func():
                    return f"test_{param}"

                return test_func, f"test_instantiate_{param}"

            # Call without _instantiate_module - should register in caller's module
            _test_template("default")
            test_name1 = "test_instantiate_default"
            self.assertTrue(hasattr(self.test_module, test_name1))
            self.assertFalse(hasattr(target_module, test_name1))

            # Call with _instantiate_module - should register in target module
            _test_template("target", _instantiate_module=target_module)
            test_name2 = "test_instantiate_target"
            self.assertFalse(hasattr(self.test_module, test_name2))
            self.assertTrue(hasattr(target_module, test_name2))

            # Verify they are registered and callable from their modules
            self.assertEqual(getattr(self.test_module, test_name1)(), "test_default")
            self.assertEqual(getattr(target_module, test_name2)(), "test_target")

        finally:
            del sys.modules["target_module"]


class TestTemplateTestIntegration(TestCase):
    """Integration tests for template_test decorator with existing test infrastructure."""

    def setUp(self):
        """Set up test fixtures for integration tests."""
        self.test_module = types.ModuleType("integration_test_module")
        sys.modules["integration_test_module"] = self.test_module
        self.original_currentframe = inspect.currentframe
        self.original_getmodule = inspect.getmodule
        self.mock_utility = MockFrameworkUtility(self.test_module)

    def tearDown(self):
        """Clean up after integration tests."""
        if "integration_test_module" in sys.modules:
            del sys.modules["integration_test_module"]
        self.mock_utility.restore()

    def _mock_currentframe(self, module_name="integration_test_module"):
        """Create a mock frame for integration tests."""
        return self.mock_utility.create_mock_currentframe(module_name)

    def test_integration_with_mock_spec_decorators(self):
        """Test template_test integration with mock spec-style decorators."""
        inspect.currentframe = self._mock_currentframe("integration_test_module")

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
        self.assertTrue(hasattr(self.test_module, test_name))

        # Test the decorated function
        test_func = getattr(self.test_module, test_name)
        result = test_func(spec="mock_spec", phases=["phase0", "altair"])
        self.assertEqual(result, "transition_phase0_to_altair")

    def test_template_with_generator_functions(self):
        """Test template_test with generator functions (common in spec tests)."""
        inspect.currentframe = self._mock_currentframe("integration_test_module")

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
        self.assertTrue(hasattr(self.test_module, test_name))

        # Test the generator function
        test_func = getattr(self.test_module, test_name)
        gen = test_func(spec="mock_spec", state="mock_state")
        pre_result = next(gen)
        post_result = next(gen)

        self.assertEqual(pre_result[0], "pre")
        self.assertEqual(pre_result[1]["case"], "block_processing")
        self.assertEqual(post_result[0], "post")
        self.assertEqual(post_result[1]["result"], "processed_block_processing")

    def _mock_currentframe_with_function_call(
        self, module_name="integration_test_module", function_name="test_function"
    ):
        """Create a mock frame that simulates being called from within a function."""
        return self.mock_utility.create_mock_currentframe_with_function(module_name, function_name)

    def test_template_called_from_within_function(self):
        """Test template_test decorator when called from within a function (non-module-level)."""
        inspect.currentframe = self._mock_currentframe_with_function_call(
            "integration_test_module", "function_that_calls_template"
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
        self.assertTrue(hasattr(self.test_module, test_name))

        # The registered function should work correctly
        registered_func = getattr(self.test_module, test_name)
        self.assertEqual(registered_func(), "function_scoped_test_example")


class TestTemplateUpgradeDecorators(TestCase):
    """Test suite for template_test_upgrades_from and template_test_upgrades_from_to decorators."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a mock module for testing
        self.test_module = types.ModuleType("upgrade_test_module")
        sys.modules["upgrade_test_module"] = self.test_module

        # Store original functions for restoration
        self.original_currentframe = inspect.currentframe
        self.original_getmodule = inspect.getmodule
        self.mock_utility = MockFrameworkUtility(self.test_module)

    def tearDown(self):
        """Clean up after tests."""
        # Remove test module from sys.modules
        if "upgrade_test_module" in sys.modules:
            del sys.modules["upgrade_test_module"]

        # Restore original functions
        self.mock_utility.restore()

    def _mock_currentframe(self, module_name="upgrade_test_module"):
        """Create a mock frame that simulates being called from a specific module."""
        return self.mock_utility.create_mock_currentframe(module_name)

    def test_template_test_upgrades_from_basic(self):
        """Test basic functionality of template_test_upgrades_from decorator."""
        inspect.currentframe = self._mock_currentframe("upgrade_test_module")

        @template_test_upgrades_from(CAPELLA)
        def _template_upgrade(pre_spec: SpecForkName, post_spec: SpecForkName):
            def test_func():
                return f"upgrade_{pre_spec}_to_{post_spec}"

            return test_func, f"test_upgrade_{pre_spec}_to_{post_spec}"

        # Call the decorated function to trigger registration
        _template_upgrade()

        # The decorator should have registered tests for CAPELLA->DENEB, DENEB->ELECTRA, ELECTRA->FULU
        # Check that tests were registered for the expected upgrades
        self.assertTrue(hasattr(self.test_module, "test_upgrade_capella_to_deneb"))
        self.assertTrue(hasattr(self.test_module, "test_upgrade_deneb_to_electra"))
        self.assertTrue(hasattr(self.test_module, "test_upgrade_electra_to_fulu"))

        # Should NOT have registered for earlier forks
        self.assertFalse(hasattr(self.test_module, "test_upgrade_phase0_to_altair"))
        self.assertFalse(hasattr(self.test_module, "test_upgrade_altair_to_bellatrix"))

        # Execute the registered tests to verify they work
        test_capella_deneb = getattr(self.test_module, "test_upgrade_capella_to_deneb")
        self.assertEqual(test_capella_deneb(), "upgrade_capella_to_deneb")

        test_deneb_electra = getattr(self.test_module, "test_upgrade_deneb_to_electra")
        self.assertEqual(test_deneb_electra(), "upgrade_deneb_to_electra")

        test_electra_fulu = getattr(self.test_module, "test_upgrade_electra_to_fulu")
        self.assertEqual(test_electra_fulu(), "upgrade_electra_to_fulu")

    def test_template_test_upgrades_from_to_basic(self):
        """Test basic functionality of template_test_upgrades_from_to decorator."""
        inspect.currentframe = self._mock_currentframe("upgrade_test_module")

        @template_test_upgrades_from_to(PHASE0, BELLATRIX)
        def _template_range_upgrade(pre_spec: SpecForkName, post_spec: SpecForkName):
            def test_func():
                return f"range_{pre_spec}_to_{post_spec}"

            return test_func, f"test_range_{pre_spec}_to_{post_spec}"

        # Call the decorated function to trigger registration
        _template_range_upgrade()

        # Should have registered tests for PHASE0->ALTAIR, ALTAIR->BELLATRIX, and BELLATRIX->CAPELLA
        self.assertTrue(hasattr(self.test_module, "test_range_phase0_to_altair"))
        self.assertTrue(hasattr(self.test_module, "test_range_altair_to_bellatrix"))
        self.assertTrue(hasattr(self.test_module, "test_range_bellatrix_to_capella"))

        # Should NOT have registered beyond CAPELLA
        self.assertFalse(hasattr(self.test_module, "test_range_capella_to_deneb"))

        # Execute the registered tests
        test_phase0_altair = getattr(self.test_module, "test_range_phase0_to_altair")
        self.assertEqual(test_phase0_altair(), "range_phase0_to_altair")

        test_altair_bellatrix = getattr(self.test_module, "test_range_altair_to_bellatrix")
        self.assertEqual(test_altair_bellatrix(), "range_altair_to_bellatrix")

        test_bellatrix_capella = getattr(self.test_module, "test_range_bellatrix_to_capella")
        self.assertEqual(test_bellatrix_capella(), "range_bellatrix_to_capella")

    def test_template_test_upgrades_from_to_single_upgrade(self):
        """Test template_test_upgrades_from_to with a single upgrade."""
        inspect.currentframe = self._mock_currentframe("upgrade_test_module")

        @template_test_upgrades_from_to(DENEB, DENEB)
        def _template_single(pre_spec: SpecForkName, post_spec: SpecForkName):
            def test_func():
                return f"single_{pre_spec}_to_{post_spec}"

            return test_func, f"test_single_{pre_spec}_to_{post_spec}"

        # Call the decorated function to trigger registration
        _template_single()

        # Should only register the upgrade from DENEB to ELECTRA
        self.assertTrue(hasattr(self.test_module, "test_single_deneb_to_electra"))

        # Should NOT register others
        self.assertFalse(hasattr(self.test_module, "test_single_capella_to_deneb"))
        self.assertFalse(hasattr(self.test_module, "test_single_electra_to_fulu"))


if __name__ == "__main__":
    unittest.main()
