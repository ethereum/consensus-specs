import functools
import inspect
from collections.abc import Callable

from tests.infra.trace.traced_spec import RecordingSpec


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
    def wrapper(*args, **kwargs):
        # this might be somewhat overcomplicated just for figuring out if the first arg is a spec of not
        # 1. Bind arguments to find 'spec' and fixtures
        try:
            bound_args = inspect.signature(fn).bind(*args, **kwargs)
            bound_args.apply_defaults()
        except TypeError:
            # Fallback for non-test invocations
            fn(*args, **kwargs)

        if "spec" not in bound_args.arguments:
            fn(*args, **kwargs)

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
            recorder.finalize()

            # yield data so that runner can pick it up and dump
            yield from [
                # trace to be dumped as yaml
                ("trace", "data", recorder._model.model_dump(mode="json", exclude_none=True)),
            ] + [
                (name, "ssz", value)
                # ssz artifacts are already serialized and will be compressed by the dumper
                for name, value in recorder._model._artifacts.items()
            ]

    return wrapper
