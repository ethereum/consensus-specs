import inspect
from collections.abc import Callable
from contextlib import suppress
from functools import wraps
from typing import TypeVar

from eth2spec.test.helpers.constants import PHASE0, POST_FORK_OF
from eth2spec.test.helpers.typing import SpecForkName

# Type definitions
F = TypeVar("F", bound=Callable[..., tuple[Callable, str]])


def template_test(template_test_func: F) -> Callable[..., tuple[Callable, str]]:
    """
    This is a decorator that applies to a template test function.
    The template test function returns a function and a string name.
    The function returned is the actual test to be run, and the string is its name.
    The decorator should be used to register the test function in the caller's module.

    Usage:
        @template_test
        def _template_test_something(param1, param2):
            def test_function(spec, state):
                # test implementation
                pass
            return test_function, f"test_something_{param1}_{param2}"

    The decorator will automatically register the test in the caller's module,
    making it discoverable by pytest.

    To register in a specific module instead of the caller's module:
        test_func, test_name = _template_test_something(param1, param2, _instantiate_module=some_module)
    """

    # Create a wrapper that registers the test when called
    def wrapper(*args, **kwargs) -> None:
        # Extract _instantiate_module parameter if provided (not passed to template_test_func)
        target_module = kwargs.pop("_instantiate_module", None)

        if target_module is None:
            # Get the caller's module with improved error handling
            frame = None
            with suppress(AttributeError):
                frame = inspect.currentframe()
                if frame and frame.f_back:
                    target_module = inspect.getmodule(frame.f_back)

            if target_module is None:
                raise RuntimeError("Could not determine target module for test registration")

        test_func, test_name = template_test_func(*args, **kwargs)
        setattr(target_module, test_name, test_func)

    return wrapper


def template_test_upgrades_from(
    _from: SpecForkName,
) -> Callable[[Callable[[SpecForkName, SpecForkName], tuple[Callable, str]]], Callable]:
    """
    This is a decorator that applies to a template test function for fork upgrades.
    It takes a mandatory parameter _from: SpecForkName and automatically applies
    the template to all upgrades starting from that fork.

    The template test function must have two parameters (pre_spec: SpecForkName, post_spec: SpecForkName)
    and return tuple[Callable, str] like in template_test.

    Usage:
        @template_test_upgrades_from(ELECTRA)
        def _template_test_something(pre_spec: SpecForkName, post_spec: SpecForkName) -> Tuple[Callable, str]:
            def test_function(spec, state):
                # test implementation
                pass
            return test_function, f"test_something_{pre_spec}_to_{post_spec}"

    The decorator will automatically register tests for all fork upgrades starting from _from.
    """

    def decorator(
        template_func: Callable[[SpecForkName, SpecForkName], tuple[Callable, str]],
    ) -> Callable:
        # First, wrap the template function with @template_test
        template_with_test = template_test(template_func)

        @wraps(template_func)
        def wrapper(*args, **kwargs) -> None:
            # Extract _instantiate_module parameter if provided
            target_module = kwargs.pop("_instantiate_module", None)

            if target_module is None:
                # Get the caller's module with improved error handling
                frame = None
                with suppress(AttributeError):
                    frame = inspect.currentframe()
                    if frame and frame.f_back:
                        target_module = inspect.getmodule(frame.f_back)

                if target_module is None:
                    raise RuntimeError("Could not determine target module for test registration")

            # Apply the template to all upgrades starting from _from
            pre_fork = _from
            while pre_fork:
                post_fork = POST_FORK_OF.get(pre_fork)
                if not post_fork:
                    break

                # Call the template_test wrapped function with _instantiate_module
                template_with_test(pre_fork, post_fork, _instantiate_module=target_module)
                pre_fork = post_fork

        return wrapper

    return decorator


def template_test_upgrades_from_to(
    _from: SpecForkName, _to: SpecForkName
) -> Callable[[Callable[[SpecForkName, SpecForkName], tuple[Callable, str]]], Callable]:
    """
    This is a decorator that applies to a template test function for fork upgrades.
    It takes two mandatory parameters _from and _to: SpecForkName and automatically applies
    the template to all upgrades from _from fork up to and including _to fork.

    The template test function must have two parameters (pre_spec: SpecForkName, post_spec: SpecForkName)
    and return tuple[Callable, str] like in template_test.

    Usage:
        @template_test_upgrades_from_to(PHASE0, CAPELLA)
        def _template_test_something(pre_spec: SpecForkName, post_spec: SpecForkName) -> Tuple[Callable, str]:
            def test_function(spec, state):
                # test implementation
                pass
            return test_function, f"test_something_{pre_spec}_to_{post_spec}"

    The decorator will automatically register tests for all fork upgrades from _from to _to (inclusive).
    """

    def decorator(
        template_func: Callable[[SpecForkName, SpecForkName], tuple[Callable, str]],
    ) -> Callable:
        # First, wrap the template function with @template_test
        template_with_test = template_test(template_func)

        @wraps(template_func)
        def wrapper(*args, **kwargs) -> None:
            # Extract _instantiate_module parameter if provided
            target_module = kwargs.pop("_instantiate_module", None)

            if target_module is None:
                # Get the caller's module with improved error handling
                frame = None
                with suppress(AttributeError):
                    frame = inspect.currentframe()
                    if frame and frame.f_back:
                        target_module = inspect.getmodule(frame.f_back)

                if target_module is None:
                    raise RuntimeError("Could not determine target module for test registration")

            # Apply the template to all upgrades from _from to _to
            pre_fork = _from
            while pre_fork:
                post_fork = POST_FORK_OF.get(pre_fork)
                if not post_fork:
                    break

                # Call the template_test wrapped function with _instantiate_module
                template_with_test(pre_fork, post_fork, _instantiate_module=target_module)

                # Stop if we've reached the target fork
                if pre_fork == _to:
                    break

                pre_fork = post_fork

        return wrapper

    return decorator


def template_test_upgrades_all(
    template_func: Callable[[SpecForkName, SpecForkName], tuple[Callable, str]],
) -> Callable:
    return template_test_upgrades_from(PHASE0)(template_func)
