import functools
import inspect
from collections.abc import Callable, Generator
from typing import Any

from .traced_spec import RecordingSpec


def spec_trace(fn: Callable) -> Callable:
    """
    Decorator to wrap a pyspec test and record execution traces.
    Usage:
        @with_all_phases  # or other decorators
        @spec_state_test  # still needed as before
        @spec_trace  # new decorator to record trace
        def test_my_feature(spec, ...):
            ...
    """

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Generator:
        # 1. Bind arguments to find 'spec' and fixtures
        try:
            bound_args = inspect.signature(fn).bind(*args, **kwargs)
            bound_args.apply_defaults()
        except TypeError as e:
            raise TypeError(
                f"Failed to bind arguments for test function '{fn.__name__}': {e}"
            ) from e

        if "spec" not in bound_args.arguments:
            raise ValueError(
                f"spec argument not found for test function '{fn.__name__}', cannot proceed"
            )

        # 2. Get the actual spec instance
        real_spec = bound_args.arguments["spec"]

        # 3. Inject the recorder
        recorder: RecordingSpec = RecordingSpec(real_spec)
        bound_args.arguments["spec"] = recorder

        # 4. Run test & Save trace
        fn(*bound_args.args, **bound_args.kwargs)
        # we need to do this after execution is done before returning data
        recorder.finalize_trace()

        # yield data so that runner can pick it up and dump
        yield "trace", "pydantic", recorder.model

    return wrapper
