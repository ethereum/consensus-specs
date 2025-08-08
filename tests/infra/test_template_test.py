import builtins
import inspect
import sys
import types
import unittest
from collections.abc import Callable
from typing import Any
from unittest import TestCase

from eth2spec.test.helpers.constants import ALTAIR, BELLATRIX, CAPELLA, DENEB, ELECTRA, FULU, PHASE0
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

    def create_mock_currentframe_with_nested_calls(
        self, module_name: str
    ) -> Callable[[], MockFrame]:
        """
        Create a mock frame that simulates being called from within nested function contexts.

        Args:
            module_name: The name of the module

        Returns:
            A function that returns a mock frame with nested call stack
        """

        def mock_frame():
            # Current frame (decorator's frame)
            current_frame = MockFrame("tests.infra.template_test", "template_test")

            # Immediate caller frame (deeply_nested_function)
            deep_frame = MockFrame(module_name, "deeply_nested_function")

            # Middle frame (inner_function)
            inner_frame = MockFrame(module_name, "inner_function")

            # Outer frame (outer_function)
            outer_frame = MockFrame(module_name, "outer_function")

            # Link the frames to simulate nested calls
            current_frame.f_back = deep_frame
            deep_frame.f_back = inner_frame
            inner_frame.f_back = outer_frame

            return current_frame

        # Set up mock getmodule
        def mock_getmodule(frame):
            if hasattr(frame, "f_globals") and frame.f_globals.get("__name__") == module_name:
                return self.test_module
            return self.original_getmodule(frame)

        inspect.getmodule = mock_getmodule
        return mock_frame

    def create_mock_getmodule_for_invalid_module(self) -> Callable[[Any], types.ModuleType | None]:
        """
        Create a mock getmodule function that returns None for invalid modules.

        Returns:
            A mock getmodule function
        """

        def mock_getmodule(frame):
            if (
                hasattr(frame, "f_globals")
                and frame.f_globals.get("__name__") == "nonexistent_module"
            ):
                return None
            return self.original_getmodule(frame)

        return mock_getmodule

    def create_mock_getmodule_for_custom_module(
        self, module_name: str, target_module: types.ModuleType
    ) -> Callable[[Any], types.ModuleType | None]:
        """
        Create a mock getmodule function that returns a specific module for a given name.

        Args:
            module_name: The module name to match
            target_module: The module to return for that name

        Returns:
            A mock getmodule function
        """

        def mock_getmodule(frame):
            if hasattr(frame, "f_globals") and frame.f_globals.get("__name__") == module_name:
                return target_module
            return self.original_getmodule(frame)

        return mock_getmodule

    def restore(self):
        """Restore original inspect functions."""
        inspect.currentframe = self.original_currentframe
        inspect.getmodule = self.original_getmodule


class MockDecoratorUtility:
    """Utility class for creating common mock decorators used in tests."""

    @staticmethod
    def create_simple_wrapper(prefix: str) -> Callable:
        """
        Create a simple decorator that wraps the result with a prefix.

        Args:
            prefix: The prefix to add to the result

        Returns:
            A decorator function
        """

        def decorator(fn):
            def wrapper(*args, **kwargs):
                result = fn(*args, **kwargs)
                return f"{prefix}({result})"

            wrapper.__name__ = fn.__name__
            return wrapper

        return decorator

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

    @staticmethod
    def create_mock_with_state() -> Callable:
        """
        Create a mock decorator that adds state to kwargs.

        Returns:
            A decorator function
        """

        def mock_with_state(fn):
            def wrapper(*args, **kwargs):
                kwargs["state"] = "mock_genesis_state"
                return fn(*args, **kwargs)

            wrapper.__name__ = fn.__name__
            return wrapper

        return mock_with_state

    @staticmethod
    def create_mock_with_config(config_values: dict) -> Callable:
        """
        Create a mock decorator that adds config to kwargs.

        Args:
            config_values: Configuration values to add

        Returns:
            A decorator function
        """

        def decorator(fn):
            def wrapper(*args, **kwargs):
                kwargs["config"] = config_values
                return fn(*args, **kwargs)

            wrapper.__name__ = fn.__name__
            return wrapper

        return decorator

    @staticmethod
    def create_failing_decorator(error_message: str) -> Callable:
        """
        Create a mock decorator that raises an exception.

        Args:
            error_message: The error message to raise

        Returns:
            A decorator that fails
        """

        def failing_decorator(fn):
            def wrapper(*args, **kwargs):
                raise ValueError(error_message)

            wrapper.__name__ = fn.__name__
            return wrapper

        return failing_decorator


