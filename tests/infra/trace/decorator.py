import functools
import inspect

from tests.infra.trace.traced_spec import RecordingSpec


def spec_trace(fn: callable) -> callable:
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
    def wrapper(*args, **kwargs):
        # 1. Bind arguments to find 'spec' and fixtures
        try:
            bound_args = inspect.signature(fn).bind(*args, **kwargs)
            bound_args.apply_defaults()
        except TypeError as e:
            raise RuntimeError("non-test invocation detected") from e

        if "spec" not in bound_args.arguments:
            raise RuntimeError("spec argument not found, cannot proceed")

        # 2. Get the actual spec instance
        real_spec = bound_args.arguments["spec"]

        # 3. Inject the recorder
        recorder = RecordingSpec(real_spec)
        bound_args.arguments["spec"] = recorder

        # 4. Run test & Save trace
        try:
            fn(*bound_args.args, **bound_args.kwargs)
        finally:
            # we need to do this after execution is done before returning data
            recorder._finalize_trace()

            # yield data so that runner can pick it up and dump
            yield "trace", "pydantic", recorder._model

    return wrapper