def create_simple_mock_frame(module_name: str) -> Callable[[], Any]:
    """
    Create a simple mock frame without f_back.

    Args:
        module_name: The module name

    Returns:
        A function that returns a MockFrame with no f_back
    """

    class SimpleMockFrame:
        def __init__(self):
            self.f_back = None

    return lambda: SimpleMockFrame()


def create_invalid_module_mock_frame() -> Callable[[], MockRootFrame]:
    """
    Create a mock frame for testing invalid module scenarios.

    Returns:
        A function that returns a mock frame for nonexistent module
    """

    def mock_frame():
        mock_caller = MockFrame("nonexistent_module")
        mock_root = MockRootFrame(mock_caller)
        return mock_root

    return mock_frame


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

    def test_multiple_template_calls(self):
        """Test that multiple calls to the same template register different tests."""
        inspect.currentframe = self._mock_currentframe("test_module")

        @template_test
        def _test_template(param):
            def test_func():
                return f"test_{param}"

            return test_func, f"test_multiple_{param}"

        # Call template multiple times
        _test_template("first")
        _test_template("second")

        # Verify both tests are registered
        test_name1 = "test_multiple_first"
        test_name2 = "test_multiple_second"
        self.assertTrue(hasattr(self.test_module, test_name1))
        self.assertTrue(hasattr(self.test_module, test_name2))

        # Verify different tests are created
        test_func1 = getattr(self.test_module, test_name1)
        test_func2 = getattr(self.test_module, test_name2)
        self.assertIsNot(test_func1, test_func2)
        self.assertEqual(test_func1(), "test_first")
        self.assertEqual(test_func2(), "test_second")

    def test_template_with_no_parameters(self):
        """Test template function with no parameters."""
        inspect.currentframe = self._mock_currentframe("test_module")

        @template_test
        def _test_template():
            def test_func():
                return "static_test"

            return test_func, "test_static"

        _test_template()

        test_name = "test_static"
        self.assertTrue(hasattr(self.test_module, test_name))
        test_func = getattr(self.test_module, test_name)
        self.assertEqual(test_func(), "static_test")

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

    def test_template_with_complex_return_values(self):
        """Test template that returns complex test functions."""
        inspect.currentframe = self._mock_currentframe("test_module")

        @template_test
        def _test_template(spec_name):
            def test_func(spec, state):
                # Simulate a typical spec test function
                return {"spec": spec, "state": state, "spec_name": spec_name}

            return test_func, f"test_complex_{spec_name}"

        _test_template("phase0")

        test_name = "test_complex_phase0"
        self.assertTrue(hasattr(self.test_module, test_name))
        test_func = getattr(self.test_module, test_name)
        result = test_func("mock_spec", "mock_state")
        self.assertEqual(result["spec_name"], "phase0")

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

    def test_frame_inspection_error_no_caller_frame(self):
        """Test error handling when caller frame is None."""

        # Mock currentframe to return a frame with no f_back
        inspect.currentframe = create_simple_mock_frame("test_module")

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

    def test_invalid_module_name(self):
        """Test error handling when module name is invalid."""

        # Mock frame with invalid module name
        inspect.currentframe = create_invalid_module_mock_frame()
        inspect.getmodule = self.mock_utility.create_mock_getmodule_for_invalid_module()

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

    def test_template_function_returns_invalid_tuple(self):
        """Test error handling when template function returns invalid tuple."""
        inspect.currentframe = self._mock_currentframe("test_module")

        @template_test  # type: ignore
        def _test_template():
            # Return invalid tuple (too many elements)
            def test_func():
                pass

            return test_func, "test_name", "extra_element"

        # This should raise an error when unpacking
        with self.assertRaises(ValueError):
            _test_template()

    def test_template_function_returns_non_tuple(self):
        """Test error handling when template function returns non-tuple."""
        inspect.currentframe = self._mock_currentframe("test_module")

        @template_test  # type: ignore
        def _test_template():
            # Return a non-tuple value
            return "not_a_tuple"

        with self.assertRaises(ValueError):
            _test_template()

    def test_template_function_returns_none(self):
        """Test error handling when template function returns None."""
        inspect.currentframe = self._mock_currentframe("test_module")

        @template_test  # type: ignore
        def _test_template():
            # Return None instead of tuple
            return None

        with self.assertRaises(TypeError):
            _test_template()

    def test_template_function_raises_exception(self):
        """Test error handling when template function raises an exception."""
        inspect.currentframe = self._mock_currentframe("test_module")

        @template_test
        def _test_template():
            # Raise an exception during template execution
            raise ValueError("Template error")

        with self.assertRaises(ValueError) as context:
            _test_template()

        self.assertEqual(str(context.exception), "Template error")

    def test_overwrite_existing_attribute(self):
        """Test that template can overwrite existing module attributes."""
        inspect.currentframe = self._mock_currentframe("test_module")

        # Set an existing attribute
        setattr(self.test_module, "test_overwrite", "original_value")

        @template_test
        def _test_template():
            def test_func():
                return "new_value"

            return test_func, "test_overwrite"

        _test_template()

        # Verify the attribute was overwritten
        test_name = "test_overwrite"
        registered_func = getattr(self.test_module, test_name)
        self.assertEqual(registered_func(), "new_value")

    def test_template_with_empty_string_name(self):
        """Test template function that returns empty string as name."""
        inspect.currentframe = self._mock_currentframe("test_module")

        @template_test
        def _test_template():
            def test_func():
                return "empty_name_test"

            return test_func, ""

        _test_template()

        test_name = ""
        self.assertTrue(hasattr(self.test_module, test_name))
        test_func = getattr(self.test_module, test_name)
        self.assertEqual(test_func(), "empty_name_test")

    def test_template_with_special_characters_in_name(self):
        """Test template function with special characters in test name."""
        inspect.currentframe = self._mock_currentframe("test_module")

        @template_test
        def _test_template():
            def test_func():
                return "special_test"

            return test_func, "test_with_special-chars_123"

        _test_template()

        test_name = "test_with_special-chars_123"
        self.assertTrue(hasattr(self.test_module, test_name))

    def test_decorated_function_preserves_original_behavior(self):
        """Test that the decorated function still behaves like the original."""
        inspect.currentframe = self._mock_currentframe("test_module")

        def original_template(param):
            def test_func():
                return f"original_{param}"

            return test_func, f"test_original_{param}"

        decorated_template = template_test(original_template)

        # The original returns a tuple, decorated returns None
        orig_result = original_template("test")
        decorated_template("test")

        # Check that the test was registered with the same name
        self.assertTrue(hasattr(self.test_module, orig_result[1]))
        registered_func = getattr(self.test_module, orig_result[1])
        self.assertEqual(orig_result[0](), registered_func())  # Same test function behavior

    def test_multiple_modules(self):
        """Test template_test works with different modules."""
        # Create second test module
        test_module2 = types.ModuleType("test_module2")
        sys.modules["test_module2"] = test_module2

        try:
            # Test with first module
            inspect.currentframe = self._mock_currentframe("test_module")

            @template_test
            def _test_template1():
                def test_func():
                    return "module1_test"

                return test_func, "test_module1"

            _test_template1()

            # Test with second module - create a new mock for the second module
            mock_utility2 = MockFrameworkUtility(test_module2)
            inspect.currentframe = mock_utility2.create_mock_currentframe("test_module2")

            @template_test
            def _test_template2():
                def test_func():
                    return "module2_test"

                return test_func, "test_module2"

            _test_template2()

            # Verify tests are registered in correct modules
            self.assertTrue(hasattr(self.test_module, "test_module1"))
            self.assertTrue(hasattr(test_module2, "test_module2"))
            self.assertFalse(hasattr(self.test_module, "test_module2"))
            self.assertFalse(hasattr(test_module2, "test_module1"))

        finally:
            # Clean up
            if "test_module2" in sys.modules:
                del sys.modules["test_module2"]

    def test_decorator_with_builtin_module(self):
        """Test behavior when called from a builtin module."""

        # Create a special mock for builtins
        inspect.currentframe = self.mock_utility.create_mock_currentframe("builtins")
        inspect.getmodule = self.mock_utility.create_mock_getmodule_for_custom_module(
            "builtins", builtins
        )

        # This should work but register in the builtins module
        @template_test
        def _test_template():
            def test_func():
                return "builtin_test"

            return test_func, "test_builtin"

        _test_template()

        # Verify the test was registered in builtins
        test_name = "test_builtin"
        self.assertTrue(hasattr(builtins, test_name))

        # Clean up
        delattr(builtins, test_name)

    def test_concurrent_decoration(self):
        """Test that multiple decorators can be applied concurrently."""
        inspect.currentframe = self._mock_currentframe("test_module")

        @template_test
        def _test_template1():
            def test_func():
                return "concurrent1"

            return test_func, "test_concurrent1"

        @template_test
        def _test_template2():
            def test_func():
                return "concurrent2"

            return test_func, "test_concurrent2"

        # Call both templates
        _test_template1()
        _test_template2()

        # Verify both tests are registered
        self.assertTrue(hasattr(self.test_module, "test_concurrent1"))
        self.assertTrue(hasattr(self.test_module, "test_concurrent2"))

        func1 = getattr(self.test_module, "test_concurrent1")
        func2 = getattr(self.test_module, "test_concurrent2")

        self.assertEqual(func1(), "concurrent1")
        self.assertEqual(func2(), "concurrent2")

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

    def test_integration_with_state_decorators(self):
        """Test template_test integration with state-related decorators."""
        inspect.currentframe = self._mock_currentframe("integration_test_module")

        # Mock state decorator
        mock_with_state = MockDecoratorUtility.create_mock_with_state()

        @template_test
        def _test_template(test_type):
            @mock_with_state
            def test_state_function(spec, state):
                return f"{test_type}_test_with_state_{state}"

            return test_state_function, f"test_state_{test_type}"

        # Call the template
        _test_template("validator")

        # Verify registration and functionality
        test_name = "test_state_validator"
        self.assertTrue(hasattr(self.test_module, test_name))

        test_func = getattr(self.test_module, test_name)
        result = test_func(spec="mock_spec", state="unused")
        self.assertEqual(result, "validator_test_with_state_mock_genesis_state")

    def test_integration_with_multiple_decorators(self):
        """Test template_test with multiple stacked decorators."""
        inspect.currentframe = self._mock_currentframe("integration_test_module")

        # Mock multiple decorators
        mock_decorator1 = MockDecoratorUtility.create_simple_wrapper("decorator1")
        mock_decorator2 = MockDecoratorUtility.create_simple_wrapper("decorator2")

        @template_test
        def _test_template(param):
            @mock_decorator1
            @mock_decorator2
            def test_multi_decorated(spec):
                return f"base_test_{param}"

            return test_multi_decorated, f"test_multi_{param}"

        # Call the template
        _test_template("example")

        # Verify the decorators are applied correctly
        test_name = "test_multi_example"
        self.assertTrue(hasattr(self.test_module, test_name))

        test_func = getattr(self.test_module, test_name)
        result = test_func(spec="mock_spec")
        self.assertEqual(result, "decorator1(decorator2(base_test_example))")

    def test_integration_with_parametrized_decorators(self):
        """Test template_test with parametrized decorators."""
        inspect.currentframe = self._mock_currentframe("integration_test_module")

        # Mock parametrized decorator
        mock_with_config = MockDecoratorUtility.create_mock_with_config

        @template_test
        def _test_template(fork_name, config_type):
            @mock_with_config({"fork": fork_name, "type": config_type})
            def test_configured(spec, config):
                return f"test_{fork_name}_{config_type}_{config}"

            return test_configured, f"test_configured_{fork_name}_{config_type}"

        # Call the template
        _test_template("deneb", "mainnet")

        # Verify the parametrized decorator works
        test_name = "test_configured_deneb_mainnet"
        self.assertTrue(hasattr(self.test_module, test_name))

        test_func = getattr(self.test_module, test_name)
        result = test_func(spec="mock_spec", config="unused")
        expected_config = {"fork": "deneb", "type": "mainnet"}
        self.assertIn(str(expected_config), result)

    def test_integration_error_handling_with_decorators(self):
        """Test error handling when decorators fail."""
        inspect.currentframe = self._mock_currentframe("integration_test_module")

        # Mock decorator that raises an exception
        failing_decorator = MockDecoratorUtility.create_failing_decorator("Decorator failed")

        @template_test
        def _test_template():
            @failing_decorator
            def test_failing():
                return "should_not_reach_here"

            return test_failing, "test_failing"

        # The template should work, but calling the test function should fail
        _test_template()

        # Verify registration
        test_name = "test_failing"
        self.assertTrue(hasattr(self.test_module, test_name))

        # Verify the decorated function fails as expected
        test_func = getattr(self.test_module, test_name)
        with self.assertRaises(ValueError) as context:
            test_func()
        self.assertEqual(str(context.exception), "Decorator failed")

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

    def test_template_called_from_within_class_method(self):
        """Test template_test decorator when called from within a class method."""
        inspect.currentframe = self._mock_currentframe_with_function_call(
            "integration_test_module", "TestGenerator.generate_test"
        )

        @template_test
        def _test_template(param):
            def test_func():
                return f"class_method_test_{param}"

            return test_func, f"test_class_method_{param}"

        class TestGenerator:
            def generate_test(self, param):
                """Method that calls the template."""
                _test_template(param)

        # Call the template from within the class method
        generator = TestGenerator()
        generator.generate_test("method_call")

        # The template should still register in the module
        test_name = "test_class_method_method_call"
        self.assertTrue(hasattr(self.test_module, test_name))

        # The registered function should work correctly
        registered_func = getattr(self.test_module, test_name)
        self.assertEqual(registered_func(), "class_method_test_method_call")

    def _mock_currentframe_with_nested_calls(self, module_name="integration_test_module"):
        """Create a mock frame that simulates being called from within nested function contexts."""
        return self.mock_utility.create_mock_currentframe_with_nested_calls(module_name)

    def test_template_called_from_nested_function_context(self):
        """Test template_test decorator when called from within nested function contexts."""
        inspect.currentframe = self._mock_currentframe_with_nested_calls("integration_test_module")

        @template_test
        def _test_template(param):
            def test_func():
                return f"nested_context_test_{param}"

            return test_func, f"test_nested_context_{param}"

        def outer_function():
            def inner_function():
                def deeply_nested_function():
                    _test_template("deeply_nested")

                deeply_nested_function()

            inner_function()

        # Call the template from deeply nested context
        outer_function()

        # The template should still register in the module, regardless of nesting
        test_name = "test_nested_context_deeply_nested"
        self.assertTrue(hasattr(self.test_module, test_name))

        # The registered function should work correctly
        registered_func = getattr(self.test_module, test_name)
        self.assertEqual(registered_func(), "nested_context_test_deeply_nested")


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

    def test_template_test_upgrades_from_phase0(self):
        """Test template_test_upgrades_from starting from PHASE0."""
        inspect.currentframe = self._mock_currentframe("upgrade_test_module")

        @template_test_upgrades_from(PHASE0)
        def _template_all_upgrades(pre_spec: SpecForkName, post_spec: SpecForkName):
            def test_func():
                return f"all_{pre_spec}_to_{post_spec}"

            return test_func, f"test_all_upgrades_{pre_spec}_to_{post_spec}"

        # Call the decorated function to trigger registration
        _template_all_upgrades()

        # Should register tests for all transitions
        self.assertTrue(hasattr(self.test_module, "test_all_upgrades_phase0_to_altair"))
        self.assertTrue(hasattr(self.test_module, "test_all_upgrades_altair_to_bellatrix"))
        self.assertTrue(hasattr(self.test_module, "test_all_upgrades_bellatrix_to_capella"))
        self.assertTrue(hasattr(self.test_module, "test_all_upgrades_capella_to_deneb"))
        self.assertTrue(hasattr(self.test_module, "test_all_upgrades_deneb_to_electra"))
        self.assertTrue(hasattr(self.test_module, "test_all_upgrades_electra_to_fulu"))

    def test_template_test_upgrades_from_last_fork(self):
        """Test template_test_upgrades_from starting from the last fork."""
        inspect.currentframe = self._mock_currentframe("upgrade_test_module")

        @template_test_upgrades_from(FULU)
        def _template_last_fork(pre_spec: SpecForkName, post_spec: SpecForkName):
            def test_func():
                return f"last_{pre_spec}_to_{post_spec}"

            return test_func, f"test_last_{pre_spec}_to_{post_spec}"

        # Call the decorated function to trigger registration
        _template_last_fork()

        # Should not register any tests since FULU is the last fork
        # Check that no test names starting with "test_last_" were registered
        for attr_name in dir(self.test_module):
            self.assertFalse(attr_name.startswith("test_last_"))

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

    def test_template_test_upgrades_from_to_all_forks(self):
        """Test template_test_upgrades_from_to covering all forks."""
        inspect.currentframe = self._mock_currentframe("upgrade_test_module")

        @template_test_upgrades_from_to(PHASE0, FULU)
        def _template_all(pre_spec: SpecForkName, post_spec: SpecForkName):
            def test_func():
                return f"full_{pre_spec}_to_{post_spec}"

            return test_func, f"test_full_{pre_spec}_to_{post_spec}"

        # Call the decorated function to trigger registration
        _template_all()

        # Should register all transitions
        self.assertTrue(hasattr(self.test_module, "test_full_phase0_to_altair"))
        self.assertTrue(hasattr(self.test_module, "test_full_altair_to_bellatrix"))
        self.assertTrue(hasattr(self.test_module, "test_full_bellatrix_to_capella"))
        self.assertTrue(hasattr(self.test_module, "test_full_capella_to_deneb"))
        self.assertTrue(hasattr(self.test_module, "test_full_deneb_to_electra"))
        self.assertTrue(hasattr(self.test_module, "test_full_electra_to_fulu"))

    def test_template_test_upgrades_with_custom_module(self):
        """Test upgrade decorators with _instantiate_module parameter."""
        # Create a mock module to register tests in
        mock_module = types.ModuleType("mock_upgrade_module")
        sys.modules["mock_upgrade_module"] = mock_module

        try:
            inspect.currentframe = self._mock_currentframe("upgrade_test_module")

            @template_test_upgrades_from(DENEB)
            def _template_custom(pre_spec: SpecForkName, post_spec: SpecForkName):
                def test_function():
                    return f"custom_{pre_spec}_to_{post_spec}"

                return test_function, f"test_custom_{pre_spec}_to_{post_spec}"

            # Call with custom module
            _template_custom(_instantiate_module=mock_module)

            # Check that tests were registered in the mock module
            self.assertTrue(hasattr(mock_module, "test_custom_deneb_to_electra"))
            self.assertTrue(hasattr(mock_module, "test_custom_electra_to_fulu"))

            # Should NOT be registered in the default module
            self.assertFalse(hasattr(self.test_module, "test_custom_deneb_to_electra"))

            # Verify they work
            test_deneb_electra = getattr(mock_module, "test_custom_deneb_to_electra")
            self.assertEqual(test_deneb_electra(), "custom_deneb_to_electra")

        finally:
            if "mock_upgrade_module" in sys.modules:
                del sys.modules["mock_upgrade_module"]

    def test_template_test_upgrades_complex_function(self):
        """Test upgrade decorators with more complex test functions."""
        inspect.currentframe = self._mock_currentframe("upgrade_test_module")

        @template_test_upgrades_from_to(ALTAIR, CAPELLA)
        def _template_complex(pre_spec: SpecForkName, post_spec: SpecForkName):
            def test_func(spec, state):
                # Simulate a complex spec test
                return {
                    "pre_spec": pre_spec,
                    "post_spec": post_spec,
                    "spec": spec,
                    "state": state,
                    "result": f"transition_{pre_spec}_to_{post_spec}_complete",
                }

            return test_func, f"test_complex_{pre_spec}_to_{post_spec}"

        # Call the decorated function to trigger registration
        _template_complex()

        # Verify registration
        self.assertTrue(hasattr(self.test_module, "test_complex_altair_to_bellatrix"))
        self.assertTrue(hasattr(self.test_module, "test_complex_bellatrix_to_capella"))

        # Test execution
        test_func = getattr(self.test_module, "test_complex_altair_to_bellatrix")
        result = test_func("mock_spec", "mock_state")

        self.assertEqual(result["pre_spec"], "altair")
        self.assertEqual(result["post_spec"], "bellatrix")
        self.assertEqual(result["spec"], "mock_spec")
        self.assertEqual(result["state"], "mock_state")
        self.assertEqual(result["result"], "transition_altair_to_bellatrix_complete")

    def test_template_test_upgrades_with_decorators(self):
        """Test upgrade decorators with additional decorators on test functions."""
        inspect.currentframe = self._mock_currentframe("upgrade_test_module")

        # Mock decorator
        mock_decorator = MockDecoratorUtility.create_simple_wrapper("decorated")

        @template_test_upgrades_from(ELECTRA)
        def _template_decorated(pre_spec: SpecForkName, post_spec: SpecForkName):
            @mock_decorator
            def test_func():
                return f"test_{pre_spec}_to_{post_spec}"

            return test_func, f"test_decorated_{pre_spec}_to_{post_spec}"

        # Call the decorated function to trigger registration
        _template_decorated()

        # Verify registration
        self.assertTrue(hasattr(self.test_module, "test_decorated_electra_to_fulu"))

        # Test execution with decorator
        test_func = getattr(self.test_module, "test_decorated_electra_to_fulu")
        result = test_func()
        self.assertEqual(result, "decorated(test_electra_to_fulu)")

    def test_template_test_upgrades_return_value(self):
        """Test that upgrade decorators properly register all expected tests."""
        inspect.currentframe = self._mock_currentframe("upgrade_test_module")

        @template_test_upgrades_from_to(CAPELLA, ELECTRA)
        def _template_return(pre_spec: SpecForkName, post_spec: SpecForkName):
            def test_func():
                return f"return_{pre_spec}_to_{post_spec}"

            return test_func, f"test_return_{pre_spec}_to_{post_spec}"

        # Call the decorated function to trigger registration
        _template_return()

        # The decorator should have registered tests for CAPELLA->DENEB and DENEB->ELECTRA
        self.assertTrue(hasattr(self.test_module, "test_return_capella_to_deneb"))
        self.assertTrue(hasattr(self.test_module, "test_return_deneb_to_electra"))

        # Verify the tests work correctly
        test_capella_deneb = getattr(self.test_module, "test_return_capella_to_deneb")
        self.assertEqual(test_capella_deneb(), "return_capella_to_deneb")

        test_deneb_electra = getattr(self.test_module, "test_return_deneb_to_electra")
        self.assertEqual(test_deneb_electra(), "return_deneb_to_electra")


if __name__ == "__main__":
    unittest.main()
